import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import webbrowser
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
import os
import zipfile
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Dark theme colors
TITLE_COLOR = "#d4a017"
BACKGROUND_COLOR = "#1e1e1e"
TEXT_COLOR = "#ffffff"
BUTTON_COLOR = "#333333"
ENTRY_BG_COLOR = "#3c3c3c"
ENTRY_FG_COLOR = "#ffffff"

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "spotify_credentials.txt")
cancel_requested = False  # Global flag for canceling downloads

def save_credentials(client_id, client_secret):
    with open(CREDENTIALS_FILE, "w") as f:
        f.write(f"{client_id}\n{client_secret}")

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            lines = f.readlines()
            if len(lines) >= 2:
                return lines[0].strip(), lines[1].strip()
    return None, None

def initialize_spotify(client_id, client_secret):
    global sp
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))

def get_spotify_data(url):
    if "track" in url:
        return "track", [url]
    elif "playlist" in url:
        return "playlist", [track['track']['external_urls']['spotify'] for track in sp.playlist_tracks(url)['items']]
    elif "album" in url:
        return "album", [track['external_urls']['spotify'] for track in sp.album_tracks(url)['items']]
    else:
        console.insert(tk.END, "Invalid Spotify URL\n")
        return None, []

def get_spotify_song_metadata(track_url):
    try:
        track_id = track_url.split("/")[-1].split("?")[0]
        track = sp.track(track_id)
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        search_term = f"{track_name} {artist_name}"
        return search_term
    except Exception as e:
        console.insert(tk.END, f"Could not retrieve track data: {e}\n")
        return None

def download_youtube_audio(search_term, download_folder):
    global cancel_requested
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
        'ffmpeg_location': os.path.join(os.path.dirname(__file__), 'ffmpeg', 'ffmpeg.exe')
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            console.insert(tk.END, f"Starting download: {search_term}\n")
            console.see(tk.END)
            
            # Check if cancellation was requested
            if cancel_requested:
                console.insert(tk.END, f"Download of '{search_term}' canceled.\n")
                console.see(tk.END)
                return
            
            info_dict = ydl.extract_info(f"ytsearch:{search_term}", download=True)
            video = info_dict['entries'][0]
            console.insert(tk.END, f"Downloaded: {video['title']}\n")
            console.see(tk.END)
        except Exception as e:
            console.insert(tk.END, f"Could not download audio for {search_term}: {e}\n")
            console.see(tk.END)

def create_zip_from_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))

def select_zip_location():
    zip_location = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP files", "*.zip")])
    zip_location_entry.delete(0, tk.END)
    zip_location_entry.insert(0, zip_location)

def on_download_click():
    reset_ui()  # Reset UI before starting a new download
    download_button.config(state=tk.DISABLED)  # Disable the download button
    cancel_button.config(state=tk.NORMAL)
    threading.Thread(target=download_songs).start()

def download_songs():
    client_id = client_id_entry.get().strip()
    client_secret = client_secret_entry.get().strip()

    if not client_id or not client_secret:
        console.insert(tk.END, "Please enter your Spotify Client ID and Secret.\n")
        reset_ui()  # Reset UI on error
        return

    initialize_spotify(client_id, client_secret)
    url = entry.get().strip()
    zip_path = zip_location_entry.get().strip()

    if not url:
        console.insert(tk.END, "Please enter a Spotify URL.\n")
        reset_ui()  # Reset UI on error
        return
    if not zip_path:
        console.insert(tk.END, "Please select a save location for the ZIP file.\n")
        reset_ui()  # Reset UI on error
        return

    item_type, track_urls = get_spotify_data(url)
    if not track_urls:
        reset_ui()  # Reset UI if no tracks found
        return

    download_folder = os.path.join(os.getcwd(), "downloads")
    os.makedirs(download_folder, exist_ok=True)

    total_songs = len(track_urls)
    songs_downloaded = 0

    progress_bar["maximum"] = total_songs
    progress_label.config(text=f"0/{total_songs}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for track_url in track_urls:
            search_term = get_spotify_song_metadata(track_url)
            if search_term:
                futures.append(executor.submit(download_youtube_audio, search_term, download_folder))

        for future in as_completed(futures):
            if cancel_requested:
                console.insert(tk.END, "Download canceled by user.\n")
                break
            try:
                future.result()
                songs_downloaded += 1
                progress_bar["value"] = songs_downloaded
                progress_label.config(text=f"{songs_downloaded}/{total_songs}")
            except Exception as e:
                console.insert(tk.END, f"An error occurred during download: {e}\n")

    if not cancel_requested:
        if item_type in ["playlist", "album"]:
            create_zip_from_folder(download_folder, zip_path)
            console.insert(tk.END, f"All tracks downloaded and zipped at: {zip_path}\n")
            completion_message.insert(tk.END, "Download complete.\n")
        else:
            console.insert(tk.END, "Track downloaded.\n")
            completion_message.insert(tk.END, "Download complete.\n")

    shutil.rmtree(download_folder)

    if os.path.exists(".cache"):
        os.remove(".cache")  # Clean up .cache file

    download_button.config(state=tk.NORMAL)  # Re-enable the download button
    cancel_button.config(state=tk.DISABLED)

def reset_ui():
    completion_message.delete(1.0, tk.END)  # Clear completion message
    progress_bar["value"] = 0  # Reset progress bar
    progress_label.config(text="0/0")  # Reset progress label
    console.delete(1.0, tk.END)  # Clear console output
    global cancel_requested
    cancel_requested = False  # Reset the cancellation flag for future downloads

def cancel_download():    
    # Cleanup logic for cancellation
    if os.path.exists(".cache"):
        os.remove(".cache")  # Remove .cache file if exists

    download_folder = os.path.join(os.getcwd(), "downloads")
    if os.path.exists(download_folder):
        shutil.rmtree(download_folder)  # Remove download folder

    zip_path = zip_location_entry.get().strip()
    if os.path.exists(zip_path):
        os.remove(zip_path)  # Remove zip file if it exists

    reset_ui()  # Reset UI
    global cancel_requested
    cancel_requested = True  # Signal all threads to stop

def on_save_codes_click():
    client_id = client_id_entry.get().strip()
    client_secret = client_secret_entry.get().strip()
    if client_id and client_secret:
        save_credentials(client_id, client_secret)
        console.insert(tk.END, "Spotify credentials saved successfully.\n")
    else:
        console.insert(tk.END, "Please enter both Client ID and Secret before saving.\n")

def on_load_codes_click():
    client_id, client_secret = load_credentials()
    if client_id and client_secret:
        client_id_entry.delete(0, tk.END)
        client_id_entry.insert(0, client_id)
        client_secret_entry.delete(0, tk.END)
        client_secret_entry.insert(0, client_secret)
        console.insert(tk.END, "Spotify credentials loaded successfully.\n")
        toggle_api_button_state()
    else:
        console.insert(tk.END, "No saved credentials found.\n")

def open_spotify_developer_page():
    webbrowser.open("https://developer.spotify.com/")

# Tkinter GUI setup
root = tk.Tk()
root.title("Spotify YouTube Downloader - MM-13")

root.configure(bg=BACKGROUND_COLOR)

# Title Label
title_label = tk.Label(root, text="SYTaDeL by MM-13", fg=TITLE_COLOR, bg=BACKGROUND_COLOR, font=("Helvetica", 22, "bold"))
title_label.grid(row=0, column=0, columnspan=4, pady=10)

# Configure grid weights for resizing
root.grid_rowconfigure(0, weight=0)  # Title row
for i in range(1, 8):  # Rows 1 to 7
    root.grid_rowconfigure(i, weight=1)  # Make these rows expandable
root.grid_columnconfigure(0, weight=1)  # Column for labels and input fields
root.grid_columnconfigure(1, weight=2)  # Column for entries and buttons (expandable)
root.grid_columnconfigure(2, weight=0)  # Column for browse button (fixed size)
root.grid_columnconfigure(3, weight=3)  # Column for console output (expandable)

# Entry fields for Spotify credentials
tk.Label(root, text="Spotify Client ID:", fg=TEXT_COLOR, bg=BACKGROUND_COLOR).grid(row=1, column=0, padx=5, sticky="w")
client_id_entry = tk.Entry(root, width=50, bg=ENTRY_BG_COLOR, fg=ENTRY_FG_COLOR, insertbackground=ENTRY_FG_COLOR)
client_id_entry.grid(row=1, column=1, padx=5, sticky="ew")

tk.Label(root, text="Spotify Client Secret:", fg=TEXT_COLOR, bg=BACKGROUND_COLOR).grid(row=2, column=0, padx=5, sticky="w")
client_secret_entry = tk.Entry(root, width=50, bg=ENTRY_BG_COLOR, fg=ENTRY_FG_COLOR, insertbackground=ENTRY_FG_COLOR, show="*")
client_secret_entry.grid(row=2, column=1, padx=5, sticky="ew")

# Button to open Spotify Developer page
get_api_button = tk.Button(root, text="Get/Make API", command=open_spotify_developer_page, bg=BUTTON_COLOR, fg=TEXT_COLOR)
get_api_button.grid(row=3, column=0, padx=5, sticky="w")

tk.Button(root, text="Save Codes", command=on_save_codes_click, bg=BUTTON_COLOR, fg=TEXT_COLOR).grid(row=3, column=1, padx=5, sticky="w")
tk.Button(root, text="Load Codes", command=on_load_codes_click, bg=BUTTON_COLOR, fg=TEXT_COLOR).grid(row=3, column=1, padx=5, sticky="e")

# Spotify URL entry
tk.Label(root, text="Enter Spotify Track/Playlist/Album URL:", fg=TEXT_COLOR, bg=BACKGROUND_COLOR).grid(row=4, column=0, padx=5, sticky="w")
entry = tk.Entry(root, width=50, bg=ENTRY_BG_COLOR, fg=ENTRY_FG_COLOR, insertbackground=ENTRY_FG_COLOR)
entry.grid(row=4, column=1, padx=5, sticky="ew")

# ZIP file location entry and browse button
tk.Label(root, text="Select ZIP file location:", fg=TEXT_COLOR, bg=BACKGROUND_COLOR).grid(row=5, column=0, padx=5, sticky="w")
zip_location_entry = tk.Entry(root, width=50, bg=ENTRY_BG_COLOR, fg=ENTRY_FG_COLOR, insertbackground=ENTRY_FG_COLOR)
zip_location_entry.grid(row=5, column=1, padx=5, sticky="ew")
tk.Button(root, text="Browse", command=select_zip_location, bg=BUTTON_COLOR, fg=TEXT_COLOR).grid(row=5, column=2, padx=5)

# Progress bar
progress_bar = ttk.Progressbar(root, length=300)
progress_bar.grid(row=6, column=1, sticky="ew", padx=5)
progress_label = tk.Label(root, text="0/0", fg=TEXT_COLOR, bg=BACKGROUND_COLOR)
progress_label.grid(row=6, column=2, sticky="w")

# Download and Cancel buttons
download_button = tk.Button(root, text="Download", command=on_download_click, bg=BUTTON_COLOR, fg=TEXT_COLOR)
download_button.grid(row=7, column=1, padx=5, pady=5, sticky="w")

cancel_button = tk.Button(root, text="Cancel", command=cancel_download, bg=BUTTON_COLOR, fg=TEXT_COLOR)
cancel_button.grid(row=7, column=1, padx=5, pady=5, sticky="e")

# Console output
console = scrolledtext.ScrolledText(root, width=60, height=20, bg=ENTRY_BG_COLOR, fg=ENTRY_FG_COLOR, wrap=tk.WORD)
console.grid(row=1, column=3, rowspan=6, pady=5, padx=10, sticky="nsew")

# Completion message
completion_message = tk.Text(root, width=60, height=2, bg=ENTRY_BG_COLOR, fg=ENTRY_FG_COLOR, wrap=tk.WORD)
completion_message.grid(row=7, column=3, pady=5, padx=10, sticky="ew")

# Disable the Get API button if IDs are present
def toggle_api_button_state():
    if client_id_entry.get().strip() == "" and client_secret_entry.get().strip() == "":
        get_api_button.config(state=tk.NORMAL)
    else:
        get_api_button.config(state=tk.DISABLED)

# Call toggle_api_button_state whenever an entry is changed
client_id_entry.bind("<KeyRelease>", lambda e: toggle_api_button_state())
client_secret_entry.bind("<KeyRelease>", lambda e: toggle_api_button_state())

# Initial check for loaded credentials
client_id, client_secret = load_credentials()
if client_id and client_secret:
    client_id_entry.insert(0, client_id)
    client_secret_entry.insert(0, client_secret)
    toggle_api_button_state()  # Update button state based on loaded credentials

root.mainloop()
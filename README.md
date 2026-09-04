# Novireon Discord Bot


Novireon is a highly capable and versatile Discord bot built with `discord.py`. It is designed to enhance your server experience with a rich set of features including advanced music playback, comprehensive event logging, dynamic image generation, and robust server utilities. 

By leveraging **MongoDB** for persistent data storage and a robust background worker architecture for thread-safe command execution, Novireon ensures a seamless, lag-free, and crash-resistant experience.

---

## Features

### Advanced Music Player System
- **Multi-Source Support:** Play music from **YouTube** (single videos, search queries, and playlists), **Spotify** (automatically searches YouTube equivalents), and **Monster Siren** (Arknights OST).
- **Thread-Safe Queue (New!)**: Built on a highly robust asynchronous background worker (`RequestManager`). Ensures that multiple playback requests, skips, or stops are queued sequentially per server, completely preventing race conditions and playback overlapping.
- **Persistent Data:** Queues and playback states are managed via a MongoDB database, allowing the bot to maintain states smoothly.
- **Interactive UI:** Playback controls (pause, resume, skip, stop) are presented via intuitive Discord UI buttons.
- **Live Progress Bar:** The playback embed features a real-time progress bar that dynamically updates.
- **DJ Role:** Configurable DJ roles to restrict music playback commands to authorized members.

### Comprehensive Server Logging
- **Event Tracking:** Keep track of important server events, logging them to designated channels.
- **Message Monitoring:** Logs message edits and deletions for auditing.
- **Member Activity:** Tracks nickname changes, role updates, avatar changes, and username modifications.
- **Highly Configurable:** Easily toggle logging globally, set specific channels for different logs (e.g., messages vs. member updates), or completely ignore noisy channels.

### Quote Image Generator (`/make_it_a_quote`)
- Generate aesthetic and stylish quote images from any context.
- Customizations include attributing the quote to a tagged member, custom text, and custom avatars.
- Powered by `Pillow` for high-quality rendering.

### Utility & Admin Commands
- **Ping & Stats:** Detailed `/ping` command providing real-time API latency, host machine CPU/Memory usage, and bot process diagnostics.
- **Channel Binding:** Bind the bot to specific text channels for music commands to keep your server tidy.

---

## Setup and Installation

### 1. Prerequisites
- **Python 3.10+** (up to 3.13 supported)
- **MongoDB** instance (Local or Atlas)
- **FFmpeg** (installed and added to your system PATH for music playback)
- **Deno** (`yt-dlp` now requires an external **JavaScript runtime**)

### 2. Clone the Repository
```bash
git clone https://github.com/rexkung1029/Novireon.git
cd Novireon
```

### 3. Install Dependencies
This project uses [uv](https://github.com/astral-sh/uv) for lightning-fast package management, as defined in `pyproject.toml`.

```bash
# Install uv if you haven't already
pip install uv

# Install dependencies using uv
uv pip install -r pyproject.toml
```
*(Alternatively, you can manually install the dependencies via `pip install -r requirements.txt` if available, or by checking `pyproject.toml` dependencies list).*

### 4. Configuration
Create a `.env` file in the root directory and configure the following variables:

```env
DISCORD=YOUR_DISCORD_BOT_TOKEN
MONGO_URI=YOUR_MONGODB_CONNECTION_STRING
```
Additionally, the bot uses `toml` files for configuration. You can find and tweak these files in the `Novireon/config/` directory (e.g., `Player_config.toml`, `MIQ_config.toml`).

### 5. Run the Bot
To start the bot, run the main entry point:
```bash
python start.py
```
The bot will initialize its background tasks, sync slash commands with Discord, and output a confirmation log once it is ready.

---

## Command Reference

All commands are implemented as modern **Slash Commands** (`/`).

### Player Commands
- `/player play <request>`: Search and play a song from YouTube, Spotify, or Monster Siren.
- `/player play_playlist <request> [max_results]`: Loads up to 25 songs from a playlist.
- `/player pause`: Pauses the current track.
- `/player resume`: Resumes the paused track.
- `/player skip`: Votes/Forces a skip to the next track.
- `/player stop`: Clears the queue, stops playback, and disconnects the bot.

### Player Setup (Admin/DJ)
- `/player_setup dj_role [role]`: Designates a role as the DJ. Only DJs can control playback if set.
- `/player_setup channel [channel]`: Binds music commands to a specific text channel.

### Server Logger (Admin)
- `/server_logger toggle`: Turns logging features on or off.
- `/server_logger list_settings`: Displays the current server logging configuration.
- `/server_logger set_log_channel <channel> <logging_type>`: Binds specific log events (e.g., messages, members) to a channel.
- `/server_logger ignore_channel <channel>`: Ignores a specific channel from being logged.

### Utilities
- `/ping`: Displays bot latency, CPU/RAM usage, and uptime.
- `/make_it_a_quote <quote_context> [author] [avatar]`: Turns a memorable phrase into a beautifully formatted image quote.

---

## Architecture Highlights
- **Request Manager (`queue_manager.py` / `request_manager.py`)**: A custom-built asynchronous queuing system that guarantees thread-safe, sequential processing of Discord audio operations. By decoupling network requests (like Spotify scraping) from state mutation, the bot remains incredibly responsive under heavy load.
- **MongoDB State Management (`mongo_crud.py`)**: Ensures robust persistent storage for server settings and active queues.

---

## Credits & Licenses
- **Fonts**: Uses *gensen-font* (Licensed under SIL Open Font License 1.1, Copyright © 2020 ButTaiwan).
- **Core Library**: Powered by [discord.py](https://github.com/Rapptz/discord.py).
- **gensen-font** - Licensed under SIL Open Font License 1.1. (Copyright © 2020 ButTaiwan)

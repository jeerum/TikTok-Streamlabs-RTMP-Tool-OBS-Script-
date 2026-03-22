# 🚀 TikTok Streamlabs OBS Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OBS Studio](https://img.shields.io/badge/OBS-Studio-blueviolet.svg)](https://obsproject.com/)
[![Streamlabs](https://img.shields.io/badge/Streamlabs-Compatible-green.svg)](https://streamlabs.com/)

Control your TikTok LIVE directly from OBS Studio using Streamlabs integration. This script automatically fetches your TikTok RTMP server and stream key—no manual API setup or TikTok web-login required.

---

## 🔥 Features

- 🔑 **Auto-Token Detection** – Automatically reads your Streamlabs session token (no manual login needed).
- 🎮 **Category Selection** – Search and select your game/category directly within the OBS script panel.
- 📡 **One-Click Start** – Generate a fresh RTMP address and Stream Key with a single button.
- 🛑 **Clean Session End** – Uses specific Stream IDs to properly close sessions and prevent "ghost" streams.
- 📋 **Auto-Copy** – Automatically copies the stream key to your clipboard for instant pasting.
- 💾 **Session Persistence** – Saves the last Stream ID and settings locally so you can resume or stop even after a restart.

---

## ⚙️ Requirements

1. **OBS Studio** (Latest version recommended).
2. **Streamlabs Desktop** installed on the same machine.
3. You must be **logged into Streamlabs Desktop**.
4. **TikTok** must be connected/linked within your Streamlabs account.

---

## 🧠 How It Works

This tool **does NOT** use the TikTok API directly. Instead, the script:
1. Locates your local **Streamlabs session token** from your computer's app data.
2. Interfaces with the **internal Streamlabs API**.
3. Requests a unique **RTMP + Stream Key** on your behalf.
4. Allows you to broadcast via OBS while TikTok "thinks" you are using Streamlabs.

---

## 🛠️ Installation

1. Download the `tiktok_streamlabs_obs.py` file.
2. Open **OBS Studio**.
3. Go to: `Tools` → `Scripts`.
4. Click the `+` icon and select the downloaded file.
5. The interface will appear on the right side of the Scripts window.

---

## 🎮 Usage Instructions

1. **Load Account:** Click the button to ensure your token is detected.
2. **Setup:** Enter your Stream Title and select a Category.
3. **Get Key:** Click **1. FETCH & COPY KEY**.
4. **Broadcast:** Paste the RTMP Server and Key into your OBS Stream settings (or **Aitum Vertical** settings).
5. **Go Live:** Start your stream in OBS.
6. **Stop:** When finished, click **2. END STREAM (Server)** to tell TikTok the session is over.

> [!IMPORTANT]
> **Security Warning:** Never share your stream key or log files. This script uses your local session data to keep your account safe.

---

## ❌ Troubleshooting

- **403/405 Errors?** → Usually means the previous session is still "hanging." Use the **END STREAM** button, wait 15 seconds, and try again.
- **Token Not Found?** → Ensure Streamlabs Desktop is open. If the error persists, log out and back into Streamlabs Desktop.
- **Key Invalid?** → TikTok keys expire quickly. Do not fetch the key until you are ready to start the stream.

---

## ❤️ Connect with Me

| Platform | Link |
| :--- | :--- |
| **TikTok** | [@jeerum](https://tiktok.com/@jeerum) |
| **Twitch** | [misterjaak](https://twitch.tv/misterjaak) |
| **YouTube** | [@Mr_Jaak80](https://youtube.com/@Mr_Jaak80) |

**Support the Project:** Give this repo a ⭐ and share it with fellow streamers!

---
*Created by Mr. Jaak. Not affiliated with TikTok or Streamlabs.*

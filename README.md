# AuctionSniper - V.2.0.0

> **Note:** This is an updated version of CecchinoDelleAste, adapted to work with the English version of the game. It is completely unrelated to Frosty's paid V2.


## 🚀 Changelog V.2:
* **New Features:** Added *Auto-Refresh*, *Max Bid*, and *Max Buyout* functions to maximize car discovery and avoid already-ended auctions.
* **Performance:** Optimized overall performance; the tool is out-of-the-box significantly faster and more responsive than the previous version.
* **Code & Customization:** Deep code cleanup and removal of hardcoded limits. You can now customize every parameter 100% to match your PC's hardware and network speed.
* **User Interface (UI):** Rebuilt from scratch to offer a more detailed and comprehensive experience compared to V.1.
* **Bugfixes:** Applied various structural improvements and resolved minor bugs.

## Main changes
* **Added multi-resolution support.** (tested and working: 720p, 1080p, 2K and 4K)
* **Added HDR support.**
* **Added support for the Italian language in the game.**
* **Added a Settings page in the overlay.**
* **Full translation of the tool into Italian.**
* **Custom user interface.**
* **Clean, simplified code for better optimization and maintenance.**
* **Fixed minor bugs.**

## Future changes
* Add support for custom resolutions and non-standard aspect ratios

---

# AuctionSniper for FH6

## Automatic sniper for the Forza Horizon 6 Auction House

Monitors the Auction House for the car you set, buys it instantly as soon as it appears, collects it and starts over in a loop. Configure the filters once and let it run. This tool has an instant-buy rate of around 10% and usually manages a snipe in under 5 minutes.

<img width="1655" height="792" alt="image-3" src="https://github.com/user-attachments/assets/61b58048-c3e6-4156-9510-0c2600aa7e9f" />

---

# Features

- Automatic search and instant buyout
- Skips already-sold listings to find a new one
- Automatically collects every car won
- Small always-on-top overlay with real-time stats
- F8 start/stop, F9 emergency stop
- Auto-stop after a set number of cars or minutes
- Smart page recognition to avoid accidental clicks on other screens

---

# Requirements and settings

- Windows 10 or 11
- Forza Horizon 6 on PC
- Resolution 4k/2k/1080p/720p - Fullscreen, unlocked frame rate - HUD size 100%
- Graphics preset Very Low
- Animated background (Visual accessibility) **Off**
- Game language set to **English**
- Wired Ethernet connection strongly recommended

<img width="1386" height="763" alt="image-4" src="https://github.com/user-attachments/assets/fd2bf173-259f-4458-938b-2267144ce3ab" />
<img width="1386" height="758" alt="image-5" src="https://github.com/user-attachments/assets/34f3fe88-9575-4ec5-aa6c-0c9e04a9964c" />

---

# Download

Download the latest version of **AuctionSniper.zip** from the [Releases page](https://github.com/d1ablo4L/AuctionSniper/releases) and extract it into any folder on your PC.

---

# Setup

## Step 1 – Open the Auction House

Launch Forza Horizon 6 and go to the Auction House on the festival site.

<img width="1916" height="971" alt="image-1" src="https://github.com/user-attachments/assets/2e4c412e-974e-4bf4-9d4d-bbc31fcd2432" />

---

## Step 2 – Configure the search

Open **Search Auctions** and set the filters:

- **Make** and **Model** of the car you want
- **Maximum buyout price** as a safety limit. The bot buys the first matching car without checking the price, so this is the most you can spend per car. Set it carefully.

Go back so the screen shows the **search configuration view**. That's where the bot expects to start.

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/7fac68c0-f89d-45ee-a10a-5133b02da681" />

---

## Step 3 – Start the sniper

Double-click **CecchinoDelleAste.exe**. A small overlay will appear in the top-right corner of the screen.

Go back to FH6, press **F8** or **Start**, and let it run.

To stop: press **F8** again, **F9** for emergency stop, or click **STOP** on the overlay.

<img width="1902" height="1062" alt="image-2" src="https://github.com/user-attachments/assets/ccdfba46-4c90-42de-bb79-fe26658bb262" />

---

# SmartScreen warning

Windows SmartScreen will show a warning because the exe is not digitally signed. To run it anyway:

1. Click **More info**
2. Click **Run anyway**

---

# Hotkeys

| Key | Action |
|---|---|
| **F8** | Start / stop |
| **F9** | Emergency stop |
| **STOP** button | Same as F8 |
| **✕** on the overlay | Close and exit |

---

# Important

> [!WARNING]
> - Automating the Auction House may violate the Forza Code of Conduct.
> - Results may vary depending on your PC and network setup.
> - You risk a warning, a suspension or a permanent ban.
> - Use it at your own risk.

---

# Notes

- The bot only works while FH6 is the active window. The overlay shows **Paused** if you switch to another window. Click the game again to resume.
- The overlay is hidden from screen captures, so you can leave it anywhere on screen.
- Drag the overlay by clicking and holding the title bar.
- You won't win every snipe. The bot is limited by FH6's menu animations and the auction server's response, like any other tool.
- If the servers are slow or overloaded, the bot may stop working correctly (a fix is coming soon).

---

# Troubleshooting

**The overlay shows "Paused"** – FH6 is not the active window. Click the game.

**F8 does nothing** – another app on your PC may be intercepting the F8 key. Close it, or change the hotkey in `config.json`.

**The bot gets lost on a screen and freezes** – restart FH6 and the bot. Make sure the graphics preset is **Very Low** and the resolution is **1920 x 1080**.

**When reporting bot-related issues** – include the Sniper.log file so I can analyze it. If the problem persists, [open an issue](https://github.com/d1ablo4L/CecchinoDelleAste/issues) or contact me on Discord "d1ablo4l".

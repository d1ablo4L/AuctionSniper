# 𖦏 AuctionSniper - V.2.1

> **Note:** This is an updated and improved version of Frosty's FH6 Auction Sniper. It is completely unrelated to Frosty's paid V2.

---

## 📣 Changelog V.2.1

### 🔄 New Features
* Added **Auto Refresh**, **Max Bid**, and **Max Buyout** to find more cars and prevent appears already ended auctions.
* Added a **Diagnostic Mode** for matches to avoid blindly modifying thresholds when using different settings (like HDR or custom templates).
* Embedded templates and new overlay fonts directly into the executable.

### 🖥️ UI & Multi-Language Support
* Rebuilt the interface from scratch to offer a much more detailed, intuitive, and comprehensive experience.
* Added a **Customization Page** in the settings: you can now change the overlay language, select your in-game language, live resize the overlay, and change colors.
* Four languages currently available: **English, Italian, Spanish and German**.

### ⚡ Performance & Detection
* Optimized overall performance; the tool is now significantly faster compared to V1.
* Improved **"SOLD" stamp detection**: the tool will now successfully skip already sold cars without attempting to buy them.

### ⚙️ Total Customization
* Extensive code cleanup and removal of hardcoded limits. Every single parameter is now 100% customizable to perfectly match your PC's hardware and network latency.
* Reworked and improved the **Keybinds** functionality.

### 🛠️ Fixes & Improvements
* Various code improvements and general bug fixes.

---

# AuctionSniper for FH6

## Automatic sniper for the Forza Horizon 6 Auction House

Monitors the Auction House for the car you set, buys it instantly as soon as it appears, collects it and starts over in a loop. Configure the filters once and let it run. This tool has an instant-buy rate of around 10% and usually manages a snipe in under 5 minutes.

---

# Features

- Automatic search and instant buyout
- **Auto Refresh**, **Max Bid**, and **Max Buyout** controls to find more cars and avoid already-ended auctions
- Improved **"SOLD" stamp detection** to skip already-sold listings and find a new one
- **Diagnostic Mode** to fine-tune match thresholds for HDR or custom templates
- Automatically collects every car won
- Small always-on-top overlay with real-time stats
- **Customization Page**: overlay language, in-game language, live overlay resize, and custom colors
- Multi-language: **English, Italian, Spanish and German**
- F8 start/stop, F9 emergency stop, reworked keybinds
- Auto-stop after a set number of cars or minutes
- Smart page recognition to avoid accidental clicks on other screens

---

# Requirements and settings

- Windows **10 or 11**
- Resolution **4k/2k/1080p/720p**
- Frame rate **Unlocked**
- UI size **100%**
- Graphics preset **Very Low**
- Moving background (Visual accessibility) **Off**
- Wired Ethernet connection strongly recommended

<img width="1372" height="767" alt="20260623205539_1" src="https://github.com/user-attachments/assets/195fbb4c-79bc-4944-8405-00a35d4127e8" />
<img width="1367" height="760" alt="20260623205549_1" src="https://github.com/user-attachments/assets/f6bd8f5e-8122-4190-954d-9581dd5c31cc" />
<img width="1369" height="759" alt="20260623205555_1" src="https://github.com/user-attachments/assets/d15b2066-a9af-40b3-b8ab-4faf73f69bc4" />


---

# Download

Download the latest version of **AuctionSniper.zip** from the [Releases page](https://github.com/d1ablo4L/AuctionSniper/releases) and extract it into any folder on your PC.

---

# How to use

## Step 1 – Open the Auction House

Launch Forza Horizon 6 and go to the Auction House on the festival site.

<img width="1916" height="971" alt="image-1" src="https://github.com/user-attachments/assets/2e4c412e-974e-4bf4-9d4d-bbc31fcd2432" />

---

## Step 2 – Configure the search

Open **Search Auctions** and set the filters:

- **Make** and **Model** of the car you want
- **Maximum buyout price** as a safety limit. The bot buys the first matching car without checking the price, so this is the most you can spend per car. Set it carefully.

Go back so the screen shows the main **Auction House Screen**. That's where the bot expects to start.

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/7fac68c0-f89d-45ee-a10a-5133b02da681" />

---

## Step 3 – Start the sniper

Right-click **AuctionSniper.exe** and **run as administrator**. A small overlay will appear in the top-right corner of the screen.

Go back to FH6, press **F8** or **Start**, and let it run.

To stop: press **F8** again, **F9** for emergency stop, or click **STOP** on the overlay.

<img width="1916" height="971" alt="597772710-2e4c412e-974e-4bf4-9d4d-bbc31fcd2432" src="https://github.com/user-attachments/assets/66f7984f-c3a2-46a5-8f8d-cda4d8bd48b4" />

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

**F8 does nothing** – another app on your PC may be intercepting the F8 key. Close it, or change the hotkey in the settings.

**The bot gets lost on a screen and freezes** – restart FH6 and the bot. Make sure the graphics preset is **Very Low** and the resolution matches one of the supported options. Use **Diagnostic Mode** to check match thresholds if you run HDR or custom templates.

**When reporting bot-related issues** – include the Sniper.log file so I can analyze it. If the problem persists, [open an issue](https://github.com/d1ablo4L/AuctionSniper/issues) or contact me on Discord "d1ablo4l".

# Deploy the bot to an always-on host (free, 24/7)

This runs your Sunnah bot in the cloud so reminders arrive even when your PC is
off. Recommended free path: **Render** (no credit card) + **UptimeRobot** (keeps
the free instance awake). Takes ~15 minutes once.

There are no secrets in the repo — your token and chat id are set as
**environment variables** on the host. `config.json` is git-ignored.

---

## Step 0 — Get your CHAT_ID (one minute)

The cloud host needs to know which Telegram chat to message.

1. Make sure the bot is running locally (double-click `run-bot.bat`).
2. In Telegram, open your bot, press **START**, send `/city Your City, Country`.
3. Open `state.json` in this folder — copy the number next to `"chat_id"`.
   (Or visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
   and copy `chat.id`.)

Keep that number handy — you'll paste it as `CHAT_ID` below.

---

## Step 1 — Put this folder on GitHub

1. Create a free account at <https://github.com> if you don't have one.
2. New repository → name it e.g. `sunnah-bot` → **Private** → Create.
3. Upload the files from **this `bot/` folder** (you can drag-and-drop on the
   GitHub web "Add file → Upload files" page). Upload:
   `sunnah_bot.py`, `requirements.txt`, `render.yaml`, `Dockerfile`, `.gitignore`.
   **Do NOT upload `config.json` or `state.json`** (they hold your secrets — the
   `.gitignore` already excludes them if you use git from the command line).

---

## Step 2 — Deploy on Render (free)

1. Sign up at <https://render.com> (you can log in with your GitHub account — no card).
2. Click **New +** → **Blueprint** → connect and pick your `sunnah-bot` repo.
   Render reads `render.yaml` and sets up a free web service automatically.
3. When prompted, fill the secret env vars:
   - `BOT_TOKEN` → your @BotFather token
   - `CHAT_ID` → the number from Step 0
   - `CITY` → e.g. `Cairo`
   - `COUNTRY` → e.g. `Egypt`
   (`MORNING_TIME`, `EVENING_TIME`, `DAILY_TIP_TIME` already have defaults.)
4. Click **Apply / Deploy**. After a minute the logs show
   `Bot @SunnahCompanionBot is live` and `Health server listening on :10000`.
5. Copy your service URL — it looks like `https://sunnah-bot-xxxx.onrender.com`.

Send `/times` to your bot to confirm it answers from the cloud. 🎉

---

## Step 3 — Keep it awake with UptimeRobot (free)

Render's free plan sleeps a service after ~15 min of no web traffic. A free
pinger keeps it awake so reminders never stop.

1. Sign up at <https://uptimerobot.com> (free, no card).
2. **Add New Monitor** → Type: **HTTP(s)** → URL: your Render URL from Step 2 →
   Monitoring interval: **5 minutes** → Create.

That's it — the bot now runs 24/7 for free. You can turn off your PC.

---

## Updating later

Change `sunnah_bot.py`, push to GitHub → Render redeploys automatically.
Change a time/city → just edit the env var in the Render dashboard and redeploy.

---

## Alternative: a truly-free always-on VM (Oracle Cloud)

If you'd rather own a real server (no sleep, no pinger), Oracle Cloud's
**Always Free** ARM VM runs this forever for $0 (needs a card for identity
verification, not charged). Heavier setup:

1. Create an Always Free **VM.Standard.A1.Flex** instance (Ubuntu).
2. SSH in, install Python: `sudo apt update && sudo apt install -y python3-pip`.
3. Copy `sunnah_bot.py` + `requirements.txt`, `pip3 install -r requirements.txt`.
4. Set env vars and run under **systemd** so it restarts automatically:
   ```ini
   # /etc/systemd/system/sunnah-bot.service
   [Unit]
   Description=Sunnah Companion bot
   After=network-online.target
   [Service]
   Environment=BOT_TOKEN=xxxx
   Environment=CHAT_ID=12345
   Environment=CITY=Cairo
   Environment=COUNTRY=Egypt
   ExecStart=/usr/bin/python3 /home/ubuntu/sunnah_bot.py
   Restart=always
   [Install]
   WantedBy=multi-user.target
   ```
   Then: `sudo systemctl enable --now sunnah-bot`.

No `PORT` is set here, so the health server stays off and no pinger is needed.

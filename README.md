# Sunnah Companion — Telegram bot

Reliable push reminders that reach your phone **even when nothing is open**:
prayer times, morning & evening adhkar, and a daily Sunnah tip.

## One-time setup (about 5 minutes)

1. **Create the bot**
   - Open Telegram, search for **@BotFather**, press Start.
   - Send `/newbot`, choose a name and a username (must end in `bot`).
   - BotFather replies with a **token** like `123456:ABC-DEF...`. Copy it.

2. **Add the token**
   - In this `bot` folder, copy `config.example.json` to `config.json`.
   - Open `config.json` and paste your token into `"bot_token"`.
   - (Optional) set `"city"` and `"country"` now, or do it later with `/city`.

3. **Run it**
   - **Windows:** double-click **`run-bot.bat`** (it installs `requests` and starts the bot).
   - **Or any OS:**
     ```
     pip install requests
     python sunnah_bot.py
     ```

4. **Activate reminders**
   - Open your new bot in Telegram and press **START**.
   - Send your city: `/city Cairo, Egypt`
   - Done — you'll now get reminders. Test with `/times`, `/today`, `/dua`.

## Commands

| Command | What it does |
|---|---|
| `/start` | Register your phone for reminders |
| `/city <City, Country>` | Set location for prayer times |
| `/times` | Today's prayer times |
| `/today` | The full Sunnah checklist |
| `/hadith` | A hadith from Nawawi's Forty |
| `/friday` | The Jumu'ah Sunnah acts |
| `/fasting` | Recommended fasting days (incl. today's occasion) |
| `/dua` | A prophetic supplication |
| `/tip` | A random Sunnah tip |
| `/language` | Switch between العربية and English (or `/language ar`) |
| `/stop` / `/resume` | Pause / resume reminders |
| `/help` | List commands |

The bot speaks **Arabic or English** — every reminder, hadith, and command reply is
translated. Switch anytime with `/language`, or set the default with the `LANG` env var
(`en` / `ar`).

### Automatic reminders

- **Every prayer time** + **morning/evening adhkar** + a **daily Sunnah tip**
- **Hadith of the day** (08:00) — cycles through Nawawi's Forty
- **Jumu'ah pack** every Friday (09:30) — Al-Kahf, ghusl, salawat, last-hour du'a
- **Last hour before Maghrib on Friday** — du'a reminder
- **Fasting nudges** (evening) — Mon/Thu, the 3 White Days, Ashura, Arafah, six of Shawwal

## Keeping it running 24/7

The bot only sends reminders while the script is running. Options:

- **Your PC** — easiest. Reminders arrive whenever your PC is on. (Add `run-bot.bat`
  to Windows Startup so it launches with your computer:
  press `Win+R`, type `shell:startup`, drop a shortcut to `run-bot.bat` there.)
- **A Raspberry Pi** at home — runs silently 24/7 for ~nothing.
- **A free/cheap cloud host** (Railway, Render, Fly.io, a small VPS) — always on,
  independent of your PC. Just run `python sunnah_bot.py` there with your `config.json`.

## Notes

- `config.json` and `state.json` hold your token and chat id — **don't share them.**
- Prayer times come from the free [Aladhan API](https://aladhan.com/prayer-times-api)
  (calculation method 2 = ISNA; change `&method=` in the code for another method).
- The reminders are aids to worship — always learn the details of each act of the
  Sunnah from the Qur'an, authentic hadith, and trustworthy scholars.

## Licence

Copyright © 2026 Ayman Ahmed. All rights reserved.

This code is public so it can be **read and evaluated**, not reused. You're
welcome to look through it and to quote it with attribution; copying, modifying,
redistributing or building on it needs written permission. See [LICENSE](LICENSE).

The supplications and hadith are well-known texts of the Islamic tradition and
are not claimed as original work — the selection, arrangement and surrounding
software are.

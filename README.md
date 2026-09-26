# Sunnah Companion — Telegram bot

Reliable push reminders that reach your phone **even when nothing is open**:
prayer times, morning & evening adhkar, and a daily Sunnah tip.

**Anyone can use it.** Share your bot's link (`t.me/<your_bot_username>`) —
everyone who presses START gets their own location, language, calculation
method and reminders, in their own time zone.

## One-time setup (about 5 minutes)

1. **Create the bot**
   - Open Telegram, search for **@BotFather**, press Start.
   - Send `/newbot`, choose a name and a username (must end in `bot`).
   - BotFather replies with a **token** like `123456:ABC-DEF...`. Copy it.

2. **Add the token**
   - In this `bot` folder, copy `config.example.json` to `config.json`.
   - Open `config.json` and paste your token into `"bot_token"`.

3. **Run it**
   - **Windows:** double-click **`run-bot.bat`** (it installs the requirements and starts the bot).
   - **Or any OS:**
     ```
     pip install -r requirements.txt
     python sunnah_bot.py
     ```

4. **Activate reminders**
   - Open your new bot in Telegram and press **START**.
   - Send `/location` and tap **📍 Send my location** (most accurate), or type your
     city: `/city Cairo, Egypt`
   - Done — you'll now get reminders. Test with `/times`, `/today`, `/dua`.

## Commands

| Command | What it does |
|---|---|
| `/start` | Sign up for reminders |
| `/location` | Share your phone's location: the most accurate prayer times |
| `/city <City, Country>` | Set location by name instead |
| `/times` | Today's prayer times (shows the method used) |
| `/method [n]` | See or choose the calculation method (`/method 0` = automatic) |
| `/asr standard` / `/asr hanafi` | How Asr is calculated |
| `/adjust <prayer> <±min>` | Match your mosque's timetable, e.g. `/adjust maghrib +3` |
| `/today` | The full Sunnah checklist |
| `/hadith` | A hadith from Nawawi's Forty |
| `/friday` | The Jumu'ah Sunnah acts |
| `/fasting` | Recommended fasting days (incl. today's occasion) |
| `/dua` | A prophetic supplication |
| `/tip` | A random Sunnah tip |
| `/language` | Switch between العربية and English (or `/language ar`) |
| `/stop` / `/resume` | Pause / resume reminders |
| `/forget` | Delete your settings and location, and stop reminders |
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
- **A free/cheap cloud host** (Render, Railway, Fly.io, a small VPS) — always on,
  independent of your PC. See [DEPLOY.md](DEPLOY.md).

### Did the reminders go out?

When the bot runs with a `PORT` set, it answers `GET /health` with JSON: a
seven-day ledger of how many reminders were **sent**, **failed**, sent **twice**
or **missed**, how late they were, and a pass/fail verdict for yesterday. It is
counters only — no chat ids, no cities, no per-person timeline — so it says
whether the reminders worked without recording who got what.

```bash
curl -s "$BOT_URL/health?token=$HEALTH_TOKEN" | jq '.verdict'
```

```json
{ "date": "2026-09-25", "pass": true, "fail": [], "warn": [],
  "totals": { "sent": 214, "failed": 0, "dupe": 0, "missed": 0, "late_max_s": 41,
              "prayers_unavailable": 0, "gaps": 0, "gap_max_s": 0 } }
```

`.verdict.pass` is the whole check: `true` → say so and stop. `false` → read
`.verdict.fail`, which is one of

| Failure | What it means |
| --- | --- |
| `N reminder(s) never went out` | a send window (3 min after the scheduled minute) closed with nothing delivered |
| `N reminder(s) were sent twice` | the once-a-day guard broke — a user got the same reminder again |
| `no reminder was sent` / `no dispatch recorded at all` | the scheduler did not run that day |
| `the scheduler was silent for Ns` | the process stopped or slept for over 5 minutes, so anything due in that hole was skipped |
| `a reminder was Ns late` | the send window itself changed; the code no longer matches this check |

`.verdict.warn` is not a failure: a send that Telegram refused once and the next
tick delivered, or a prayer-times fetch that didn't answer. Worth a line in the
status comment, not a task. `.dispatch` has the same counters per reminder key
(`morning`, `salah_Fajr`, …) when you need to know *which* reminder broke.

Notes for whoever reads this daily:

- Days are **UTC**, because users are in many timezones — yesterday's row is
  final at 00:00 UTC, so check any time after that.
- The verdict covers **the Telegram bot only**. The PWA and Android app schedule
  their reminders on the device and report nothing back, by design; there is no
  data to check and this endpoint does not invent any.
- The first verdict is meaningful from the second full UTC day after a deploy —
  before that, yesterday has no row and it reports `no dispatch recorded at all`.
- Set `HEALTH_TOKEN` on a public host. Without it `/health` is readable by
  anyone who guesses the path (it still holds no personal data). `/` keeps
  answering plain text either way, so an uptime pinger needs no change.

### Where users are saved

Everyone's settings are saved in `state.json` next to the script (or in
`DATA_DIR`). Many free cloud hosts, including Render, **wipe the disk on every
deploy**, which would sign everyone out. On those hosts set `DATABASE_URL` to a
free Postgres database (e.g. [Supabase](https://supabase.com) or
[Neon](https://neon.tech)) and the bot keeps its data there instead.

## Notes

- `config.json` holds your bot token and `state.json` holds users' settings —
  **don't share or commit them** (both are git-ignored).
- **Privacy:** each person only ever sees their own settings. Shared locations
  are stored rounded to about 1 km, nothing else about users is kept, and
  `/forget` deletes a person's data. Logs never include users' cities, locations
  or messages. The dispatch ledger behind `/health` counts reminders, not people:
  it holds no chat ids and keeps seven days.
- Reminders use **each person's local time**, detected automatically from the
  prayer-times API — so a cloud host running on UTC still reminds everyone on time.
- **Your own settings on a host (optional):** set `CHAT_ID` (your Telegram chat id)
  plus any of `CITY`, `COUNTRY`, `LATITUDE`, `LONGITUDE`, `PRAYER_METHOD`,
  `ASR_SCHOOL` (`standard` / `hanafi`) and `TIMEZONE`, and they're re-applied on
  every start, even if the disk was wiped.
- Run the tests with `python test_sunnah_bot.py`.
- Prayer times come from the free [Aladhan API](https://aladhan.com/prayer-times-api).
  **For the most accurate times:**
  1. Share your location with `/location` (exact coordinates beat a city name).
  2. The bot picks the authority your country's mosques follow (e.g. Moonsighting
     Committee for the UK, Umm al-Qura for Saudi Arabia, Egyptian Authority for
     Egypt, Karachi + Hanafi Asr for Pakistan/India). Change it with `/method`.
  3. Choose `/asr hanafi` if you follow the Hanafi madhab.
  4. Compare with your local mosque's timetable and fine-tune with `/adjust`
     (mosques often add a few minutes, e.g. to Maghrib or Dhuhr).
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

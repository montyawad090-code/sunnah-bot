#!/usr/bin/env python3
"""
Sunnah Companion — Telegram reminder bot
----------------------------------------
Sends you reminders to follow the Sunnah of the Prophet Muhammad (peace be upon him):
prayer times, morning/evening adhkar, and a daily Sunnah tip — even when nothing is open.

Dependencies: `requests` and `tzdata`  (pip install -r requirements.txt)

Setup (once):
  1. On Telegram, message @BotFather -> /newbot -> copy the token.
  2. Put the token in config.json (copy config.example.json).
  3. Run this file:  python sunnah_bot.py
  4. Open your new bot in Telegram and press START. The bot saves your chat id.
  5. Set your city with:  /city Cairo, Egypt
  6. Leave it running (PC, a Raspberry Pi, or a free host). See README.md.

Commands inside Telegram:
  /start   register for reminders
  /city <City, Country>   set location for prayer times
  /times   today's prayer times
  /today   today's Sunnah checklist
  /hadith  a hadith from Nawawi's Forty
  /friday  the Jumu'ah Sunnah acts
  /fasting recommended fasting days
  /language  switch العربية / English
  /dua     a prophetic supplication
  /tip     a random Sunnah tip
  /stop    pause reminders     /resume  resume them
  /help    show commands
"""

import json, os, time, random, datetime, threading
from zoneinfo import ZoneInfo
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
STATE_PATH = os.path.join(HERE, "state.json")
API = "https://api.telegram.org/bot{token}/{method}"

# ----------------------------------------------------------------------------
# Content (well-known acts from the Sunnah; references are general pointers)
# ----------------------------------------------------------------------------
# (en_label, arabic, en_meaning, ar_label)
DUAS = [
    ("Morning", "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ",
     "We have entered the morning and the dominion belongs to Allah.", "أذكار الصباح"),
    ("Before eating", "بِسْمِ اللَّهِ", "In the name of Allah.", "قبل الطعام"),
    ("After eating", "الْحَمْدُ لِلَّهِ الَّذِي أَطْعَمَنِي هَذَا",
     "Praise be to Allah who fed me this.", "بعد الطعام"),
    ("Leaving home", "بِسْمِ اللَّهِ تَوَكَّلْتُ عَلَى اللَّهِ",
     "In the name of Allah, I place my trust in Allah.", "الخروج من البيت"),
    ("Distress", "لَا إِلَٰهَ إِلَّا اللَّهُ الْعَظِيمُ الْحَلِيمُ",
     "There is no god but Allah, the Magnificent, the Forbearing.", "عند الكرب"),
    ("Seeking forgiveness", "أَسْتَغْفِرُ اللَّهَ وَأَتُوبُ إِلَيْهِ",
     "I seek Allah's forgiveness and turn to Him in repentance.", "الاستغفار"),
    ("Salawat", "اللَّهُمَّ صَلِّ وَسَلِّمْ عَلَى نَبِيِّنَا مُحَمَّدٍ",
     "O Allah, send blessings and peace upon our Prophet Muhammad.", "الصلاة على النبي ﷺ"),
    ("Before sleep", "بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا",
     "In Your name O Allah, I die and I live.", "قبل النوم"),
]

# (english, arabic)
TIPS = [
    ("Use the miswak / brush your teeth — the Prophet ﷺ loved it before every prayer. (Bukhari)",
     "استعمل السواك — كان النبي ﷺ يحبه عند كل صلاة. (البخاري)"),
    ("Smile at someone today — your smile in your brother's face is charity. (Tirmidhi)",
     "ابتسم لأحدهم اليوم — تبسّمك في وجه أخيك صدقة. (الترمذي)"),
    ("Eat with your right hand and from what is nearest to you. (Bukhari & Muslim)",
     "كُل بيمينك ومما يليك. (البخاري ومسلم)"),
    ("Say Bismillah before you begin, and Alhamdulillah after you finish.",
     "قل بسم الله قبل أن تبدأ، والحمد لله بعد أن تنتهي."),
    ("Pray the 12 Sunnah rak'ah and a house is built for you in Paradise. (Muslim)",
     "صلِّ ١٢ ركعة من السنن يُبنَ لك بها بيت في الجنة. (مسلم)"),
    ("Send salawat on the Prophet ﷺ — for each one, Allah sends ten blessings on you. (Muslim)",
     "أكثر من الصلاة على النبي ﷺ — بكل واحدة يصلي الله عليك عشرًا. (مسلم)"),
    ("Spread salam to those you know and those you don't. (Bukhari)",
     "أفشِ السلام على من عرفت ومن لم تعرف. (البخاري)"),
    ("Control yourself when angry — that is true strength. (Bukhari)",
     "املك نفسك عند الغضب — فتلك هي القوة الحقيقية. (البخاري)"),
    ("Sleep on your right side after making wudu, as the Prophet ﷺ did. (Bukhari)",
     "نَم على شقك الأيمن بعد الوضوء، كما كان النبي ﷺ يفعل. (البخاري)"),
    ("Give in charity today, even half a date. (Bukhari)",
     "تصدّق اليوم ولو بشقّ تمرة. (البخاري)"),
    ("The most beloved deeds to Allah are the consistent ones, even if small. (Bukhari)",
     "أحب الأعمال إلى الله أدومها وإن قلّ. (البخاري)"),
    ("Read some Qur'an today — the best of you learn it and teach it. (Bukhari)",
     "اقرأ وردًا من القرآن اليوم — خيركم من تعلّمه وعلّمه. (البخاري)"),
    ("Honour your parents — Allah's pleasure is in the parent's pleasure. (Tirmidhi)",
     "برّ والديك — رضا الرب في رضا الوالد. (الترمذي)"),
    ("Seek forgiveness often — the Prophet ﷺ did so 70+ times a day. (Bukhari)",
     "أكثر من الاستغفار — كان النبي ﷺ يستغفر أكثر من ٧٠ مرة في اليوم. (البخاري)"),
    ("Pray two rak'ah of Duha (forenoon) — charity for every joint in your body. (Muslim)",
     "صلِّ ركعتي الضحى — صدقة عن كل مفصل في جسدك. (مسلم)"),
]

# (number, english, arabic, ref) — from the Forty Hadith of Imam an-Nawawi.
HADITHS = [
    ("1", "Actions are but by intentions, and every person will have only what they intended.", "إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى.", "Bukhari & Muslim"),
    ("2", "Islam is built on five: testifying there is no god but Allah and Muhammad is His Messenger, establishing prayer, giving zakat, fasting Ramadan, and Hajj.", "بُني الإسلام على خمس: شهادة أن لا إله إلا الله وأن محمدًا رسول الله، وإقام الصلاة، وإيتاء الزكاة، وصوم رمضان، وحج البيت.", "Bukhari & Muslim"),
    ("3", "Worship Allah as though you see Him, for though you do not see Him, He surely sees you. (Ihsan)", "أن تعبد الله كأنك تراه، فإن لم تكن تراه فإنه يراك. (الإحسان)", "Muslim"),
    ("4", "Whoever believes in Allah and the Last Day, let him speak good or remain silent.", "من كان يؤمن بالله واليوم الآخر فليقل خيرًا أو ليصمت.", "Bukhari & Muslim"),
    ("5", "None of you truly believes until he loves for his brother what he loves for himself.", "لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه.", "Bukhari & Muslim"),
    ("6", "Part of the perfection of a person's Islam is his leaving alone that which does not concern him.", "من حُسن إسلام المرء تركه ما لا يعنيه.", "Tirmidhi"),
    ("7", "The lawful is clear and the unlawful is clear, and between them are doubtful matters. Whoever avoids them protects his religion.", "الحلال بيّن والحرام بيّن، وبينهما أمور مشتبهات، فمن اتقى الشبهات استبرأ لدينه.", "Bukhari & Muslim"),
    ("8", "Allah is Pure and accepts only what is pure.", "إن الله طيّب لا يقبل إلا طيّبًا.", "Muslim"),
    ("9", "What I have forbidden you, avoid; what I have commanded you, do as much of it as you can.", "ما نهيتكم عنه فاجتنبوه، وما أمرتكم به فأتوا منه ما استطعتم.", "Bukhari & Muslim"),
    ("10", "Be mindful of Allah and He will protect you. Be mindful of Allah and you will find Him before you.", "احفظ الله يحفظك، احفظ الله تجده تجاهك.", "Tirmidhi"),
    ("11", "Leave what makes you doubt for what does not make you doubt.", "دع ما يريبك إلى ما لا يريبك.", "Tirmidhi"),
    ("12", "Allah does not look at your forms or wealth, but He looks at your hearts and your deeds.", "إن الله لا ينظر إلى صوركم وأموالكم، ولكن ينظر إلى قلوبكم وأعمالكم.", "Muslim"),
    ("13", "The strong believer is better and more beloved to Allah than the weak believer. Strive for what benefits you, seek Allah's help, and do not give up.", "المؤمن القوي خير وأحب إلى الله من المؤمن الضعيف. احرص على ما ينفعك واستعن بالله ولا تعجز.", "Muslim"),
    ("14", "Do not be angry.", "لا تغضب.", "Bukhari"),
    ("15", "Allah has prescribed excellence (ihsan) in all things.", "إن الله كتب الإحسان على كل شيء.", "Muslim"),
    ("16", "Fear Allah wherever you are; follow a bad deed with a good one to wipe it out; and treat people with good character.", "اتق الله حيثما كنت، وأتبع السيئة الحسنة تمحها، وخالق الناس بخلق حسن.", "Tirmidhi"),
    ("17", "Whoever removes a worldly hardship from a believer, Allah will remove from him a hardship on the Day of Resurrection.", "من نفّس عن مؤمن كربة من كرب الدنيا نفّس الله عنه كربة من كرب يوم القيامة.", "Muslim"),
    ("18", "The most beloved deeds to Allah are the most consistent, even if they are small.", "أحب الأعمال إلى الله أدومها وإن قلّ.", "Bukhari & Muslim"),
    ("19", "Make things easy and do not make them difficult; give glad tidings and do not repel people.", "يسّروا ولا تعسّروا، وبشّروا ولا تنفّروا.", "Bukhari & Muslim"),
    ("20", "Richness is not having many possessions; rather, true richness is the richness of the soul.", "ليس الغنى عن كثرة العَرَض، ولكن الغنى غنى النفس.", "Bukhari & Muslim"),
]

# Aladhan calculation methods (https://aladhan.com/calculation-methods).
METHODS = {
    1: "University of Islamic Sciences, Karachi", 2: "ISNA (North America)",
    3: "Muslim World League", 4: "Umm al-Qura, Makkah", 5: "Egyptian General Authority of Survey",
    7: "University of Tehran", 8: "Gulf Region", 9: "Kuwait", 10: "Qatar",
    11: "Majlis Ugama Islam Singapura", 12: "Union des Organisations Islamiques de France",
    13: "Diyanet, Turkey", 14: "Spiritual Administration of Muslims of Russia",
    15: "Moonsighting Committee Worldwide", 16: "Dubai", 17: "JAKIM, Malaysia",
    18: "Tunisia", 19: "Algeria", 20: "KEMENAG, Indonesia", 21: "Morocco",
    22: "Comunidade Islamica de Lisboa", 23: "Ministry of Awqaf, Jordan",
}

# The authority most mosques in each country follow. Countries not listed are
# left to Aladhan, which picks the closest authority to the location.
_COUNTRY_METHOD = {
    15: ["united kingdom", "uk", "england", "scotland", "wales", "northern ireland", "great britain", "britain", "ireland"],
    2: ["united states", "united states of america", "usa", "us", "america", "canada"],
    5: ["egypt", "sudan", "libya", "syria", "lebanon", "iraq", "palestine"],
    4: ["saudi arabia", "ksa", "yemen"],
    16: ["united arab emirates", "uae"],
    10: ["qatar"], 9: ["kuwait"], 8: ["bahrain", "oman"],
    1: ["pakistan", "india", "bangladesh", "afghanistan"],
    13: ["turkey", "türkiye", "turkiye"], 7: ["iran"], 17: ["malaysia"], 20: ["indonesia"],
    11: ["singapore"], 12: ["france"], 14: ["russia"], 18: ["tunisia"], 19: ["algeria"],
    21: ["morocco"], 22: ["portugal"], 23: ["jordan"],
}
METHOD_BY_COUNTRY = {c: m for m, cs in _COUNTRY_METHOD.items() for c in cs}
# Where the Hanafi Asr (shadow = twice the object's length) is the local norm.
HANAFI_COUNTRIES = {"pakistan", "india", "bangladesh", "afghanistan", "turkey", "türkiye", "turkiye"}

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

PRAYER_AR = {"Fajr": "الفجر", "Sunrise": "الشروق", "Dhuhr": "الظهر",
             "Asr": "العصر", "Maghrib": "المغرب", "Isha": "العشاء"}

# Fasting occasions of the Hijri month — returns phrases in the current language.
def fasting_special(hijri_day, hijri_month):
    msgs = []
    if hijri_day in (13, 14, 15):
        msgs.append(L("🤍 a *White Day* (the " + str(hijri_day) + "th) — “fasting three days each month is like fasting the whole month.” (Bukhari)",
                      "🤍 *يوم بيض* (" + str(hijri_day) + ") — «صيام ثلاثة أيام من كل شهر كصيام الدهر». (البخاري)"))
    if hijri_month == 1 and hijri_day in (9, 10):
        msgs.append(L("🌙 *Ashura* (Muharram " + str(hijri_day) + ") — fasting the 10th (with the 9th) expiates the past year's sins. (Muslim)",
                      "🌙 *عاشوراء* (محرم " + str(hijri_day) + ") — صيام العاشر (مع التاسع) يكفّر السنة الماضية. (مسلم)"))
    if hijri_month == 12 and hijri_day == 9:
        msgs.append(L("⛰️ the *Day of Arafah* — fasting it expiates the sins of two years. (Muslim) (For those not on Hajj.)",
                      "⛰️ *يوم عرفة* — صيامه يكفّر سنتين. (مسلم) (لغير الحاج.)"))
    if hijri_month == 10 and 2 <= hijri_day <= 7:
        msgs.append(L("✨ one of the *Six of Shawwal* — “whoever fasts Ramadan then six of Shawwal, it is as if he fasted the whole year.” (Muslim)",
                      "✨ من *ست شوال* — «من صام رمضان ثم أتبعه ستًا من شوال كان كصيام الدهر». (مسلم)"))
    return msgs

def checklist():
    return L(
        "🕌 *Salah & Adhkar*\n"
        "▫️ Pray the 5 prayers on time\n"
        "▫️ 12 Sunnah rak'ah (rawatib)\n"
        "▫️ Morning & evening adhkar\n"
        "▫️ Ayat al-Kursi after each salah\n"
        "▫️ Tasbih 33×3 after salah\n"
        "▫️ Witr before sleeping\n\n"
        "🌿 *Rawatib — Sunnah prayers*\n"
        "▫️ 2 rak'ah before Fajr\n"
        "▫️ 4 rak'ah before Dhuhr\n"
        "▫️ 2 rak'ah after Dhuhr\n"
        "▫️ 2 rak'ah after Maghrib\n"
        "▫️ 2 rak'ah after Isha\n"
        "_12 rak'ah → a house in Paradise (Bukhari & Muslim)_\n\n"
        "🌱 *Daily Sunan*\n"
        "▫️ Miswak / brush\n"
        "▫️ Bismillah + right hand when eating\n"
        "▫️ Send salawat on the Prophet ﷺ\n"
        "▫️ Istighfar 100×\n"
        "▫️ Read some Qur'an\n"
        "▫️ Duha & sleep on right side after wudu\n\n"
        "📅 *Weekly*\n"
        "▫️ Surah Al-Kahf + ghusl on Friday\n"
        "▫️ Fast Monday & Thursday\n"
        "▫️ The 3 white days (13–15)\n"
        "▫️ Keep ties with family\n\n"
        "💛 *Akhlaq*\n"
        "▫️ Smile & spread salam\n"
        "▫️ Be truthful, restrain anger\n"
        "▫️ Honour parents\n"
        "▫️ Speak good or stay silent",
        # ---- Arabic ----
        "🕌 *الصلاة والأذكار*\n"
        "▫️ صلِّ الفروض الخمسة في وقتها\n"
        "▫️ ١٢ ركعة من السنن الرواتب\n"
        "▫️ أذكار الصباح والمساء\n"
        "▫️ آية الكرسي بعد كل صلاة\n"
        "▫️ التسبيح ٣٣×٣ بعد الصلاة\n"
        "▫️ الوتر قبل النوم\n\n"
        "🌿 *السنن الرواتب*\n"
        "▫️ ركعتان قبل الفجر\n"
        "▫️ أربع ركعات قبل الظهر\n"
        "▫️ ركعتان بعد الظهر\n"
        "▫️ ركعتان بعد المغرب\n"
        "▫️ ركعتان بعد العشاء\n"
        "_١٢ ركعة يُبنى بها بيت في الجنة (البخاري ومسلم)_\n\n"
        "🌱 *سنن يومية*\n"
        "▫️ السواك\n"
        "▫️ التسمية والأكل باليمين\n"
        "▫️ الصلاة على النبي ﷺ\n"
        "▫️ الاستغفار ١٠٠ مرة\n"
        "▫️ قراءة وردٍ من القرآن\n"
        "▫️ الضحى والنوم على الشق الأيمن بعد الوضوء\n\n"
        "📅 *أسبوعية*\n"
        "▫️ سورة الكهف والغُسل يوم الجمعة\n"
        "▫️ صيام الإثنين والخميس\n"
        "▫️ الأيام البيض (١٣–١٥)\n"
        "▫️ صلة الرحم\n\n"
        "💛 *الأخلاق*\n"
        "▫️ الابتسامة وإفشاء السلام\n"
        "▫️ الصدق وكظم الغيظ\n"
        "▫️ برّ الوالدين\n"
        "▫️ قول الخير أو الصمت")

# ----------------------------------------------------------------------------
# Config / state
# ----------------------------------------------------------------------------
# The scheduler and the command poller run in separate threads and both mutate
# `state`; every read-modify-write of it happens under this lock.
STATE_LOCK = threading.RLock()

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            print(f"Warning: couldn't read {os.path.basename(path)} ({e}); starting fresh.")
    return default

def save_json(path, data):
    # Write to a temp file and rename, so a crash mid-write never leaves a
    # truncated state.json behind.
    with STATE_LOCK:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

# Settings come from environment variables first (best for cloud hosting —
# the token lives as a secret, never in a committed file), then fall back to
# config.json for easy local use.
config = load_json(CONFIG_PATH, {}) or {}

def cfg(env_key, json_key, default=None):
    v = os.environ.get(env_key)
    if v is not None and v != "":
        return v
    return config.get(json_key, default)

TOKEN = cfg("BOT_TOKEN", "bot_token")
if not TOKEN or "PUT_" in TOKEN:
    raise SystemExit(
        "\n  Missing bot token.\n"
        "  Local:  copy config.example.json -> config.json and paste your @BotFather token.\n"
        "  Cloud:  set the BOT_TOKEN environment variable / secret.\n"
    )

MORNING = cfg("MORNING_TIME", "morning_time", "07:00")
EVENING = cfg("EVENING_TIME", "evening_time", "17:30")
TIP_TIME = cfg("DAILY_TIP_TIME", "daily_tip_time", "09:00")
HADITH_TIME = cfg("HADITH_TIME", "hadith_time", "08:00")        # daily hadith
FRIDAY_TIME = cfg("FRIDAY_TIME", "friday_time", "09:30")        # Jumu'ah pack
FAST_REMIND_TIME = cfg("FAST_REMIND_TIME", "fast_remind_time", "20:00")  # eve-of-fast nudge

# On an always-on host the filesystem is wiped on every restart, so chat_id /
# city must come from durable env vars (host secrets). Locally they persist in
# state.json. Env values, when set, win and are kept fresh.
state = load_json(STATE_PATH, {})
env_chat = cfg("CHAT_ID", "chat_id")
state.setdefault("chat_id", int(env_chat) if (env_chat and str(env_chat).lstrip("-").isdigit()) else env_chat)
if env_chat:
    state["chat_id"] = int(env_chat) if str(env_chat).lstrip("-").isdigit() else env_chat
state.setdefault("city", cfg("CITY", "city", ""))
state.setdefault("country", cfg("COUNTRY", "country", ""))
if cfg("CITY", "city"):
    state["city"] = cfg("CITY", "city", "")
    state["country"] = cfg("COUNTRY", "country", "")
state.setdefault("paused", False)
state.setdefault("last_update_id", 0)
state.setdefault("prayers", None)          # {"date": "YYYY-MM-DD", "times": {...}}
state.setdefault("sent_today", [])         # keys of reminders already sent today
state.setdefault("sent_date", "")
state.setdefault("lang", cfg("LANG", "lang", "en"))   # "en" or "ar"

# Prayer-time accuracy settings. Coordinates (shared from the phone, or
# LATITUDE/LONGITUDE) beat a city name; method/school None = pick by country.
state.setdefault("lat", None)
state.setdefault("lng", None)
state.setdefault("method", None)
state.setdefault("school", None)          # 0 = Shafi'i/standard Asr, 1 = Hanafi
state.setdefault("offsets", {})           # {"Fajr": 2, ...} minutes, to match your mosque
_lat, _lng = cfg("LATITUDE", "latitude"), cfg("LONGITUDE", "longitude")
if _lat not in (None, "") and _lng not in (None, ""):
    state["lat"], state["lng"] = float(_lat), float(_lng)
if cfg("PRAYER_METHOD", "prayer_method") not in (None, ""):
    state["method"] = int(cfg("PRAYER_METHOD", "prayer_method"))
_asr = str(cfg("ASR_SCHOOL", "asr_school", "") or "").lower()
if _asr:
    state["school"] = 1 if _asr in ("1", "hanafi") else 0

# Prayer times are in the city's local time, but a cloud host's clock is
# usually UTC. The city's timezone is detected from the prayer-times API and
# stored in state["tz"]; TIMEZONE (e.g. "Europe/London") forces it instead.
TIMEZONE = cfg("TIMEZONE", "timezone")
if TIMEZONE:
    try:
        ZoneInfo(TIMEZONE)
        state["tz"] = TIMEZONE
    except Exception:
        # A typo here would otherwise silently put every reminder on the
        # server's clock *and* switch off auto-detection.
        print(f"Warning: unknown TIMEZONE {TIMEZONE!r}; detecting it from your city instead.")
        TIMEZONE = None

def L(en, ar):
    """Pick the string for the user's current language."""
    return ar if state.get("lang") == "ar" else en

def now_local():
    """Current time in the user's city (falls back to the machine's clock)."""
    name = state.get("tz")
    if name:
        try:
            return datetime.datetime.now(ZoneInfo(name))
        except Exception:
            pass
    return datetime.datetime.now()

def today_local():
    return now_local().date()

# ----------------------------------------------------------------------------
# Telegram helpers
# ----------------------------------------------------------------------------
def api(method, **params):
    # POST (not GET) so long messages never hit URL-length limits. The HTTP
    # timeout must outlast getUpdates' long-poll timeout.
    try:
        r = requests.post(API.format(token=TOKEN, method=method), json=params,
                          timeout=int(params.get("timeout", 0)) + 30)
        return r.json()
    except Exception as e:
        # The request URL contains the token; keep it out of the logs.
        print("API error:", str(e).replace(TOKEN, "<token>"))
        return {}

def md(text):
    """Escape user-supplied text for Telegram's (legacy) Markdown."""
    return "".join("\\" + c if c in "_*`[" else c for c in str(text))

def send(text, chat_id=None, **extra):
    """Send a message; returns True if Telegram accepted it."""
    cid = chat_id or state.get("chat_id")
    if not cid:
        return False
    res = api("sendMessage", chat_id=cid, text=text, parse_mode="Markdown",
              disable_web_page_preview=True, **extra)
    # Telegram rejects the whole message if the Markdown doesn't parse (e.g. a
    # city name with an underscore). Resend it as plain text rather than lose it.
    if res.get("error_code") == 400 and "parse" in str(res.get("description", "")).lower():
        res = api("sendMessage", chat_id=cid, text=text, disable_web_page_preview=True, **extra)
    if res and not res.get("ok"):
        print("Send failed:", res.get("description"))
    return bool(res.get("ok"))

# ----------------------------------------------------------------------------
# Prayer times (Aladhan API — free, no key)
# ----------------------------------------------------------------------------
FETCH_RETRY_SECONDS = 600
_last_fetch_fail = 0.0

def has_location():
    return state.get("lat") is not None or bool(state.get("city"))

def calc_settings():
    """(method, school) to use: the user's choice, else the local norm."""
    country = (state.get("country") or "").strip().lower()
    method = state.get("method") or METHOD_BY_COUNTRY.get(country)
    school = state.get("school")
    if school is None:
        school = 1 if country in HANAFI_COUNTRIES else 0
    return method, school

def prayer_request(day):
    """Aladhan URL and query params for `day` at the user's location."""
    dmy = day.strftime("%d-%m-%Y")
    if state.get("lat") is not None:
        url = "https://api.aladhan.com/v1/timings/" + dmy
        params = {"latitude": state["lat"], "longitude": state["lng"]}
    else:
        url = "https://api.aladhan.com/v1/timingsByCity/" + dmy
        params = {"city": state["city"], "country": state.get("country", "")}
    method, school = calc_settings()
    if method:
        params["method"] = method
    params["school"] = school
    return url, params

def apply_offsets(times):
    """Shift each prayer by the user's minute adjustments (to match a mosque)."""
    out = {}
    for name, hhmm in times.items():
        off = int((state.get("offsets") or {}).get(name, 0))
        if off:
            h, m = map(int, hhmm.split(":"))
            total = (h * 60 + m + off) % (24 * 60)
            hhmm = f"{total // 60:02d}:{total % 60:02d}"
        out[name] = hhmm
    return out

def fetch_prayers():
    global _last_fetch_fail
    if not has_location():
        return None
    today = today_local()
    url, params = prayer_request(today)
    try:
        j = requests.get(url, params=params, timeout=30).json()
        if j.get("code") == 200:
            t = j["data"]["timings"]
            times = {k: t[k][:5] for k in PRAYERS}
            meth = ((j["data"].get("meta") or {}).get("method") or {}).get("name", "")
            state["prayers"] = {"date": today.isoformat(), "times": times, "method": meth}
            # capture the Hijri date for fasting / occasion reminders
            try:
                h = j["data"]["date"]["hijri"]
                state["hijri"] = {"day": int(h["day"]), "month": int(h["month"]["number"]),
                                  "monthName": h["month"]["en"], "year": h["year"],
                                  "date": today.isoformat()}
            except Exception:
                pass
            tzname = (j["data"].get("meta") or {}).get("timezone")
            if tzname and not TIMEZONE:
                # If the city's date differs from the date we asked for,
                # ensure_prayers() notices on its next call and refetches.
                state["tz"] = tzname
            save_json(STATE_PATH, state)
            _last_fetch_fail = 0.0
            return apply_offsets(times)
        print("Prayer fetch failed:", j.get("data"))
    except Exception as e:
        print("Prayer fetch error:", e)
    _last_fetch_fail = time.time()
    return None

def ensure_prayers():
    p = state.get("prayers")
    if not p or p.get("date") != today_local().isoformat():
        # The scheduler asks every 30s; don't hammer the API after a failure.
        if time.time() - _last_fetch_fail < FETCH_RETRY_SECONDS:
            return None
        return fetch_prayers()
    return apply_offsets(p["times"])

def hijri_today():
    """Today's Hijri date, or {} if the cached one is from another day."""
    h = state.get("hijri") or {}
    return h if h.get("date") == today_local().isoformat() else {}

def fmt12(hhmm):
    h, m = map(int, hhmm.split(":"))
    ap = (("م" if h >= 12 else "ص") if state.get("lang") == "ar" else ("PM" if h >= 12 else "AM"))
    h = h % 12 or 12
    return f"{h}:{m:02d} {ap}"

def place_name():
    if state.get("lat") is not None:
        return L("your location", "موقعك")
    return md(state.get("city", ""))

def times_message():
    if not has_location():
        return L("Set your location first: /location (most accurate) or `/city Cairo, Egypt`",
                 "حدد موقعك أولًا: /location (الأدق) أو `/city Cairo, Egypt`")
    t = ensure_prayers()
    if not t:
        return L("Couldn't load prayer times right now. Please try again in a few minutes.",
                 "تعذّر تحميل أوقات الصلاة الآن. حاول مرة أخرى بعد دقائق.")
    lines = "\n".join(L(f"  *{n}* — {fmt12(v)}", f"  *{PRAYER_AR.get(n, n)}* — {fmt12(v)}") for n, v in t.items())
    _, school = calc_settings()
    meth = md((state.get("prayers") or {}).get("method") or "")
    asr = L("Hanafi", "حنفي") if school == 1 else L("standard", "الجمهور")
    note = L(f"\n\n_Method: {meth} · Asr: {asr}_", f"\n\n_طريقة الحساب: {meth} · العصر: {asr}_") if meth else ""
    if state.get("offsets"):
        note += L("\n_Adjusted to your mosque (/adjust)_", "\n_معدّلة حسب مسجدك (/adjust)_")
    return L(f"🕌 *Prayer times — {place_name()}*\n{lines}", f"🕌 *أوقات الصلاة — {place_name()}*\n{lines}") + note

# ----------------------------------------------------------------------------
# Reminder scheduling loop
# ----------------------------------------------------------------------------
def reset_daily_if_needed():
    today = today_local().isoformat()
    if state.get("sent_date") != today:
        state["sent_date"] = today
        state["sent_today"] = []
        save_json(STATE_PATH, state)

def due(key, hhmm, now):
    """Return True if reminder `key` scheduled at hhmm is due and unsent."""
    if key in state["sent_today"]:
        return False
    h, m = map(int, hhmm.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    # fire within a 0..3 minute window after the target so we never miss it
    return target <= now < target + datetime.timedelta(minutes=3)

def mark(key):
    state["sent_today"].append(key)
    save_json(STATE_PATH, state)

def remind(key, text):
    """Send a scheduled reminder; mark it done only once Telegram accepts it,
    so a failed send is retried on the next tick. text=None: nothing to say today."""
    if text is None or send(text):
        mark(key)

def scheduler_tick(now=None):
    """Send whatever reminders are due right now (called every 30s)."""
    if state.get("paused") or not state.get("chat_id"):
        return
    # Refresh today's prayer times first — this also refreshes the Hijri date
    # the fasting reminders below depend on, and may detect the city's timezone,
    # so read the clock only afterwards.
    t = ensure_prayers()
    now = now or now_local()
    reset_daily_if_needed()

    if due("morning", MORNING, now):
        d = DUAS[0]
        remind("morning", L(f"🌅 *Morning adhkar time*\n\n{d[1]}\n_{d[2]}_\n\nSay it 3× and start your day with Allah's remembrance.",
                            f"🌅 *وقت أذكار الصباح*\n\n{d[1]}\n\nقُلها ٣ مرات وابدأ يومك بذكر الله."))

    if due("tip", TIP_TIME, now):
        tp = random.choice(TIPS)
        remind("tip", L("🌿 *Sunnah of the day*\n\n" + tp[0], "🌿 *سنّة اليوم*\n\n" + tp[1]))

    if due("evening", EVENING, now):
        remind("evening", L("🌇 *Evening adhkar time*\n\nأَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ\n_We have entered the evening and the dominion belongs to Allah._\n\nDon't forget to review your Sunnah list today.",
                            "🌇 *وقت أذكار المساء*\n\nأَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ\n\nولا تنسَ مراجعة قائمة سننك اليوم."))

    # hadith of the day (cycles through Nawawi's Forty)
    if due("hadith", HADITH_TIME, now):
        n, en, ar, ref = HADITHS[now.date().toordinal() % len(HADITHS)]
        remind("hadith", L(f"📖 *Hadith of the day* (Nawawi #{n})\n\n“{en}”\n\n_— {ref}_",
                           f"📖 *حديث اليوم* (النووي #{n})\n\n«{ar}»\n\n_— {ref}_"))

    wd = now.weekday()  # Mon=0 … Fri=4 … Sun=6
    hij = hijri_today()
    hd, hm = hij.get("day"), hij.get("month")

    # today's fasting occasion (white days, Ashura, Arafah, Shawwal)
    if hd and due("occasion", HADITH_TIME, now):
        occ = fasting_special(hd, hm)
        remind("occasion", L("🗓️ *Today* is " + "; ".join(occ) + "\n\nA blessed day to fast if you're able. 🤍",
                             "🗓️ *اليوم* " + "؛ ".join(occ) + "\n\nيوم مبارك للصيام إن استطعت. 🤍") if occ else None)

    # Jumu'ah (Friday) pack
    if wd == 4 and due("jumuah", FRIDAY_TIME, now):
        remind("jumuah", L("🕌 *Jumu'ah Mubarak!* Today's Sunnah acts:\n\n"
                           "📖 Read *Surah Al-Kahf* — light between the two Fridays. (al-Hakim)\n"
                           "🚿 *Ghusl* and wear your best clothes.\n"
                           "🤲 Abundant *salawat* on the Prophet ﷺ — they are presented to him today. (Abu Dawud)\n"
                           "⏳ Watch for the *last hour before Maghrib* — a time when dua is answered. (Bukhari)",
                           "🕌 *جمعة مباركة!* من سنن اليوم:\n\n"
                           "📖 اقرأ *سورة الكهف* — نور ما بين الجمعتين. (الحاكم)\n"
                           "🚿 *الغُسل* وأفضل الثياب.\n"
                           "🤲 الإكثار من *الصلاة على النبي ﷺ* — فهي معروضة عليه اليوم. (أبو داود)\n"
                           "⏳ تحرَّ *الساعة الأخيرة قبل المغرب* — ساعة يُستجاب فيها الدعاء. (البخاري)"))

    # evening nudge to plan fasting tomorrow (suhoor)
    if due("fast_eve", FAST_REMIND_TIME, now):
        eve = []
        if wd == 6:
            eve.append(L("🌙 *Monday* — a day the Prophet ﷺ fasted. (Tirmidhi)", "🌙 *الإثنين* — يوم كان النبي ﷺ يصومه. (الترمذي)"))
        if wd == 2:
            eve.append(L("🌙 *Thursday* — a day the Prophet ﷺ fasted. (Tirmidhi)", "🌙 *الخميس* — يوم كان النبي ﷺ يصومه. (الترمذي)"))
        if hd:
            eve += fasting_special(hd + 1, hm)  # tomorrow's occasion
        remind("fast_eve", L("🍽️ *Plan to fast tomorrow?*\n\nTomorrow is " + "; ".join(eve) + "\n\nMake the intention and remember suhoor. 🤍",
                             "🍽️ *تنوي صيام الغد؟*\n\nالغد " + "؛ ".join(eve) + "\n\nاعقد النية ولا تنسَ السحور. 🤍") if eve else None)

    # prayer-time reminders
    if t:
        for name, hhmm in t.items():
            if due("salah_" + name, hhmm, now):
                remind("salah_" + name, L(f"🕌 *It's time for {name}* ({fmt12(hhmm)})\n\nHayya 'ala-s-salah. Leave what you're doing and pray. 🤍",
                                          f"🕌 *حان وقت صلاة {PRAYER_AR.get(name, name)}* ({fmt12(hhmm)})\n\nحيّ على الصلاة. اترك ما بيدك وصلِّ. 🤍"))
        # Friday: dua reminder in the last hour before Maghrib
        if wd == 4 and t.get("Maghrib"):
            mh, mm = map(int, t["Maghrib"].split(":"))
            last = (now.replace(hour=mh, minute=mm) - datetime.timedelta(minutes=60)).strftime("%H:%M")
            if due("friday_dua", last, now):
                remind("friday_dua", L("⏳ *The last hour before Maghrib (Friday)*\n\nThis is a time when no Muslim asks Allah for good except that He grants it. (Bukhari)\n\nRaise your hands and make du'a. 🤲",
                                       "⏳ *الساعة الأخيرة قبل المغرب (الجمعة)*\n\nساعة لا يسأل الله فيها مسلمٌ خيرًا إلا أعطاه إياه. (البخاري)\n\nارفع يديك وادعُ. 🤲"))

def scheduler_loop():
    print("Reminder scheduler running…")
    while True:
        try:
            with STATE_LOCK:
                scheduler_tick()
        except Exception as e:
            print("Scheduler error:", e)
        time.sleep(30)

# ----------------------------------------------------------------------------
# Command handling (long polling)
# ----------------------------------------------------------------------------
def help_text():
    return L(
        "*Sunnah Companion* 🤍\n\n"
        "/location — share your location (most accurate times)\n"
        "/city <City, Country> — set location by name\n"
        "/times — today's prayer times\n"
        "/method — calculation method\n"
        "/asr — standard or Hanafi Asr\n"
        "/adjust — match your mosque's timetable\n"
        "/today — Sunnah checklist\n"
        "/hadith — a hadith from Nawawi's Forty\n"
        "/friday — the Jumu'ah Sunnah acts\n"
        "/fasting — recommended fasting days now\n"
        "/dua — a prophetic supplication\n"
        "/tip — a Sunnah tip\n"
        "/language — العربية / English\n"
        "/stop — pause reminders\n"
        "/resume — resume reminders\n"
        "/help — this message",
        "*رفيق السنة* 🤍\n\n"
        "/location — مشاركة موقعك (أدق الأوقات)\n"
        "/city <City, Country> — تحديد المدينة بالاسم\n"
        "/times — أوقات الصلاة اليوم\n"
        "/method — طريقة الحساب\n"
        "/asr — العصر: الجمهور أو الحنفية\n"
        "/adjust — مطابقة جدول مسجدك\n"
        "/today — قائمة السنن\n"
        "/hadith — حديث من الأربعين النووية\n"
        "/friday — سنن يوم الجمعة\n"
        "/fasting — أيام الصيام المستحبة الآن\n"
        "/dua — دعاء نبوي\n"
        "/tip — سنّة مختصرة\n"
        "/language — العربية / English\n"
        "/stop — إيقاف التذكيرات\n"
        "/resume — استئناف التذكيرات\n"
        "/help — هذه القائمة")

def cmd_start(text, low, chat_id):
    state["chat_id"] = chat_id
    save_json(STATE_PATH, state)
    send(L("Assalamu alaikum 🤍\n\nYou're registered for Sunnah reminders. "
           "For the most accurate prayer times, share your location with /location "
           "(or type your city, e.g. `/city Cairo, Egypt`).\n\n",
           "السلام عليكم 🤍\n\nتم تسجيلك لتذكيرات السنة. "
           "لأدق أوقات الصلاة شارك موقعك عبر /location "
           "(أو اكتب مدينتك، مثال: `/city Cairo, Egypt`).\n\n") + help_text(), chat_id)

def cmd_language(text, low, chat_id):
    arg = low.replace("/language", "").replace("/lang", "").strip()
    if "ar" in arg or "عرب" in arg or low.startswith("/arabic") or low.startswith("/عربي") or low.startswith("/العربية"):
        state["lang"] = "ar"
    elif "en" in arg or low.startswith("/english"):
        state["lang"] = "en"
    else:
        state["lang"] = "ar" if state.get("lang") == "en" else "en"  # toggle
    save_json(STATE_PATH, state)
    send(L("✅ Language set to English.", "✅ تم ضبط اللغة على العربية.") + "\n\n" + help_text(), chat_id)

def cmd_city(text, low, chat_id):
    rest = text[5:].strip().lstrip(":").strip()
    if not rest:
        return send(L("Send it like: `/city Cairo, Egypt`", "أرسلها هكذا: `/city Cairo, Egypt`"), chat_id)
    if "," in rest:
        city, country = [x.strip() for x in rest.split(",", 1)]
    else:
        city, country = rest, ""
    state["city"], state["country"] = city, country
    state["lat"] = state["lng"] = None      # a typed city replaces a shared location
    state["prayers"] = None
    save_json(STATE_PATH, state)
    t = fetch_prayers()
    if t:
        send(L(f"📍 Location set to *{md(city)}*.\n\n", f"📍 تم تحديد الموقع: *{md(city)}*.\n\n") + times_message(), chat_id)
    else:
        send(L(f"📍 Saved *{md(city)}*, but I couldn't load prayer times. Check the spelling, e.g. `/city Cairo, Egypt`.",
               f"📍 حُفظت *{md(city)}*، لكن تعذّر تحميل أوقات الصلاة. تحقق من الكتابة، مثال: `/city Cairo, Egypt`."), chat_id)

def refresh_times_reply(chat_id, header):
    state["prayers"] = None
    save_json(STATE_PATH, state)
    fetch_prayers()
    send(header + "\n\n" + times_message(), chat_id, reply_markup={"remove_keyboard": True})

def cmd_location(text, low, chat_id):
    send(L("📍 Tap the button below to share your location. Prayer times will be "
           "calculated for your exact position — more accurate than a city name.\n\n"
           "_Share it again whenever you travel._",
           "📍 اضغط الزر بالأسفل لمشاركة موقعك، لتُحسب أوقات الصلاة لموقعك بالضبط — "
           "وهذا أدق من اسم المدينة.\n\n_أعد المشاركة كلما سافرت._"), chat_id,
         reply_markup={"keyboard": [[{"text": L("📍 Send my location", "📍 أرسل موقعي"),
                                      "request_location": True}]],
                       "one_time_keyboard": True, "resize_keyboard": True})

def handle_location(loc, chat_id):
    """A location shared from the phone (the most accurate way to set it)."""
    if not is_owner(chat_id):
        return send(L("This is a private Sunnah Companion bot — it's already registered to someone else.",
                      "هذا بوت خاص — وهو مسجّل لشخص آخر بالفعل."), chat_id)
    state["lat"], state["lng"] = round(float(loc["latitude"]), 4), round(float(loc["longitude"]), 4)
    refresh_times_reply(chat_id, L("📍 Got your location.", "📍 تم استلام موقعك."))

def cmd_method(text, low, chat_id):
    arg = low.split(maxsplit=1)[1].strip() if " " in low else ""
    if arg.isdigit() and (int(arg) == 0 or int(arg) in METHODS):
        state["method"] = int(arg) or None
        method, _ = calc_settings()
        name = METHODS.get(method, L("closest authority to you", "أقرب هيئة لموقعك"))
        return refresh_times_reply(chat_id, L(f"✅ Calculation method: *{name}*", f"✅ طريقة الحساب: *{name}*"))
    method, _ = calc_settings()
    current = METHODS.get(method, L("auto (closest authority)", "تلقائي (أقرب هيئة)"))
    listing = "\n".join(f"`{k}` — {v}" for k, v in METHODS.items())
    send(L(f"🧭 *Calculation method* — now: *{current}*\n\nPick the one your local mosque uses, e.g. `/method 15`. "
           f"`/method 0` = automatic for your country.\n\n{listing}",
           f"🧭 *طريقة الحساب* — الحالية: *{current}*\n\nاختر ما يعتمده مسجدك، مثال: `/method 15`. "
           f"`/method 0` = تلقائي حسب بلدك.\n\n{listing}"), chat_id)

def cmd_asr(text, low, chat_id):
    if "hanaf" in low or "حنف" in low:
        state["school"] = 1
    elif "shaf" in low or "standard" in low or "شاف" in low or "جمهور" in low:
        state["school"] = 0
    else:
        return send(L("Choose how Asr is calculated:\n`/asr standard` — Shafi'i, Maliki, Hanbali (shadow = object)\n"
                      "`/asr hanafi` — Hanafi (shadow = 2× object, later)",
                      "اختر طريقة حساب العصر:\n`/asr standard` — الجمهور (ظل الشيء مثله)\n"
                      "`/asr hanafi` — الحنفية (ظل الشيء مثليه، وقت متأخر)"), chat_id)
    refresh_times_reply(chat_id, L("✅ Asr updated.", "✅ تم تحديث وقت العصر."))

def cmd_adjust(text, low, chat_id):
    parts = low.split()
    if len(parts) == 2 and parts[1] == "reset":
        state["offsets"] = {}
        return refresh_times_reply(chat_id, L("✅ Adjustments cleared.", "✅ تم حذف التعديلات."))
    names = {p.lower(): p for p in PRAYERS}
    if len(parts) == 3 and parts[1] in names and parts[2].lstrip("+-").isdigit() and abs(int(parts[2])) <= 60:
        offs = dict(state.get("offsets") or {})
        offs[names[parts[1]]] = int(parts[2])
        state["offsets"] = {k: v for k, v in offs.items() if v}
        return refresh_times_reply(chat_id, L("✅ Adjusted.", "✅ تم التعديل."))
    send(L("Match your mosque's timetable by shifting a prayer (±60 min):\n"
           "`/adjust maghrib +3`\n`/adjust fajr -2`\n`/adjust reset`",
           "طابق جدول مسجدك بتعديل صلاة (±٦٠ دقيقة):\n"
           "`/adjust maghrib +3`\n`/adjust fajr -2`\n`/adjust reset`"), chat_id)

def cmd_times(text, low, chat_id):
    send(times_message(), chat_id)

def cmd_today(text, low, chat_id):
    send(checklist(), chat_id)

def cmd_hadith(text, low, chat_id):
    n, en, ar, ref = random.choice(HADITHS)
    send(L(f"📖 *Hadith* (Nawawi #{n})\n\n“{en}”\n\n_— {ref}_",
           f"📖 *حديث* (النووي #{n})\n\n«{ar}»\n\n_— {ref}_"), chat_id)

def cmd_friday(text, low, chat_id):
    send(L("🕌 *Jumu'ah Sunnah acts*\n\n"
           "📖 Read *Surah Al-Kahf* — light between the two Fridays. (al-Hakim)\n"
           "🚿 *Ghusl* and wear your best clothes; use perfume.\n"
           "⏱️ Go *early* to the masjid.\n"
           "🤲 Abundant *salawat* on the Prophet ﷺ. (Abu Dawud)\n"
           "⏳ The *last hour before Maghrib* — a time du'a is answered. (Bukhari)",
           "🕌 *سنن يوم الجمعة*\n\n"
           "📖 اقرأ *سورة الكهف* — نور ما بين الجمعتين. (الحاكم)\n"
           "🚿 *الغُسل* وأفضل الثياب والطيب.\n"
           "⏱️ *التبكير* إلى المسجد.\n"
           "🤲 الإكثار من *الصلاة على النبي ﷺ*. (أبو داود)\n"
           "⏳ *الساعة الأخيرة قبل المغرب* — ساعة يُستجاب فيها الدعاء. (البخاري)"), chat_id)

def cmd_fasting(text, low, chat_id):
    ensure_prayers()
    hij = hijri_today()
    lines = L(["🍽️ *Recommended fasting*\n",
               "• *Mondays & Thursdays* — the Prophet ﷺ fasted them. (Tirmidhi)",
               "• The *3 White Days* — 13th, 14th, 15th of each Hijri month. (Bukhari)"],
              ["🍽️ *الصيام المستحب*\n",
               "• *الإثنين والخميس* — كان النبي ﷺ يصومهما. (الترمذي)",
               "• *الأيام البيض* — ١٣ و١٤ و١٥ من كل شهر هجري. (البخاري)"])
    lines = list(lines)
    if hij.get("day"):
        lines.append(L(f"\n_Today is {hij['day']} {hij.get('monthName','')} {hij.get('year','')} AH._",
                       f"\n_اليوم {hij['day']} {hij.get('monthName','')} {hij.get('year','')}هـ._"))
        occ = fasting_special(hij["day"], hij["month"])
        if occ:
            lines.append(L("👉 Today is " + "; ".join(occ), "👉 اليوم " + "؛ ".join(occ)))
    send("\n".join(lines), chat_id)

def cmd_dua(text, low, chat_id):
    d = random.choice(DUAS)
    send(L(f"🤲 *{d[0]}*\n\n{d[1]}\n_{d[2]}_", f"🤲 *{d[3]}*\n\n{d[1]}"), chat_id)

def cmd_tip(text, low, chat_id):
    tp = random.choice(TIPS)
    send("🌿 " + L(tp[0], tp[1]), chat_id)

def cmd_stop(text, low, chat_id):
    state["paused"] = True; save_json(STATE_PATH, state)
    send(L("Reminders paused. Send /resume anytime.", "تم إيقاف التذكيرات. أرسل /resume في أي وقت."), chat_id)

def cmd_resume(text, low, chat_id):
    state["paused"] = False; save_json(STATE_PATH, state)
    send(L("Reminders resumed. 🤍", "تم استئناف التذكيرات. 🤍"), chat_id)

def cmd_help(text, low, chat_id):
    send(help_text(), chat_id)


def cmd_unknown(text, low, chat_id):
    send(L("I didn't recognise that. Send /help for commands.", "لم أفهم ذلك. أرسل /help لعرض الأوامر."), chat_id)

# Ordered dispatch table: (matcher, handler, owner_only). owner_only commands
# change the bot's settings: once it is registered to a chat, other chats can't
# take it over or change it. First match wins, so the order
# here reproduces the old if/elif chain exactly (prefix match, not equality).
# handle() calls the handler indirectly through this list, which is also why it
# is no longer a "god node" in the call graph — each command owns its own edges.
def _starts(*prefixes):
    return lambda low: any(low.startswith(p) for p in prefixes)

COMMANDS = [
    (_starts("/start"), cmd_start, True),
    (_starts("/language", "/lang", "/arabic", "/english", "/عربي", "/العربية"), cmd_language, True),
    (_starts("/city"), cmd_city, True),
    (_starts("/location"), cmd_location, True),
    (_starts("/method"), cmd_method, True),
    (_starts("/asr", "/madhab"), cmd_asr, True),
    (_starts("/adjust"), cmd_adjust, True),
    (_starts("/times"), cmd_times, False),
    (_starts("/today"), cmd_today, False),
    (_starts("/hadith"), cmd_hadith, False),
    (_starts("/friday", "/jumuah", "/jumah"), cmd_friday, False),
    (lambda low: low.startswith("/fasting") or (low.startswith("/fast") and not low.startswith("/faste")), cmd_fasting, False),
    (_starts("/dua"), cmd_dua, False),
    (_starts("/tip"), cmd_tip, False),
    (_starts("/stop"), cmd_stop, True),
    (_starts("/resume"), cmd_resume, True),
    (_starts("/help"), cmd_help, False),
]

def is_owner(chat_id):
    owner = state.get("chat_id")
    return not owner or str(owner) == str(chat_id)

def handle(text, chat_id):
    text = (text or "").strip()
    if not text:
        return  # stickers, photos, etc.
    # In groups Telegram sends "/city@MyBot Cairo" — drop the @MyBot part.
    head, sep, rest = text.partition(" ")
    if head.startswith("/") and "@" in head:
        text = head.split("@", 1)[0] + sep + rest
    low = text.lower()
    for matches, fn, owner_only in COMMANDS:
        if matches(low):
            if owner_only and not is_owner(chat_id):
                return send(L("This is a private Sunnah Companion bot — it's already registered to someone else.",
                              "هذا بوت خاص — وهو مسجّل لشخص آخر بالفعل."), chat_id)
            return fn(text, low, chat_id)
    return cmd_unknown(text, low, chat_id)

def polling_loop():
    print("Listening for Telegram commands…")
    while True:
        try:
            res = api("getUpdates", offset=state["last_update_id"] + 1, timeout=25)
            if not res.get("ok"):
                # Network down, or 409 = another copy of the bot is polling
                # with the same token. Back off instead of spinning.
                print("getUpdates failed:", res.get("description", "no response"))
                time.sleep(10)
                continue
            updates = res.get("result", [])
            for upd in updates:
                with STATE_LOCK:
                    state["last_update_id"] = upd["update_id"]
                    msg = upd.get("message") or upd.get("edited_message")
                    if msg and msg.get("location"):
                        handle_location(msg["location"], msg["chat"]["id"])
                    elif msg:
                        handle(msg.get("text", ""), msg["chat"]["id"])
            if updates:  # an empty long-poll changes nothing worth writing
                save_json(STATE_PATH, state)
        except Exception as e:
            print("Polling error:", e)
            time.sleep(5)

# ----------------------------------------------------------------------------
# Tiny health-check web server. Cloud hosts (Render, Koyeb, etc.) set $PORT and
# expect the process to answer HTTP. An uptime pinger (e.g. UptimeRobot) hits
# "/" every few minutes so the free instance never goes to sleep.
# ----------------------------------------------------------------------------
def start_health_server():
    port = os.environ.get("PORT")
    if not port:
        return
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Sunnah Companion bot is alive \xf0\x9f\xa4\x8d")
        def do_HEAD(self):  # some uptime pingers use HEAD
            self.send_response(200)
            self.end_headers()
        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", int(port)), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"Health server listening on :{port}")

def main():
    start_health_server()
    delay = 5
    while True:
        me = api("getMe")
        if me.get("ok"):
            break
        if me.get("error_code") in (401, 404):
            raise SystemExit("Telegram rejected the bot token — check BOT_TOKEN / config.json.")
        print(f"Could not reach Telegram — retrying in {delay}s…")
        time.sleep(delay)
        delay = min(delay * 2, 300)
    print(f"Bot @{me['result']['username']} is live. Press Ctrl+C to stop.")
    threading.Thread(target=scheduler_loop, daemon=True).start()
    polling_loop()

if __name__ == "__main__":
    main()

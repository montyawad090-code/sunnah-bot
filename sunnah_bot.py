#!/usr/bin/env python3
"""
Sunnah Companion — Telegram reminder bot
----------------------------------------
Sends you reminders to follow the Sunnah of the Prophet Muhammad (peace be upon him):
prayer times, morning/evening adhkar, and a daily Sunnah tip — even when nothing is open.

Only dependency: `requests`  (pip install requests)

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
  /dua     a prophetic supplication
  /tip     a random Sunnah tip
  /stop    pause reminders     /resume  resume them
  /help    show commands
"""

import json, os, time, random, datetime, threading
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
        "🌿 *Daily Sunan*\n"
        "▫️ Miswak / brush\n"
        "▫️ Bismillah + right hand when eating\n"
        "▫️ Send salawat on the Prophet ﷺ\n"
        "▫️ Istighfar 100×\n"
        "▫️ Read some Qur'an\n"
        "▫️ Sleep on right side after wudu\n\n"
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
        "🌿 *سنن يومية*\n"
        "▫️ السواك\n"
        "▫️ التسمية والأكل باليمين\n"
        "▫️ الصلاة على النبي ﷺ\n"
        "▫️ الاستغفار ١٠٠ مرة\n"
        "▫️ قراءة وردٍ من القرآن\n"
        "▫️ النوم على الشق الأيمن بعد الوضوء\n\n"
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
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
# city must come from durable env vars (Fly secrets). Locally they persist in
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

def L(en, ar):
    """Pick the string for the user's current language."""
    return ar if state.get("lang") == "ar" else en

# ----------------------------------------------------------------------------
# Telegram helpers
# ----------------------------------------------------------------------------
def api(method, **params):
    try:
        r = requests.get(API.format(token=TOKEN, method=method), params=params, timeout=30)
        return r.json()
    except Exception as e:
        print("API error:", e)
        return {}

def send(text, chat_id=None):
    cid = chat_id or state.get("chat_id")
    if not cid:
        return
    api("sendMessage", chat_id=cid, text=text, parse_mode="Markdown",
        disable_web_page_preview=True)

# ----------------------------------------------------------------------------
# Prayer times (Aladhan API — free, no key)
# ----------------------------------------------------------------------------
def fetch_prayers():
    if not state.get("city"):
        return None
    today = datetime.date.today()
    dmy = today.strftime("%d-%m-%Y")
    url = ("https://api.aladhan.com/v1/timingsByCity/" + dmy +
           "?city=" + requests.utils.quote(state["city"]) +
           "&country=" + requests.utils.quote(state.get("country", "")) +
           "&method=2")
    try:
        j = requests.get(url, timeout=30).json()
        if j.get("code") == 200:
            t = j["data"]["timings"]
            times = {k: t[k][:5] for k in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]}
            state["prayers"] = {"date": today.isoformat(), "times": times}
            # capture the Hijri date for fasting / occasion reminders
            try:
                h = j["data"]["date"]["hijri"]
                state["hijri"] = {"day": int(h["day"]), "month": int(h["month"]["number"]),
                                  "monthName": h["month"]["en"], "year": h["year"],
                                  "date": today.isoformat()}
            except Exception:
                pass
            save_json(STATE_PATH, state)
            return times
    except Exception as e:
        print("Prayer fetch error:", e)
    return None

def ensure_prayers():
    p = state.get("prayers")
    if not p or p.get("date") != datetime.date.today().isoformat():
        return fetch_prayers()
    return p["times"]

def fmt12(hhmm):
    h, m = map(int, hhmm.split(":"))
    ap = (("م" if h >= 12 else "ص") if state.get("lang") == "ar" else ("PM" if h >= 12 else "AM"))
    h = h % 12 or 12
    return f"{h}:{m:02d} {ap}"

def times_message():
    t = ensure_prayers()
    if not t:
        return L("Set your city first, e.g. `/city Cairo, Egypt`", "حدد مدينتك أولًا، مثال: `/city Cairo, Egypt`")
    lines = "\n".join(L(f"  *{n}* — {fmt12(v)}", f"  *{PRAYER_AR.get(n, n)}* — {fmt12(v)}") for n, v in t.items())
    return L(f"🕌 *Prayer times — {state['city']}*\n{lines}", f"🕌 *أوقات الصلاة — {state['city']}*\n{lines}")

# ----------------------------------------------------------------------------
# Reminder scheduling loop
# ----------------------------------------------------------------------------
def reset_daily_if_needed():
    today = datetime.date.today().isoformat()
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

def scheduler_loop():
    print("Reminder scheduler running…")
    while True:
        try:
            if not state.get("paused") and state.get("chat_id"):
                reset_daily_if_needed()
                now = datetime.datetime.now()

                if due("morning", MORNING, now):
                    d = DUAS[0]
                    send(L(f"🌅 *Morning adhkar time*\n\n{d[1]}\n_{d[2]}_\n\nSay it 3× and start your day with Allah's remembrance.",
                           f"🌅 *وقت أذكار الصباح*\n\n{d[1]}\n\nقُلها ٣ مرات وابدأ يومك بذكر الله."))
                    mark("morning")

                if due("tip", TIP_TIME, now):
                    tp = random.choice(TIPS)
                    send(L("🌿 *Sunnah of the day*\n\n" + tp[0], "🌿 *سنّة اليوم*\n\n" + tp[1]))
                    mark("tip")

                if due("evening", EVENING, now):
                    send(L("🌇 *Evening adhkar time*\n\nأَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ\n_We have entered the evening and the dominion belongs to Allah._\n\nDon't forget to review your Sunnah list today.",
                           "🌇 *وقت أذكار المساء*\n\nأَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ\n\nولا تنسَ مراجعة قائمة سننك اليوم."))
                    mark("evening")

                # hadith of the day (cycles through Nawawi's Forty)
                if due("hadith", HADITH_TIME, now):
                    n, en, ar, ref = HADITHS[datetime.date.today().toordinal() % len(HADITHS)]
                    send(L(f"📖 *Hadith of the day* (Nawawi #{n})\n\n“{en}”\n\n_— {ref}_",
                           f"📖 *حديث اليوم* (النووي #{n})\n\n«{ar}»\n\n_— {ref}_"))
                    mark("hadith")

                wd = now.weekday()  # Mon=0 … Fri=4 … Sun=6
                hij = state.get("hijri") or {}
                hd, hm = hij.get("day"), hij.get("month")

                # today's fasting occasion (white days, Ashura, Arafah, Shawwal)
                if hd and due("occasion", HADITH_TIME, now):
                    occ = fasting_special(hd, hm)
                    if occ:
                        send(L("🗓️ *Today* is " + "; ".join(occ) + "\n\nA blessed day to fast if you're able. 🤍",
                               "🗓️ *اليوم* " + "؛ ".join(occ) + "\n\nيوم مبارك للصيام إن استطعت. 🤍"))
                    mark("occasion")

                # Jumu'ah (Friday) pack
                if wd == 4 and due("jumuah", FRIDAY_TIME, now):
                    send(L("🕌 *Jumu'ah Mubarak!* Today's Sunnah acts:\n\n"
                           "📖 Read *Surah Al-Kahf* — light between the two Fridays. (al-Hakim)\n"
                           "🚿 *Ghusl* and wear your best clothes.\n"
                           "🤲 Abundant *salawat* on the Prophet ﷺ — they are presented to him today. (Abu Dawud)\n"
                           "⏳ Watch for the *last hour before Maghrib* — a time when dua is answered. (Bukhari)",
                           "🕌 *جمعة مباركة!* من سنن اليوم:\n\n"
                           "📖 اقرأ *سورة الكهف* — نور ما بين الجمعتين. (الحاكم)\n"
                           "🚿 *الغُسل* وأفضل الثياب.\n"
                           "🤲 الإكثار من *الصلاة على النبي ﷺ* — فهي معروضة عليه اليوم. (أبو داود)\n"
                           "⏳ تحرَّ *الساعة الأخيرة قبل المغرب* — ساعة يُستجاب فيها الدعاء. (البخاري)"))
                    mark("jumuah")

                # evening nudge to plan fasting tomorrow (suhoor)
                if due("fast_eve", FAST_REMIND_TIME, now):
                    eve = []
                    if wd == 6:
                        eve.append(L("🌙 *Monday* — a day the Prophet ﷺ fasted. (Tirmidhi)", "🌙 *الإثنين* — يوم كان النبي ﷺ يصومه. (الترمذي)"))
                    if wd == 2:
                        eve.append(L("🌙 *Thursday* — a day the Prophet ﷺ fasted. (Tirmidhi)", "🌙 *الخميس* — يوم كان النبي ﷺ يصومه. (الترمذي)"))
                    if hd:
                        eve += fasting_special(hd + 1, hm)  # tomorrow's occasion
                    if eve:
                        send(L("🍽️ *Plan to fast tomorrow?*\n\nTomorrow is " + "; ".join(eve) + "\n\nMake the intention and remember suhoor. 🤍",
                               "🍽️ *تنوي صيام الغد؟*\n\nالغد " + "؛ ".join(eve) + "\n\nاعقد النية ولا تنسَ السحور. 🤍"))
                    mark("fast_eve")

                # prayer-time reminders
                t = ensure_prayers()
                if t:
                    for name, hhmm in t.items():
                        if due("salah_" + name, hhmm, now):
                            send(L(f"🕌 *It's time for {name}* ({fmt12(hhmm)})\n\nHayya 'ala-s-salah. Leave what you're doing and pray. 🤍",
                                   f"🕌 *حان وقت صلاة {PRAYER_AR.get(name, name)}* ({fmt12(hhmm)})\n\nحيّ على الصلاة. اترك ما بيدك وصلِّ. 🤍"))
                            mark("salah_" + name)
                    # Friday: dua reminder in the last hour before Maghrib
                    if wd == 4 and t.get("Maghrib"):
                        mh, mm = map(int, t["Maghrib"].split(":"))
                        last = (datetime.datetime.now().replace(hour=mh, minute=mm) - datetime.timedelta(minutes=60)).strftime("%H:%M")
                        if due("friday_dua", last, now):
                            send(L("⏳ *The last hour before Maghrib (Friday)*\n\nThis is a time when no Muslim asks Allah for good except that He grants it. (Bukhari)\n\nRaise your hands and make du'a. 🤲",
                                   "⏳ *الساعة الأخيرة قبل المغرب (الجمعة)*\n\nساعة لا يسأل الله فيها مسلمٌ خيرًا إلا أعطاه إياه. (البخاري)\n\nارفع يديك وادعُ. 🤲"))
                            mark("friday_dua")
        except Exception as e:
            print("Scheduler error:", e)
        time.sleep(30)

# ----------------------------------------------------------------------------
# Command handling (long polling)
# ----------------------------------------------------------------------------
def help_text():
    return L(
        "*Sunnah Companion* 🤍\n\n"
        "/city <City, Country> — set location\n"
        "/times — today's prayer times\n"
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
        "/city <City, Country> — تحديد المدينة\n"
        "/times — أوقات الصلاة اليوم\n"
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

def handle(text, chat_id):
    text = (text or "").strip()
    low = text.lower()

    if low.startswith("/start"):
        state["chat_id"] = chat_id
        save_json(STATE_PATH, state)
        send(L("Assalamu alaikum 🤍\n\nYou're registered for Sunnah reminders. "
               "Set your city for prayer times, e.g.\n`/city Cairo, Egypt`\n\n",
               "السلام عليكم 🤍\n\nتم تسجيلك لتذكيرات السنة. "
               "حدد مدينتك لأوقات الصلاة، مثال:\n`/city Cairo, Egypt`\n\n") + help_text(), chat_id)

    elif low.startswith("/language") or low.startswith("/lang") or low.startswith("/arabic") or low.startswith("/english") or low.startswith("/عربي") or low.startswith("/العربية"):
        arg = low.replace("/language", "").replace("/lang", "").strip()
        if "ar" in arg or "عرب" in arg or low.startswith("/arabic") or low.startswith("/عربي") or low.startswith("/العربية"):
            state["lang"] = "ar"
        elif "en" in arg or low.startswith("/english"):
            state["lang"] = "en"
        else:
            state["lang"] = "ar" if state.get("lang") == "en" else "en"  # toggle
        save_json(STATE_PATH, state)
        send(L("✅ Language set to English.", "✅ تم ضبط اللغة على العربية.") + "\n\n" + help_text(), chat_id)

    elif low.startswith("/city"):
        rest = text[5:].strip().lstrip(":").strip()
        if not rest:
            return send(L("Send it like: `/city Cairo, Egypt`", "أرسلها هكذا: `/city Cairo, Egypt`"), chat_id)
        if "," in rest:
            city, country = [x.strip() for x in rest.split(",", 1)]
        else:
            city, country = rest, ""
        state["city"], state["country"] = city, country
        state["prayers"] = None
        save_json(STATE_PATH, state)
        t = fetch_prayers()
        if t:
            send(L(f"📍 Location set to *{city}*.\n\n", f"📍 تم تحديد الموقع: *{city}*.\n\n") + times_message(), chat_id)
        else:
            send(L(f"📍 Saved *{city}*, but I couldn't load prayer times. Check the spelling, e.g. `/city Cairo, Egypt`.",
                   f"📍 حُفظت *{city}*، لكن تعذّر تحميل أوقات الصلاة. تحقق من الكتابة، مثال: `/city Cairo, Egypt`."), chat_id)

    elif low.startswith("/times"):
        send(times_message(), chat_id)

    elif low.startswith("/today"):
        send(checklist(), chat_id)

    elif low.startswith("/hadith"):
        n, en, ar, ref = random.choice(HADITHS)
        send(L(f"📖 *Hadith* (Nawawi #{n})\n\n“{en}”\n\n_— {ref}_",
               f"📖 *حديث* (النووي #{n})\n\n«{ar}»\n\n_— {ref}_"), chat_id)

    elif low.startswith("/friday") or low.startswith("/jumuah") or low.startswith("/jumah"):
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

    elif low.startswith("/fasting") or (low.startswith("/fast") and not low.startswith("/faste")):
        hij = state.get("hijri") or {}
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

    elif low.startswith("/dua"):
        d = random.choice(DUAS)
        send(L(f"🤲 *{d[0]}*\n\n{d[1]}\n_{d[2]}_", f"🤲 *{d[3]}*\n\n{d[1]}"), chat_id)

    elif low.startswith("/tip"):
        tp = random.choice(TIPS)
        send("🌿 " + L(tp[0], tp[1]), chat_id)

    elif low.startswith("/stop"):
        state["paused"] = True; save_json(STATE_PATH, state)
        send(L("Reminders paused. Send /resume anytime.", "تم إيقاف التذكيرات. أرسل /resume في أي وقت."), chat_id)

    elif low.startswith("/resume"):
        state["paused"] = False; save_json(STATE_PATH, state)
        send(L("Reminders resumed. 🤍", "تم استئناف التذكيرات. 🤍"), chat_id)

    elif low.startswith("/help"):
        send(help_text(), chat_id)

    else:
        send(L("I didn't recognise that. Send /help for commands.", "لم أفهم ذلك. أرسل /help لعرض الأوامر."), chat_id)

def polling_loop():
    print("Listening for Telegram commands…")
    while True:
        try:
            res = api("getUpdates", offset=state["last_update_id"] + 1, timeout=25)
            for upd in res.get("result", []):
                state["last_update_id"] = upd["update_id"]
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                handle(msg.get("text", ""), chat_id)
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
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Sunnah Companion bot is alive \xf0\x9f\xa4\x8d")
        def log_message(self, *a):
            pass

    srv = HTTPServer(("0.0.0.0", int(port)), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"Health server listening on :{port}")

def main():
    me = api("getMe")
    if not me.get("ok"):
        raise SystemExit("Could not reach Telegram — check your bot token and internet.")
    print(f"Bot @{me['result']['username']} is live. Press Ctrl+C to stop.")
    start_health_server()
    if state.get("chat_id"):
        ensure_prayers()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    polling_loop()

if __name__ == "__main__":
    main()

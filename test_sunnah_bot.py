#!/usr/bin/env python3
"""
Behavior tests for the two highest-blast-radius functions in the bot:
  - L()      — language string picker (bridges every user-facing message)
  - handle() — the Telegram command dispatcher (the god node: ~10 call edges)

These tests are intentionally hermetic: no network, no disk. They set a dummy
BOT_TOKEN in the environment *before* import (env wins over config.json), then
stub out `send`, `save_json`, and `fetch_prayers` so nothing leaves the process.

Run:  python test_sunnah_bot.py       (or: python -m unittest -v)
"""
import datetime
import os
import unittest

# Env must be set before importing the bot: the module reads its token at import
# time and raises SystemExit if none is found. cfg() checks env before config.json,
# so this also isolates the tests from whatever is in the real config.json.
os.environ.setdefault("BOT_TOKEN", "TESTING:dummy-token")

import sunnah_bot as bot  # noqa: E402


class BotTestBase(unittest.TestCase):
    """Snapshot global state, stub out the I/O seams, restore on teardown."""

    def setUp(self):
        # Deep-ish snapshot: state holds only JSON-able scalars/lists/dicts.
        import copy
        self._state_backup = copy.deepcopy(bot.state)
        self._orig_send = bot.send
        self._orig_save = bot.save_json
        self._orig_fetch = bot.fetch_prayers

        self.sent = []  # list of (text, chat_id)
        # Like the real send(), report success so the scheduler marks reminders sent.
        bot.send = lambda text, chat_id=None: self.sent.append((text, chat_id)) or True
        bot.save_json = lambda *a, **k: None  # never touch state.json on disk
        bot.fetch_prayers = lambda *a, **k: None  # never hit the Aladhan API

        # Default language English unless a test overrides it.
        bot.state["lang"] = "en"

    def tearDown(self):
        bot.send = self._orig_send
        bot.save_json = self._orig_save
        bot.fetch_prayers = self._orig_fetch
        bot.state.clear()
        bot.state.update(self._state_backup)

    # Convenience: text of the last message the bot tried to send.
    def last(self):
        self.assertTrue(self.sent, "expected the bot to send a message")
        return self.sent[-1][0]

    def last_chat(self):
        self.assertTrue(self.sent, "expected the bot to send a message")
        return self.sent[-1][1]


class TestL(BotTestBase):
    def test_en_returns_first(self):
        bot.state["lang"] = "en"
        self.assertEqual(bot.L("hello", "مرحبا"), "hello")

    def test_ar_returns_second(self):
        bot.state["lang"] = "ar"
        self.assertEqual(bot.L("hello", "مرحبا"), "مرحبا")

    def test_missing_lang_defaults_to_en(self):
        bot.state.pop("lang", None)
        self.assertEqual(bot.L("en", "ar"), "en")


class TestHandleStateMutations(BotTestBase):
    def test_start_registers_chat_id(self):
        bot.state["chat_id"] = None
        bot.handle("/start", 4242)
        self.assertEqual(bot.state["chat_id"], 4242)
        self.assertIn("registered", self.last().lower())

    def test_stop_sets_paused(self):
        bot.state["paused"] = False
        bot.handle("/stop", 1)
        self.assertTrue(bot.state["paused"])
        self.assertIn("paused", self.last().lower())

    def test_resume_clears_paused(self):
        bot.state["paused"] = True
        bot.handle("/resume", 1)
        self.assertFalse(bot.state["paused"])
        self.assertIn("resumed", self.last().lower())

    def test_language_explicit_arabic(self):
        bot.state["lang"] = "en"
        bot.handle("/language ar", 1)
        self.assertEqual(bot.state["lang"], "ar")

    def test_language_explicit_english(self):
        bot.state["lang"] = "ar"
        bot.handle("/language en", 1)
        self.assertEqual(bot.state["lang"], "en")

    def test_language_toggles_when_no_arg(self):
        bot.state["lang"] = "en"
        bot.handle("/language", 1)
        self.assertEqual(bot.state["lang"], "ar")
        bot.handle("/language", 1)
        self.assertEqual(bot.state["lang"], "en")

    def test_arabic_alias_sets_arabic(self):
        bot.state["lang"] = "en"
        bot.handle("/arabic", 1)
        self.assertEqual(bot.state["lang"], "ar")


class TestHandleCity(BotTestBase):
    def test_city_without_arg_prompts_format(self):
        prev_city = bot.state.get("city")
        bot.handle("/city", 1)
        # Should not change the stored city, just show the expected format.
        self.assertEqual(bot.state.get("city"), prev_city)
        self.assertIn("Cairo, Egypt", self.last())

    def test_city_with_arg_parses_city_and_country(self):
        import datetime

        def fake_fetch():
            # Populate a fresh cache so the follow-up times_message() call in
            # handle() finds cached prayers and never hits the network.
            times = {"Fajr": "05:00", "Dhuhr": "12:00", "Asr": "15:30",
                     "Maghrib": "18:00", "Isha": "19:30"}
            bot.state["prayers"] = {"date": datetime.date.today().isoformat(),
                                    "times": times}
            return times

        bot.fetch_prayers = fake_fetch
        bot.handle("/city Cairo, Egypt", 1)
        self.assertEqual(bot.state["city"], "Cairo")
        self.assertEqual(bot.state["country"], "Egypt")
        self.assertIn("Cairo", self.last())


class TestHandleContentCommands(BotTestBase):
    """Read-only commands: assert they route to the right content block."""

    def test_today_sends_checklist(self):
        bot.handle("/today", 1)
        self.assertIn("Salah", self.last())

    def test_hadith_sends_nawawi(self):
        bot.handle("/hadith", 1)
        self.assertIn("Nawawi", self.last())

    def test_friday_sends_kahf(self):
        bot.handle("/friday", 1)
        self.assertIn("Al-Kahf", self.last())

    def test_fasting_lists_mondays(self):
        bot.state["hijri"] = {}
        bot.handle("/fasting", 1)
        self.assertIn("Mondays", self.last())

    def test_fast_alias_routes_to_fasting(self):
        bot.state["hijri"] = {}
        bot.handle("/fast", 1)
        self.assertIn("Mondays", self.last())

    def test_dua_sends_supplication(self):
        bot.handle("/dua", 1)
        self.assertIn("🤲", self.last())

    def test_tip_sends_tip(self):
        bot.handle("/tip", 1)
        self.assertIn("🌿", self.last())

    def test_help_lists_commands(self):
        bot.handle("/help", 1)
        self.assertIn("/city", self.last())

    def test_unknown_command_falls_back(self):
        bot.handle("/wat", 1)
        self.assertIn("recognise", self.last().lower())

    def test_message_is_addressed_to_sender(self):
        # handle() must pass the caller's chat_id through to send().
        bot.handle("/help", 9999)
        self.assertEqual(self.last_chat(), 9999)


class TestOwnerAndParsing(BotTestBase):
    def test_other_chat_cannot_take_over(self):
        bot.state["chat_id"] = 111
        bot.handle("/start", 222)
        self.assertEqual(bot.state["chat_id"], 111)
        self.assertIn("private", self.last().lower())

    def test_other_chat_cannot_pause(self):
        bot.state["chat_id"] = 111
        bot.state["paused"] = False
        bot.handle("/stop", 222)
        self.assertFalse(bot.state["paused"])

    def test_other_chat_can_read_content(self):
        bot.state["chat_id"] = 111
        bot.handle("/today", 222)
        self.assertIn("Salah", self.last())

    def test_owner_matches_string_chat_id(self):
        bot.state["chat_id"] = "111"  # CHAT_ID env values may be strings
        bot.handle("/stop", 111)
        self.assertTrue(bot.state["paused"])

    def test_bot_username_suffix_is_ignored(self):
        bot.state["chat_id"] = None
        prev = bot.state.get("city")
        bot.handle("/city@SunnahBot", 1)
        self.assertEqual(bot.state.get("city"), prev)
        self.assertIn("Cairo, Egypt", self.last())

    def test_non_text_message_is_ignored(self):
        bot.handle("", 1)
        bot.handle(None, 1)
        self.assertEqual(self.sent, [])


class TestTimezone(BotTestBase):
    def test_now_local_uses_city_timezone(self):
        bot.state["tz"] = "Asia/Tokyo"
        self.assertEqual(bot.now_local().utcoffset(), datetime.timedelta(hours=9))

    def test_bad_timezone_falls_back(self):
        bot.state["tz"] = "Not/AZone"
        self.assertIsNotNone(bot.now_local())

    def test_stale_hijri_is_ignored(self):
        bot.state["tz"] = None
        bot.state["hijri"] = {"day": 13, "month": 3, "date": "2000-01-01"}
        self.assertEqual(bot.hijri_today(), {})
        bot.state["hijri"]["date"] = datetime.date.today().isoformat()
        self.assertEqual(bot.hijri_today()["day"], 13)


class TestScheduler(BotTestBase):
    def setUp(self):
        super().setUp()
        bot.state.update({"chat_id": 1, "paused": False, "tz": None,
                          "sent_date": "", "sent_today": [], "hijri": {}})
        self.today = datetime.date.today()
        bot.state["prayers"] = {"date": self.today.isoformat(),
                                "times": {"Fajr": "05:00", "Dhuhr": "12:00", "Asr": "15:30",
                                          "Maghrib": "18:00", "Isha": "19:30"}}

    def at(self, hhmm):
        h, m = map(int, hhmm.split(":"))
        return datetime.datetime.combine(self.today, datetime.time(h, m, 30))

    def test_prayer_reminder_fires_once(self):
        bot.scheduler_tick(self.at("12:00"))
        self.assertIn("Dhuhr", self.last())
        n = len(self.sent)
        bot.scheduler_tick(self.at("12:01"))
        self.assertEqual(len(self.sent), n)

    def test_failed_send_is_retried(self):
        bot.send = lambda text, chat_id=None: False  # Telegram unreachable
        bot.scheduler_tick(self.at("12:00"))
        self.assertNotIn("salah_Dhuhr", bot.state["sent_today"])

    def test_nothing_sent_when_paused(self):
        bot.state["paused"] = True
        bot.scheduler_tick(self.at("12:00"))
        self.assertEqual(self.sent, [])

    def test_white_day_occasion(self):
        bot.state["hijri"] = {"day": 13, "month": 3, "date": self.today.isoformat()}
        bot.scheduler_tick(self.at(bot.HADITH_TIME))
        self.assertTrue(any("White Day" in t for t, _ in self.sent))


class TestMarkdownEscaping(BotTestBase):
    def test_md_escapes_markdown_characters(self):
        self.assertEqual(bot.md("St_Albans*[x]`"), "St\\_Albans\\*\\[x]\\`")

    def test_city_reply_escapes_user_text(self):
        bot.state["chat_id"] = None
        bot.handle("/city Some_Town", 1)  # fetch stubbed to fail
        self.assertIn("Some\\_Town", self.last())


class TestFetchPrayers(BotTestBase):
    def test_detects_city_timezone(self):
        import unittest.mock as mock
        payload = {"code": 200, "data": {
            "timings": {"Fajr": "05:00 (JST)", "Dhuhr": "11:45", "Asr": "15:00",
                        "Maghrib": "17:40", "Isha": "19:00"},
            "date": {"hijri": {"day": "13", "month": {"number": 3, "en": "Rabi"}, "year": "1448"}},
            "meta": {"timezone": "Asia/Tokyo"}}}
        bot.fetch_prayers = self._orig_fetch
        bot.state.update({"city": "Tokyo", "country": "Japan", "tz": None})
        with mock.patch.object(bot.requests, "get") as get:
            get.return_value.json.return_value = payload
            times = bot.fetch_prayers()
        self.assertEqual(times["Fajr"], "05:00")
        self.assertEqual(bot.state["tz"], "Asia/Tokyo")
        self.assertEqual(bot.state["hijri"]["day"], 13)


class TestSend(unittest.TestCase):
    def test_markdown_error_resends_as_plain_text(self):
        calls = []

        def fake_api(method, **params):
            calls.append(params)
            if "parse_mode" in params:
                return {"ok": False, "error_code": 400,
                        "description": "Bad Request: can't parse entities"}
            return {"ok": True}

        orig = bot.api
        bot.api = fake_api
        try:
            bot.send("city_with_underscore", chat_id=5)
        finally:
            bot.api = orig
        self.assertEqual(len(calls), 2)
        self.assertNotIn("parse_mode", calls[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)

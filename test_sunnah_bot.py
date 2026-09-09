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
        bot.send = lambda text, chat_id=None: self.sent.append((text, chat_id))
        bot.save_json = lambda *a, **k: None  # never touch state.json on disk

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

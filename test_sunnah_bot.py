#!/usr/bin/env python3
"""
Behaviour tests for the Sunnah Companion bot.

These tests are hermetic: no network, no disk. They set a dummy BOT_TOKEN in
the environment *before* import (env wins over config.json), then stub out
`send`, the storage, and `fetch_prayers` so nothing leaves the process.

Run:  python test_sunnah_bot.py       (or: python -m pytest -q)
"""
import datetime
import io
import json
import os
import sys
import tempfile
import types
import unittest
import unittest.mock as mock
from contextlib import redirect_stdout

# Env must be set before importing the bot: the module reads its token at import
# time and raises SystemExit if none is found.
os.environ.setdefault("BOT_TOKEN", "TESTING:dummy-token")
for k in ("CHAT_ID", "DATABASE_URL", "PORT"):
    os.environ.pop(k, None)

import sunnah_bot as bot  # noqa: E402

TODAY = datetime.date.today()
TIMES = {"Fajr": "05:00", "Dhuhr": "12:00", "Asr": "15:30", "Maghrib": "18:00", "Isha": "19:30"}


class BotTestBase(unittest.TestCase):
    """Fresh in-memory database per test; I/O seams stubbed and restored."""

    def setUp(self):
        self._orig = {n: getattr(bot, n) for n in
                      ("send", "fetch_prayers", "store", "db", "SEND_INTERVAL", "state")}
        self.sent = []  # list of (text, chat_id)
        bot.send = lambda text, chat_id=None, **kw: self.sent.append((text, chat_id or bot.state["chat_id"])) or True
        bot.fetch_prayers = lambda *a, **k: None          # never hit the Aladhan API
        bot.store = mock.Mock()                           # never touch disk / Postgres
        bot.db = {"last_update_id": 0, "users": {}, "dispatch": {}}
        bot.SEND_INTERVAL = 0
        bot.PRAYER_CACHE.clear()
        bot._fetch_fail.clear()
        bot._late.clear()
        bot._last_round = None
        self.u = bot.use(bot.register(bot.new_user(1)))
        self.u["lang"] = "en"

    def tearDown(self):
        for n, v in self._orig.items():
            setattr(bot, n, v)
        bot.PRAYER_CACHE.clear()

    def seed_times(self, times=TIMES, hijri=None, method="Moonsighting Committee Worldwide"):
        """Put today's prayer times for the current user into the cache."""
        key = bot.settings_key() + (bot.today_local().isoformat(),)
        bot.PRAYER_CACHE[key] = {"times": dict(times), "hijri": hijri or {}, "method": method}

    def last(self):
        self.assertTrue(self.sent, "expected the bot to send a message")
        return self.sent[-1][0]

    def last_chat(self):
        self.assertTrue(self.sent, "expected the bot to send a message")
        return self.sent[-1][1]

    def ledger(self):
        """Today's dispatch row as /health reports it."""
        today = bot.utc_today().isoformat()
        return bot.dispatch_report().get(today) or {"totals": {}, "reminders": {}}

    def counts(self, key):
        return self.ledger()["reminders"].get(key, {})


class TestL(BotTestBase):
    def test_en_returns_first(self):
        self.assertEqual(bot.L("hello", "مرحبا"), "hello")

    def test_ar_returns_second(self):
        bot.state["lang"] = "ar"
        self.assertEqual(bot.L("hello", "مرحبا"), "مرحبا")


class TestManyUsers(BotTestBase):
    def test_anyone_can_start(self):
        bot.handle("/start", 4242)
        self.assertIn("4242", bot.db["users"])
        self.assertIn("registered", self.last().lower())
        self.assertEqual(self.last_chat(), 4242)

    def test_users_have_separate_settings(self):
        self.seed_times()
        bot.handle("/city Cairo, Egypt", 1)
        bot.handle("/language ar", 2)
        self.assertEqual(bot.db["users"]["1"]["city"], "Cairo")
        self.assertEqual(bot.db["users"]["1"]["lang"], "en")
        self.assertEqual(bot.db["users"]["2"]["lang"], "ar")
        self.assertEqual(bot.db["users"]["2"]["city"], "")

    def test_times_never_shows_someone_elses_city(self):
        self.u["city"] = "Secretville"
        bot.handle("/times", 77)
        self.assertNotIn("Secretville", self.last())
        self.assertIn("/location", self.last())

    def test_reading_content_does_not_register(self):
        bot.handle("/hadith", 55)
        self.assertNotIn("55", bot.db["users"])

    def test_stop_and_resume_are_per_user(self):
        bot.handle("/start", 2)
        bot.handle("/stop", 2)
        self.assertTrue(bot.db["users"]["2"]["paused"])
        self.assertFalse(bot.db["users"]["1"]["paused"])
        bot.handle("/resume", 2)
        self.assertFalse(bot.db["users"]["2"]["paused"])

    def test_forget_deletes_user(self):
        bot.handle("/forget", 1)
        self.assertNotIn("1", bot.db["users"])
        self.assertIn("deleted", self.last())

    def test_message_from_blocked_user_unblocks(self):
        self.u["blocked"] = True
        bot.handle("/help", 1)
        self.assertFalse(self.u["blocked"])

    def test_language_explicit_and_toggle(self):
        bot.handle("/language ar", 1)
        self.assertEqual(self.u["lang"], "ar")
        bot.handle("/language en", 1)
        self.assertEqual(self.u["lang"], "en")
        bot.handle("/language", 1)
        self.assertEqual(self.u["lang"], "ar")
        bot.handle("/english", 1)
        self.assertEqual(self.u["lang"], "en")


class TestHandleParsing(BotTestBase):
    def test_city_without_arg_prompts_format(self):
        bot.handle("/city", 1)
        self.assertEqual(self.u["city"], "")
        self.assertIn("Cairo, Egypt", self.last())

    def test_city_too_long_is_rejected(self):
        bot.handle("/city " + "x" * 500, 1)
        self.assertEqual(self.u["city"], "")

    def test_city_with_arg_parses_city_and_country(self):
        def fake_fetch():
            self.seed_times()
            return TIMES
        bot.fetch_prayers = fake_fetch
        bot.handle("/city Cairo, Egypt", 1)
        self.assertEqual((self.u["city"], self.u["country"]), ("Cairo", "Egypt"))
        self.assertIn("Location set to *Cairo*", self.last())
        self.assertIn("Dhuhr", self.last())

    def test_bot_username_suffix_is_ignored(self):
        bot.handle("/help@SunnahBot", 1)
        self.assertIn("/city", self.last())

    def test_non_text_message_is_ignored(self):
        bot.handle("", 1)
        bot.handle(None, 1)
        self.assertEqual(self.sent, [])

    def test_unknown_command_falls_back(self):
        bot.handle("/wat", 1)
        self.assertIn("recognise", self.last().lower())

    def test_parse_int_rejects_odd_numbers(self):
        self.assertEqual(bot.parse_int("+3"), 3)
        self.assertEqual(bot.parse_int("-2"), -2)
        for bad in ("²", "+-5", "", "3.5", "99999"):
            self.assertIsNone(bot.parse_int(bad), bad)


class TestContentCommands(BotTestBase):
    def test_routes(self):
        for cmd, expect in [("/today", "Salah"), ("/hadith", "Nawawi"), ("/friday", "Al-Kahf"),
                            ("/fasting", "Mondays"), ("/fast", "Mondays"), ("/dua", "🤲"),
                            ("/tip", "🌿"), ("/help", "/forget")]:
            bot.handle(cmd, 1)
            self.assertIn(expect, self.last(), cmd)

    def test_fasting_escapes_hijri_month(self):
        self.u["city"] = "Cairo"
        self.seed_times(hijri={"day": 5, "month": 3, "monthName": "Rabi_al", "year": "1448"})
        bot.handle("/fasting", 1)
        self.assertIn("Rabi\\_al", self.last())


class TestTimezone(BotTestBase):
    def test_now_local_uses_user_timezone(self):
        self.u["tz"] = "Asia/Tokyo"
        self.assertEqual(bot.now_local().utcoffset(), datetime.timedelta(hours=9))

    def test_bad_timezone_falls_back(self):
        self.u["tz"] = "Not/AZone"
        self.assertIsNotNone(bot.now_local())


class TestScheduler(BotTestBase):
    def setUp(self):
        super().setUp()
        self.u.update({"city": "Bristol", "country": "United Kingdom"})
        self.seed_times()

    def at(self, hhmm):
        return datetime.datetime.combine(TODAY, datetime.time.fromisoformat(hhmm + ":30"))

    def test_prayer_reminder_fires_once(self):
        bot.scheduler_tick(self.at("12:00"))
        self.assertIn("Dhuhr", self.last())
        n = len(self.sent)
        bot.scheduler_tick(self.at("12:01"))
        self.assertEqual(len(self.sent), n)

    def test_failed_send_is_retried(self):
        bot.send = lambda *a, **k: False  # Telegram unreachable
        bot.scheduler_tick(self.at("12:00"))
        self.assertNotIn("salah_Dhuhr", self.u["sent_today"])

    def test_nothing_sent_when_paused(self):
        self.u["paused"] = True
        bot.scheduler_tick(self.at("12:00"))
        self.assertEqual(self.sent, [])

    def test_white_day_occasion(self):
        self.seed_times(hijri={"day": 13, "month": 3})
        bot.scheduler_tick(self.at(bot.HADITH_TIME))
        self.assertTrue(any("White Day" in t for t, _ in self.sent))

    def test_tick_all_serves_every_user_in_their_language(self):
        ar = bot.use(bot.register(bot.new_user(2)))
        ar.update({"lang": "ar", "sent_date": TODAY.isoformat()})
        blocked = bot.register(bot.new_user(3))
        blocked["blocked"] = True
        with mock.patch.object(bot, "now_local", return_value=self.at(bot.MORNING)):
            bot.scheduler_tick_all()
        by_chat = {c: t for t, c in self.sent}
        self.assertIn("Morning", by_chat[1])
        self.assertIn("أذكار الصباح", by_chat[2])
        self.assertNotIn(3, by_chat)


class TestDispatchLedger(BotTestBase):
    """The evidence the daily health check reads: every fire is counted, and a
    reminder that never went out is counted too."""

    def setUp(self):
        super().setUp()
        self.u.update({"city": "Bristol", "country": "United Kingdom"})
        self.seed_times()

    def at(self, hhmm, sec=30):
        return datetime.datetime.combine(TODAY, datetime.time.fromisoformat(f"{hhmm}:{sec:02d}"))

    def test_a_sent_reminder_is_counted_with_its_lateness(self):
        bot.scheduler_tick(self.at("12:00"))
        c = self.counts("salah_Dhuhr")
        self.assertEqual((c["sent"], c["failed"], c["dupe"], c["missed"]), (1, 0, 0, 0))
        self.assertEqual(c["late_max_s"], 30)   # fired 30s past the scheduled minute

    def test_a_failed_send_is_counted_and_not_marked_sent(self):
        bot.send = lambda *a, **k: False
        bot.scheduler_tick(self.at("12:00"))
        c = self.counts("salah_Dhuhr")
        self.assertEqual((c["sent"], c["failed"]), (0, 1))
        self.assertNotIn("salah_Dhuhr", self.u["sent_today"])

    def test_a_closed_send_window_is_counted_as_missed(self):
        bot.scheduler_tick(self.at("12:05"))   # window is 12:00–12:03
        self.assertEqual(self.sent, [])
        self.assertEqual(self.counts("salah_Dhuhr")["missed"], 1)

    def test_a_missed_reminder_is_only_counted_once(self):
        bot.scheduler_tick(self.at("12:05"))
        bot.scheduler_tick(self.at("12:06"))
        bot.scheduler_tick(self.at("12:20"))
        self.assertEqual(self.counts("salah_Dhuhr")["missed"], 1)

    def test_long_past_reminders_are_not_counted_as_missed(self):
        # Someone who starts the bot in the afternoon was never owed Fajr.
        bot.scheduler_tick(self.at("13:00"))
        self.assertEqual(self.ledger()["reminders"], {})

    def test_a_second_send_of_the_same_reminder_is_counted_as_a_duplicate(self):
        bot.remind("morning", "first")
        bot.remind("morning", "second")   # only reachable if a caller skips due()
        c = self.counts("morning")
        self.assertEqual((c["sent"], c["dupe"]), (2, 1))

    def test_dispatch_stays_idempotent_across_ticks(self):
        for sec in (0, 30, 59):
            bot.scheduler_tick(self.at("12:00", sec))
        bot.scheduler_tick(self.at("12:02"))
        self.assertEqual(len(self.sent), 1)
        c = self.counts("salah_Dhuhr")
        self.assertEqual((c["sent"], c["dupe"], c["missed"]), (1, 0, 0))

    def test_nothing_to_say_today_is_not_counted_as_a_fire(self):
        self.seed_times(hijri={"day": 5, "month": 3})   # no fasting occasion
        bot.scheduler_tick(self.at(bot.HADITH_TIME))
        self.assertEqual(self.counts("occasion"), {})

    def test_a_scheduler_gap_is_recorded(self):
        with mock.patch.object(bot.time, "monotonic", side_effect=[0.0, 900.0, 900.0]):
            bot.scheduler_tick_all()
            bot.scheduler_tick_all()
        totals = self.ledger()["totals"]
        self.assertEqual(totals["gaps"], 1)
        self.assertEqual(totals["gap_max_s"], 900)

    def test_the_ledger_never_holds_a_chat_id(self):
        loud = bot.use(bot.register(bot.new_user(987654321)))
        loud.update({"lang": "en", "city": "Bristol", "country": "United Kingdom"})
        self.seed_times()
        bot.scheduler_tick(self.at("12:00"))
        self.assertNotIn("987654321", json.dumps(bot.db["dispatch"]))

    def test_old_days_are_pruned(self):
        old = (bot.utc_today() - datetime.timedelta(days=30)).isoformat()
        keep = (bot.utc_today() - datetime.timedelta(days=2)).isoformat()
        bot.db["dispatch"] = {old: {"reminders": {}}, keep: {"reminders": {}}}
        bot.dispatch_day()   # creating today's row prunes
        self.assertNotIn(old, bot.db["dispatch"])
        self.assertIn(keep, bot.db["dispatch"])


class TestDispatchVerdict(BotTestBase):
    """Pass/fail the daily health check reads straight off /health."""

    def today(self):
        return bot.utc_today()

    def test_a_clean_day_passes(self):
        bot.dispatch_record("morning", "sent", 12)
        v = bot.dispatch_verdict(self.today())
        self.assertTrue(v["pass"], v["fail"])
        self.assertEqual(v["fail"], [])

    def test_a_missed_reminder_fails(self):
        bot.dispatch_record("morning", "sent")
        bot.dispatch_record("salah_Asr", "missed")
        v = bot.dispatch_verdict(self.today())
        self.assertFalse(v["pass"])
        self.assertTrue(any("never went out" in r for r in v["fail"]))

    def test_a_duplicate_fails(self):
        bot.dispatch_record("morning", "sent")
        bot.dispatch_record("morning", "dupe")
        self.assertFalse(bot.dispatch_verdict(self.today())["pass"])

    def test_a_long_scheduler_gap_fails(self):
        bot.dispatch_record("morning", "sent")
        bot.dispatch_note("gap_max_s", bot.MAX_GAP_SECONDS + 1)
        self.assertFalse(bot.dispatch_verdict(self.today())["pass"])

    def test_a_silent_day_with_active_users_fails(self):
        v = bot.dispatch_verdict(self.today())   # no row at all
        self.assertFalse(v["pass"])
        self.assertTrue(any("no dispatch recorded" in r for r in v["fail"]))

    def test_a_silent_day_with_no_active_users_passes(self):
        self.u["paused"] = True
        self.assertTrue(bot.dispatch_verdict(self.today())["pass"])

    def test_a_retried_send_warns_but_passes(self):
        bot.dispatch_record("morning", "failed")
        bot.dispatch_record("morning", "sent")
        v = bot.dispatch_verdict(self.today())
        self.assertTrue(v["pass"], v["fail"])
        self.assertTrue(any("retried" in w for w in v["warn"]))

    def test_a_prayer_times_outage_warns_but_passes(self):
        bot.dispatch_record("morning", "sent")
        bot.dispatch_note("prayers_unavailable")
        v = bot.dispatch_verdict(self.today())
        self.assertTrue(v["pass"], v["fail"])
        self.assertTrue(any("prayer times" in w for w in v["warn"]))

    def test_a_prayer_times_outage_is_recorded_from_a_failed_fetch(self):
        self.u.update({"city": "Bristol", "country": "United Kingdom"})

        def failing_fetch():
            bot._fetch_fail[bot.settings_key()] = bot.time.time()
            return None

        bot.fetch_prayers = failing_fetch
        bot.scheduler_tick(datetime.datetime.combine(TODAY, datetime.time(12, 0, 30)))
        self.assertEqual(self.ledger()["totals"]["prayers_unavailable"], 1)


class TestHealthEndpoint(BotTestBase):
    def test_root_stays_a_plain_liveness_reply(self):
        status, ctype, body = bot.health_response("/")
        self.assertEqual(status, 200)
        self.assertIn("text/plain", ctype)
        self.assertIn(b"alive", body)

    def test_health_returns_the_ledger_as_json(self):
        bot.dispatch_record("morning", "sent", 5)
        status, ctype, body = bot.health_response("/health")
        self.assertEqual(status, 200)
        self.assertIn("application/json", ctype)
        payload = json.loads(body)
        self.assertEqual(payload["users_active"], 1)
        self.assertEqual(payload["late_window_s"], bot.LATE_WINDOW_MINUTES * 60)
        self.assertIn("verdict", payload)
        today = bot.utc_today().isoformat()
        self.assertEqual(payload["dispatch"][today]["reminders"]["morning"]["sent"], 1)

    def test_health_is_hidden_without_the_token_when_one_is_set(self):
        with mock.patch.object(bot, "HEALTH_TOKEN", "s3cret"):
            self.assertEqual(bot.health_response("/health")[0], 404)
            self.assertEqual(bot.health_response("/health?token=wrong")[0], 404)
            self.assertEqual(bot.health_response("/health?token=s3cret")[0], 200)

    def test_a_broken_report_does_not_break_the_probe(self):
        with mock.patch.object(bot, "dispatch_report", side_effect=RuntimeError("boom")):
            with redirect_stdout(io.StringIO()):
                status, _, body = bot.health_response("/health")
        self.assertEqual(status, 503)       # never silently looks like a pass
        self.assertEqual(json.loads(body), {"error": "RuntimeError"})


class TestSend(BotTestBase):
    def setUp(self):
        super().setUp()
        bot.send = self._orig["send"]
        self.calls = []

    def fake_api(self, *responses):
        it = iter(responses)

        def api(method, **params):
            self.calls.append(params)
            return next(it)
        return mock.patch.object(bot, "api", api)

    def test_markdown_error_resends_as_plain_text(self):
        with self.fake_api({"ok": False, "error_code": 400, "description": "Bad Request: can't parse entities"},
                           {"ok": True}):
            self.assertTrue(bot.send("city_with_underscore", chat_id=5))
        self.assertNotIn("parse_mode", self.calls[1])

    def test_blocked_user_is_marked(self):
        with self.fake_api({"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}):
            self.assertFalse(bot.send("hi"))
        self.assertTrue(self.u["blocked"])

    def test_rate_limit_waits_and_retries(self):
        with self.fake_api({"ok": False, "error_code": 429, "parameters": {"retry_after": 2}}, {"ok": True}), \
                mock.patch.object(bot.time, "sleep") as sleep:
            self.assertTrue(bot.send("hi"))
        sleep.assert_called_once_with(2)


class TestMarkdownEscaping(BotTestBase):
    def test_md_escapes_markdown_characters(self):
        self.assertEqual(bot.md("St_Albans*[x]`"), "St\\_Albans\\*\\[x]\\`")

    def test_city_reply_escapes_user_text(self):
        bot.handle("/city Some_Town", 1)  # fetch stubbed to fail
        self.assertIn("Some\\_Town", self.last())


class TestFetchPrayers(BotTestBase):
    PAYLOAD = {"code": 200, "data": {
        "timings": {"Fajr": "05:00 (JST)", "Dhuhr": "11:45", "Asr": "15:00", "Maghrib": "17:40", "Isha": "19:00"},
        "date": {"hijri": {"day": "13", "month": {"number": 3, "en": "Rabi"}, "year": "1448"}},
        "meta": {"timezone": "Asia/Tokyo", "method": {"name": "Muslim World League"}}}}

    def setUp(self):
        super().setUp()
        bot.fetch_prayers = self._orig["fetch_prayers"]
        self.u.update({"city": "Tokyo", "country": "Japan"})

    def test_detects_timezone(self):
        with mock.patch.object(bot.requests, "get") as get:
            get.return_value.json.return_value = self.PAYLOAD
            times = bot.fetch_prayers()
        self.assertEqual(times["Fajr"], "05:00")
        self.assertEqual(self.u["tz"], "Asia/Tokyo")

    def test_caches_times_and_hijri(self):
        self.u["tz"] = "Asia/Tokyo"   # known already, so the date can't shift mid-test
        with mock.patch.object(bot.requests, "get") as get:
            get.return_value.json.return_value = self.PAYLOAD
            bot.fetch_prayers()
        self.assertEqual(bot.hijri_today()["day"], 13)
        self.assertEqual(bot.ensure_prayers()["Maghrib"], "17:40")

    def test_same_city_shares_one_request(self):
        with mock.patch.object(bot.requests, "get") as get:
            get.return_value.json.return_value = self.PAYLOAD
            self.u["tz"] = "Asia/Tokyo"
            bot.ensure_prayers()
            other = bot.use(bot.new_user(2))
            other.update({"city": "tokyo", "country": "japan", "tz": self.u["tz"]})
            self.assertEqual(bot.ensure_prayers()["Isha"], "19:00")
        self.assertEqual(get.call_count, 1)

    def test_cached_place_still_sets_timezone(self):
        self.u["tz"] = "Asia/Tokyo"
        with mock.patch.object(bot.requests, "get") as get:
            get.return_value.json.return_value = self.PAYLOAD
            bot.ensure_prayers()
        cached_day = datetime.date.fromisoformat(next(iter(bot.PRAYER_CACHE))[-1])
        # Someone who just moved here from London; Tokyo is already cached.
        traveller = bot.use(bot.new_user(2))
        traveller.update({"city": "Tokyo", "country": "Japan", "tz": "Europe/London"})
        with mock.patch.object(bot.requests, "get") as get, \
                mock.patch.object(bot, "today_local", return_value=cached_day):
            bot.ensure_prayers()
        get.assert_not_called()
        self.assertEqual(traveller["tz"], "Asia/Tokyo")

    def test_malformed_times_are_rejected(self):
        bad = {"code": 200, "data": dict(self.PAYLOAD["data"], timings={"Fajr": "5:3x"})}
        with mock.patch.object(bot.requests, "get") as get:
            get.return_value.json.return_value = bad
            self.assertIsNone(bot.fetch_prayers())
        self.assertEqual(bot.PRAYER_CACHE, {})

    def test_errors_do_not_log_location(self):
        self.u.update({"city": "PrivateTown"})
        out = io.StringIO()
        with mock.patch.object(bot.requests, "get", side_effect=Exception("url ?city=PrivateTown")), \
                redirect_stdout(out):
            bot.fetch_prayers()
        self.assertNotIn("PrivateTown", out.getvalue())


class TestPrayerAccuracy(BotTestBase):
    def setUp(self):
        super().setUp()
        self.u.update({"city": "Bristol", "country": "United Kingdom"})
        self.day = datetime.date(2026, 9, 25)

    def test_uk_city_uses_moonsighting_committee(self):
        url, params = bot.prayer_request(self.day)
        self.assertIn("timingsByCity/25-09-2026", url)
        self.assertEqual((params["method"], params["school"]), (15, 0))

    def test_pakistan_defaults_to_karachi_and_hanafi(self):
        self.u["country"] = "Pakistan"
        _, params = bot.prayer_request(self.day)
        self.assertEqual((params["method"], params["school"]), (1, 1))

    def test_unknown_country_lets_aladhan_pick(self):
        self.u["country"] = "Atlantis"
        self.assertNotIn("method", bot.prayer_request(self.day)[1])

    def test_shared_location_is_rounded_and_registers(self):
        bot.process_update({"message": {"chat": {"id": 9}, "location": {"latitude": 51.45451, "longitude": -2.58791}}})
        u = bot.db["users"]["9"]
        self.assertEqual((u["lat"], u["lng"]), (51.45, -2.59))
        url, params = bot.prayer_request(self.day)
        self.assertIn("/timings/25-09-2026", url)

    def test_city_clears_shared_location(self):
        self.u.update({"lat": 1.0, "lng": 2.0})
        bot.handle("/city Cairo, Egypt", 1)
        self.assertIsNone(self.u["lat"])
        self.assertEqual(bot.prayer_request(self.day)[1]["method"], 5)

    def test_method_and_asr(self):
        bot.handle("/method 3", 1)
        self.assertEqual(bot.prayer_request(self.day)[1]["method"], 3)
        bot.handle("/method 0", 1)
        self.assertEqual(bot.prayer_request(self.day)[1]["method"], 15)
        bot.handle("/asr hanafi", 1)
        self.assertEqual(bot.prayer_request(self.day)[1]["school"], 1)

    def test_adjust(self):
        bot.handle("/adjust maghrib +3", 1)
        bot.handle("/adjust Fajr -2", 1)
        self.assertEqual(bot.apply_offsets({"Fajr": "05:00", "Maghrib": "18:59", "Isha": "20:00"}),
                         {"Fajr": "04:58", "Maghrib": "19:02", "Isha": "20:00"})
        bot.handle("/adjust lunch 5", 1)
        bot.handle("/adjust fajr 500", 1)
        self.assertEqual(self.u["offsets"], {"Fajr": -2, "Maghrib": 3})
        bot.handle("/adjust reset", 1)
        self.assertEqual(self.u["offsets"], {})


class TestStorage(unittest.TestCase):
    def test_old_single_user_state_is_migrated(self):
        db = bot.load_db({"chat_id": 42, "city": "Cairo", "lang": "ar", "last_update_id": 7,
                          "prayers": {"date": "x"}})
        self.assertEqual(db["last_update_id"], 7)
        u = db["users"]["42"]
        self.assertEqual((u["city"], u["lang"], u["chat_id"]), ("Cairo", "ar", 42))
        self.assertNotIn("prayers", u)
        self.assertEqual(u["offsets"], {})

    def test_file_store_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            s = bot.FileStore(os.path.join(d, "state.json"))
            self.assertIsNone(s.load())
            s.save('{"users": {}, "last_update_id": 3}')
            self.assertEqual(s.load()["last_update_id"], 3)

    def test_postgres_store(self):
        rows = {}

        class Conn:
            closed = False

            def execute(self, sql, params=None):
                if sql.startswith("INSERT"):
                    rows[1] = params[0]
                return mock.Mock(fetchone=lambda: (rows[1],) if 1 in rows else None)

        fake = types.SimpleNamespace(connect=lambda *a, **k: Conn(), OperationalError=RuntimeError)
        with mock.patch.dict(sys.modules, {"psycopg": fake}):
            s = bot.PostgresStore("postgres://example")
            self.assertIsNone(s.load())
            s.save('{"users": {}, "last_update_id": 5}')
            self.assertEqual(s.load()["last_update_id"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

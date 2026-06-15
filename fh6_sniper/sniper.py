from __future__ import annotations
import logging
import random
import time
from . import actions, capture, vision
from .vision import Screen

log = logging.getLogger("fh6.sniper")


def _names(screens) -> str:
    return "{" + ", ".join(sorted(s.name for s in screens)) + "}"


class GameIO:

    def __init__(self, cfg, templates):
        self.cfg = cfg
        self.templates = templates
        self._last_screen = None
        self._memo_fid = None
        self._memo: dict = {}

    def _read(self, key, fn):
        frame, fid = capture.latest_frame(self.cfg.window_title)
        if fid != self._memo_fid:
            self._memo_fid = fid
            self._memo = {}
        if key not in self._memo:
            self._memo[key] = fn(frame)
        return self._memo[key]

    def await_new_frame(self, timeout: float = 0.15) -> bool:
        start = capture.frame_id()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if capture.frame_id() != start:
                return True
            time.sleep(0.002)
        return False

    def screen(self, targets=None) -> Screen:
        if (targets is not None and self._last_screen is not None
                and self._last_screen != Screen.UNKNOWN):
            targets = targets | {self._last_screen}
        key = ("screen", frozenset(targets) if targets is not None else None)
        result = self._read(
            key,
            lambda f: vision.identify_screen(
                f, self.templates, self.cfg.match_threshold, targets=targets))
        if result != self._last_screen:
            log.info("screen -> %s", result.name)
            self._last_screen = result
        return result

    def focused(self) -> bool:
        return capture.is_game_focused(self.cfg.window_title)

    def confirm_highlighted(self) -> bool:
        return self._read("confirm", vision.is_confirm_highlighted)

    def card_sold(self) -> bool:
        return self._read("card_sold", vision.is_card_sold)

    def first_buyable_slot(self) -> int:
        return self._read("slot", vision.first_buyable_slot)

    def press(self, name: str, times: int = 1) -> None:
        log.info("press %s%s", name, f" x{times}" if times > 1 else "")
        actions.tap_key(name, times,
                        self.cfg.key_hold_ms, self.cfg.between_keys_ms)
        self._memo = {}
        self._memo_fid = None


class Sniper:

    def __init__(self, io, cfg, clock=time.monotonic, sleeper=time.sleep,
                 on_purchase=None, on_status=None, on_stats=None):
        self.io = io
        self.cfg = cfg
        self.clock = clock
        self.sleeper = sleeper
        self.on_purchase = on_purchase
        self.on_status = on_status
        self.on_stats = on_stats
        self.cars_bought    = 0
        self.searches       = 0
        self.failed_buyouts = 0
        self.started_at     = None
        self._stop = False
        self._jitter_up = True

    def request_stop(self) -> None:
        self._stop = True

    def _status(self, text: str) -> None:
        log.info("[status] %s", text)
        if self.on_status:
            self.on_status(text)

    def _emit_stats(self) -> None:
        if self.on_stats:
            self.on_stats(self.searches, self.cars_bought,
                          self.failed_buyouts)

    def _poll_delay(self) -> None:
        lo, hi = self.cfg.poll_interval_ms
        self.sleeper(random.uniform(lo, hi) / 1000.0)

    def _guard_focus(self) -> None:
        if self.io.focused():
            return
        self._status("Paused: FH6 not in foreground")
        while not self.io.focused():
            if self._stop:
                return
            self.sleeper(0.5)

    def _press(self, name: str, times: int = 1) -> None:
        self._guard_focus()
        if self._stop:
            return
        self.io.press(name, times)

    def wait_for(self, screens: set, timeout: float):
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            if self._stop:
                return None
            before = self.clock()
            self._guard_focus()
            if self._stop:
                return None
            deadline += self.clock() - before
            current = self.io.screen(targets=screens)
            if current in screens:
                log.info("wait %s -> %s", _names(screens), current.name)
                return current
            self._poll_delay()
        log.info("wait %s -> TIMEOUT after %.0fs", _names(screens), timeout)
        return None

    def _press_until(self, key, from_screen, targets,
                     settle: float = 0.7, reach: float = 8.0,
                     attempts: int = 4):
        inner_targets = targets | {from_screen}
        for _ in range(attempts):
            if self._stop:
                return None
            self._press(key)
            deadline = self.clock() + settle
            while self.clock() < deadline:
                if self._stop:
                    return None
                s = self.io.screen(targets=inner_targets)
                if s in targets:
                    return s
                if s != from_screen:
                    return self.wait_for(targets, reach)
                self._poll_delay()
        return None

    def _goto_search_config(self) -> bool:
        s = self.io.screen()
        for _ in range(10):
            if self._stop:
                return False
            if s == Screen.SEARCH_CONFIG:
                return True
            if s == Screen.AH_LANDING:
                return self._enter_search_from_landing(known=s)
            if s == Screen.UNKNOWN:
                self.sleeper(0.3)
                s = self.io.screen()
                continue
            self._press("esc")
            s = self._await_settle(prev=s)
        self._status("Lost: start the bot in the Auction House")
        return False

    def _enter_search_from_landing(self, known=None) -> bool:
        self._status("Opening Auction Search")
        for attempt in range(1, 5):
            if self._stop:
                return False
            s = known if known is not None else self.io.screen()
            known = None
            log.info("enter_search attempt %d: screen=%s", attempt, s.name)
            if s == Screen.SEARCH_CONFIG:
                return True
            if s == Screen.UNKNOWN:
                self.sleeper(0.6)
                continue
            if s != Screen.AH_LANDING:
                self._press("esc")
                self.sleeper(0.3)
                continue
            self.sleeper(0.2)
            self._press("enter")
            if self.wait_for({Screen.SEARCH_CONFIG}, 0.9) is not None:
                return True
        log.info("enter_search: gave up after 4 attempts")
        return False

    def _navigate_to_confirm(self) -> bool:
        for _ in range(12):
            if self._stop:
                return False
            if self.io.confirm_highlighted():
                return True
            self._press("down")
        return self.io.confirm_highlighted()

    def _jitter_max_bid(self) -> None:
        cfg = self.cfg
        if not getattr(cfg, "search_jitter_enabled", True):
            return
        if getattr(cfg, "jitter_maxbid", True):
            rows = 2
        elif getattr(cfg, "jitter_maxbuyout", False):
            rows = 1
        else:
            rows = 0
        if rows <= 0:
            return
        steps = max(1, int(getattr(cfg, "search_jitter_steps", 1)))
        direction = "right" if self._jitter_up else "left"
        sign = "+" if self._jitter_up else "-"
        try:
            self._status(f"Updating bid ({sign}{steps})")
            for _ in range(rows):
                if self._stop:
                    return
                self._press("up")
                self.sleeper(0.02)
            if self._stop:
                return
            self._press(direction, steps)
            self._jitter_up = not self._jitter_up
            self.sleeper(0.02)
            for _ in range(rows):
                if self._stop:
                    return
                self._press("down")
                self.sleeper(0.02)
        except Exception:
            log.exception(
                "jitter skipped: 'up'/'left'/'right' keys unavailable")
            try:
                cfg.search_jitter_enabled = False
            except Exception:
                pass

    def _recover(self) -> str:
        unknown_streak = 0
        s = self.io.screen()
        for _ in range(14):
            if self._stop:
                return "recover_failed"
            if s in (Screen.SEARCH_CONFIG, Screen.AH_LANDING):
                log.info("recover: reached %s", s.name)
                return "recovered"
            if s == Screen.BUYOUT_PROGRESS:
                self.sleeper(0.3)
                s = self.io.screen()
                continue
            if s in (Screen.BUYOUT_SUCCESS, Screen.CLAIM_CAR,
                     Screen.AUCTION_OPTIONS):
                self._press("enter")
                unknown_streak = 0
                s = self._await_settle(prev=s)
                continue
            if s == Screen.UNKNOWN:
                unknown_streak += 1
                if unknown_streak >= 4:
                    self._press("esc")
                    unknown_streak = 0
                    s = self._await_settle(prev=s)
                    continue
                self.sleeper(0.3)
                s = self.io.screen()
                continue
            unknown_streak = 0
            self._press("esc")
            s = self._await_settle(prev=s)
        log.info("recover: gave up")
        return "recover_failed"

    def _await_settle(self, prev, timeout: float = 1.2):
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            if self._stop:
                return Screen.UNKNOWN
            self._poll_delay()
            s = self.io.screen()
            if s != Screen.UNKNOWN and s != prev:
                return s
        return Screen.UNKNOWN

    def _back_to_landing(self, known=None) -> None:
        s = known if known is not None else self.io.screen()
        for _ in range(6):
            if self._stop:
                return
            if s == Screen.AH_LANDING:
                return
            if s == Screen.UNKNOWN:
                self.sleeper(0.3)
                s = self.io.screen()
                continue
            self._press("esc")
            s = self._await_settle(prev=s)

    def _escape_player_options(self) -> str:
        self._status("Listing already sold, skipping")
        for _ in range(6):
            if self._stop:
                return "recover_failed"
            if self.io.screen() == Screen.AH_LANDING:
                return "no_cars"
            self._press("esc")
            self.sleeper(0.6)
        return "no_cars"

    def _collect(self) -> bool:
        self._status("Collecting the car")
        if self.wait_for({Screen.AUCTION_OPTIONS, Screen.CLAIM_CAR},
                         getattr(self.cfg, "buyout_open_wait_s", 2.5)) is None:
            return False
        if self.io.screen() != Screen.CLAIM_CAR:
            if self._press_until("enter", Screen.AUCTION_OPTIONS,
                                 {Screen.CLAIM_CAR}) is None:
                return False
        deadline = self.clock() + self.cfg.timeout_claim_s
        claimed = False
        while self.clock() < deadline:
            if self._stop:
                return claimed
            s = self.io.screen()
            if s == Screen.CLAIM_CAR:
                self._press("enter")
                claimed = True
                self.sleeper(getattr(self.cfg, "collect_claim_wait_s", 0.2))
            elif s == Screen.UNKNOWN:
                self.sleeper(getattr(self.cfg, "collect_unknown_wait_s", 0.1))
            else:
                return claimed
        return claimed

    def run_once(self) -> str:
        log.info("--- run_once ---")
        cfg = self.cfg
        t_start = self.clock()
        if not self._goto_search_config():
            return "recover_failed"

        self._status("Searching")
        if not self._navigate_to_confirm():
            return self._recover()
        self._jitter_max_bid()
        if self._stop:
            return self._recover()
        t_query = self.clock()
        log.info("time: open search %.0f ms", (t_query - t_start) * 1000)
        result = self._press_until(
            "enter", Screen.SEARCH_CONFIG,
            {Screen.RESULTS_HAS_CARS, Screen.RESULTS_EMPTY})
        log.info("time: game query %.0f ms", (self.clock() - t_query) * 1000)
        if result is not Screen.RESULTS_HAS_CARS:
            self._back_to_landing(known=result)
            return "no_cars"

        slot = self.io.first_buyable_slot()
        if slot == 0:
            self._status("All listings sold, skipping")
            self._back_to_landing(known=result)
            return "no_cars"

        self._status("Car found, buying out")
        t_buy = self.clock()
        for _ in range(slot - 1):
            self._press("down")

        if slot > 1 and self.io.first_buyable_slot() != slot:
            self._status("Listing sold during navigation, skipping")
            self._back_to_landing(known=result)
            return "no_cars"

        seen = self._press_until(
            "y", Screen.RESULTS_HAS_CARS,
            {Screen.AUCTION_OPTIONS, Screen.PLAYER_OPTIONS})
        if seen == Screen.PLAYER_OPTIONS:
            return self._escape_player_options()
        if seen is None:
            return self._recover()

        self._press("down")
        if cfg.buyout_select_delay_ms:
            self.sleeper(cfg.buyout_select_delay_ms / 1000.0)
        self._press("enter")
        seen = self.wait_for({Screen.BUY_OUT, Screen.PLAYER_OPTIONS},
                              getattr(cfg, "buyout_open_wait_s", 2.5))
        if seen == Screen.PLAYER_OPTIONS:
            return self._escape_player_options()
        if seen is None:
            return self._recover()

        interval = getattr(cfg, "buyout_confirm_window_s", 0.35)
        outcome = None
        for _ in range(4):
            if self._stop:
                return self._recover()
            self._press("enter")
            seen = self.wait_for(
                {Screen.BUYOUT_PROGRESS,
                 Screen.BUYOUT_SUCCESS, Screen.BUYOUT_FAILED},
                interval)
            if seen in (Screen.BUYOUT_SUCCESS, Screen.BUYOUT_FAILED):
                outcome = seen
                break
            if seen == Screen.BUYOUT_PROGRESS:
                outcome = self.wait_for(
                    {Screen.BUYOUT_SUCCESS, Screen.BUYOUT_FAILED},
                    cfg.timeout_outcome_s)
                break
        if outcome is None:
            late = self.wait_for(
                {Screen.BUYOUT_PROGRESS, Screen.BUYOUT_SUCCESS,
                 Screen.BUYOUT_FAILED}, cfg.timeout_outcome_s)
            if late == Screen.BUYOUT_PROGRESS:
                outcome = self.wait_for(
                    {Screen.BUYOUT_SUCCESS, Screen.BUYOUT_FAILED},
                    cfg.timeout_outcome_s)
            elif late in (Screen.BUYOUT_SUCCESS, Screen.BUYOUT_FAILED):
                outcome = late
        if outcome is None:
            return self._recover()

        log.info("time: buyout %.0f ms", (self.clock() - t_buy) * 1000)
        self._press("enter")

        if outcome == Screen.BUYOUT_FAILED:
            self._back_to_landing()
            return "failed"

        if cfg.collect_after_buyout:
            t_coll = self.clock()
            _claimable = {Screen.AUCTION_OPTIONS, Screen.CLAIM_CAR,
                          Screen.BUYOUT_SUCCESS, Screen.UNKNOWN}
            for _attempt in range(3):
                if self._stop:
                    break
                if self._collect():
                    break
                if self.io.screen() not in _claimable:
                    break
            log.info("time: collect %.0f ms", (self.clock() - t_coll) * 1000)
        self._back_to_landing()
        return "bought"

    def _auto_stop_reached(self) -> bool:
        cfg = self.cfg
        if not cfg.auto_stop_enabled:
            return False
        if self.cars_bought >= cfg.max_cars:
            return True
        elapsed_min = (self.clock() - self.started_at) / 60.0
        return elapsed_min >= cfg.max_minutes

    def run(self) -> str:
        self.started_at = self.clock()
        log.info("=== sniper started ===")
        self._status("Running")
        while not self._stop:
            if self._auto_stop_reached():
                self._status("Auto-stop limit reached")
                return "auto_stop"
            self._guard_focus()
            if self._stop:
                break
            t0 = self.clock()
            outcome = self.run_once()
            log.info("run_once outcome: %s", outcome)
            self.searches += 1
            if outcome == "recover_failed":
                self._emit_stats()
                self._status("Stopped: unable to recover")
                return "recover_failed"
            if outcome == "failed":
                self.failed_buyouts += 1
            if outcome == "bought":
                self.cars_bought += 1
                loop_s = self.clock() - t0
                self._status(f"Bought {self.cars_bought} car(s)")
                if self.on_purchase:
                    self.on_purchase(loop_s, self.cars_bought)
            self._emit_stats()
            self.sleeper(self.cfg.loop_pace_s)
        self._status("Stopped")
        return "stopped"
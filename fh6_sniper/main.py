from __future__ import annotations
import logging
import sys
import threading
from pynput import keyboard
from . import capture, notifier, paths, vision
from .config import load_config, save_config
from .overlay import Overlay
from .sniper import GameIO, Sniper


def _setup_logging():
    log_path = paths.app_dir() / "logs" / "sniper.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s %(message)s", "%H:%M:%S")
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(fmt)
    root = logging.getLogger("fh6")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    if sys.stderr is not None:         
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)

    diag_path = log_path.parent / "match_diag.log"
    diag = logging.getLogger("fh6_matchdiag")
    diag.setLevel(logging.INFO)
    diag.handlers.clear()
    diag_handler = logging.FileHandler(diag_path, mode="w", encoding="utf-8")
    diag_handler.setFormatter(fmt)
    diag.addHandler(diag_handler)
    diag.propagate = False

    return log_path


def _templates_for(cfg):
    log = logging.getLogger("fh6")
    base = paths.resource_dir() / "templates"
    lang = getattr(cfg, "game_language", "en") or "en"
    en_dir = base / "en"
    lang_dir = base / lang
    if lang_dir.is_dir():
        primary = lang_dir
        fallback = en_dir if (en_dir.is_dir() and en_dir != lang_dir) else None
    elif en_dir.is_dir():
        log.warning("template folder for '%s' not found: falling back to 'en'", lang)
        primary, fallback = en_dir, None
    else:
        primary, fallback = base, None
    log.info("loading templates for game language '%s' from %s", lang, primary)
    return vision.load_templates(primary, fallback_dir=fallback)


def main() -> None:
    log_path = _setup_logging()
    logging.getLogger("fh6").info("FH6 Sniper starting (log: %s)", log_path)
    config_path = paths.app_dir() / "config.json"
    cfg = load_config(config_path)
    templates = _templates_for(cfg)
    io = GameIO(cfg, templates)
    overlay = Overlay(
        cfg=cfg,
        on_save=lambda c: save_config(c, config_path),
        hide_from_capture=not getattr(cfg, "overlay_capturable", False))

    overlay.attach_logging(logging.getLogger("fh6"))

    state = {
        "sniper": None,
        "thread": None,
        "display": {"searches": 0, "bought": 0, "fails": 0},
        "last_bot_stats": (0, 0, 0),
    }
    purchase_log = paths.app_dir() / "logs" / "purchases.csv"

    def on_purchase(loop_seconds, total):
        notifier.log_purchase(purchase_log, "bought", loop_seconds, total)
        notifier.notify_success(total, cfg.notify_sound, cfg.notify_toast)

    def on_stats(searches, bought, fails):
        last_s, last_b, last_f = state["last_bot_stats"]
        d = state["display"]
        d["searches"] += max(0, searches - last_s)
        d["bought"]   += max(0, bought   - last_b)
        d["fails"]    += max(0, fails    - last_f)
        state["last_bot_stats"] = (searches, bought, fails)
        overlay.set_stats(d["searches"], d["bought"], d["fails"])

    def start():
        if state["thread"] and state["thread"].is_alive():
            return
        capture.focus_window()
        state["last_bot_stats"] = (0, 0, 0)     
        sniper = Sniper(io, cfg, on_purchase=on_purchase,
                        on_status=overlay.set_status,
                        on_stats=on_stats)

        def _run_safe():
            try:
                sniper.run()
            except Exception:
                logging.getLogger("fh6.main").exception(
                    "sniper thread crash")
                try:
                    overlay.set_status("Crash: see sniper.log")
                except Exception:
                    pass
            finally:
                capture.stop_capture()
                if state.get("thread") is thread:
                    state["thread"] = None
                    state["sniper"] = None
                try:
                    overlay.set_running(False)
                except Exception:
                    pass

        thread = threading.Thread(target=_run_safe, daemon=True)
        state["sniper"], state["thread"] = sniper, thread
        overlay.set_running(True)
        thread.start()

    def stop():
        s = state.get("sniper")
        if s:
            s.request_stop()

    def panic():
        stop()
        overlay.request_close()

    def toggle():
        if state["thread"] and state["thread"].is_alive():
            stop()
        else:
            start()

    hk_state = {"listener": None}

    def apply_hotkeys(config):
        old = hk_state.get("listener")
        if old is not None:
            try:
                old.stop()
            except Exception:
                pass
        try:
            listener = keyboard.GlobalHotKeys({
                config.hotkey_start_stop: toggle,
                config.hotkey_panic: panic,
            })
            listener.start()
            hk_state["listener"] = listener
        except Exception:
            hk_state["listener"] = None

    apply_hotkeys(cfg)

    def suspend_hotkeys(active):
        if active:
            listener = hk_state.get("listener")
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
                hk_state["listener"] = None
        else:
            apply_hotkeys(cfg)

    def apply_game_language(config):
        try:
            new_templates = _templates_for(config)
        except Exception:
            logging.getLogger("fh6").exception(
                "failed to reload templates for the game language")
            return
        io.templates = new_templates
        logging.getLogger("fh6").info(
            "templates reloaded for game language '%s'",
            getattr(config, "game_language", "en"))

    overlay.set_game_language_changed(apply_game_language)
    overlay.set_hotkeys_changed(apply_hotkeys)
    overlay.set_capture_active_cb(suspend_hotkeys)
    overlay.on_toggle(toggle)
    overlay.set_status("Idle")
    try:
        overlay.run()
    finally:
        stop()
        listener = hk_state.get("listener")
        if listener is not None:
            listener.stop()


if __name__ == "__main__":
    main()

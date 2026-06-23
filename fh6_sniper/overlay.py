from __future__ import annotations
import collections
import ctypes
import logging
import sys
import time
import webbrowser

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPoint, QRect, QRectF, QTimer, Signal, QObject

from . import locales
from .locales import tr

# ── Color palette ───────────────────────────────────────────────────────────

_PRIMARY   = "#FF0028"
_SECONDARY = "#c40020"
_TEXT_1    = "#f4f4f6"
_TEXT_2    = "#7a3535"
_BTN_BG    = "#0e0000"
_BTN_FG    = "#FF0028"
_BTN_HV    = "#2b0005"

_BG_HDR   = "#020000"
_BG       = "#080000"
_BG_MID   = "#0c0000"
_CARD     = "#0e0000"
_NAV_BG   = "#050000"
_NAV_ACT  = "#170006"
_DIVIDER  = "#2a0000"

_TRACK    = "#3a2222"
_SUCCESS  = "#1aa64b"
_STATUSRED= "#ff4060"

_BORDER   = _PRIMARY
_ROG      = _PRIMARY
_DIM      = _TEXT_2
_FAINT    = _TEXT_2
_RED_STAT = _STATUSRED
_IT_GREEN = _SUCCESS

# ── Fonts ────────────────────────────────────────────────────────────────────
_UI = "Sora"
_MONO = "Fira Code"
_FONTS_LOADED = False
_MSG_FILTER_INSTALLED = False


def _install_qt_msg_filter():
    global _MSG_FILTER_INSTALLED
    if _MSG_FILTER_INSTALLED:
        return
    _MSG_FILTER_INSTALLED = True
    try:
        prev = QtCore.qInstallMessageHandler(None)

        def handler(mode, ctx, message):
            low = message.lower()
            if ("populating font family aliases" in low
                    or "missing font family" in low
                    or "replace uses of missing font" in low):
                return
            if prev is not None:
                prev(mode, ctx, message)
        QtCore.qInstallMessageHandler(handler)
    except Exception:
        pass


def _set_process_dpi_aware():
    if not sys.platform.startswith("win"):
        return
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _load_fonts():
    global _FONTS_LOADED
    if _FONTS_LOADED:
        return
    _FONTS_LOADED = True
    try:
        QtGui.QFont.insertSubstitution(_UI, "Segoe UI")
        QtGui.QFont.insertSubstitution(_MONO, "Consolas")
    except Exception:
        pass
    import os
    def _wanted(fn):
        low = fn.lower()
        if not low.endswith((".ttf", ".otf")):
            return False
        return low.startswith(("sora", "firacode", "fira code",
                               "inter", "spacegrotesk", "space grotesk"))
    candidates = []
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(os.path.join(base, "fonts"))
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "fonts"))
    here = os.path.dirname(os.path.abspath(__file__))
    roots = [here]
    try:
        roots.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    except Exception:
        pass
    roots.append(os.getcwd())
    for r in roots:
        d = r
        for _ in range(5):
            candidates.append(os.path.join(d, "fonts"))
            nd = os.path.dirname(d)
            if nd == d:
                break
            d = nd
    sysroot = os.environ.get("SystemRoot", r"C:\Windows").lower()
    seen = set()
    loaded = []
    found_dir = None
    for d in candidates:
        d = os.path.normpath(d)
        if d in seen:
            continue
        seen.add(d)
        if d.lower().startswith(sysroot):
            continue
        try:
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if _wanted(fn):
                    fid = QtGui.QFontDatabase.addApplicationFont(
                        os.path.join(d, fn))
                    fams = QtGui.QFontDatabase.applicationFontFamilies(fid)
                    if fams:
                        loaded += list(fams)
                        found_dir = d
        except Exception:
            pass
        if any(f == _UI for f in loaded):
            break
    log = logging.getLogger("fh6")
    if loaded:
        log.debug("Fonts loaded from %s: %s", found_dir,
                  ", ".join(sorted(set(loaded))))
    else:
        log.debug("UI font '%s' not found - using system fallback. Put "
                  "Sora-Regular/Medium/SemiBold/Bold.ttf in a 'fonts' folder "
                  "next to the app.", _UI)

# ── Live UI scale ────────────────────────────────────────────────────────────
UI_SCALE_MIN, UI_SCALE_MAX = 0.7, 1.4
_SCALE = 1.0


def _set_scale(scale):
    global _SCALE
    _SCALE = max(UI_SCALE_MIN, min(UI_SCALE_MAX, float(scale)))
    return _SCALE


def px(n):
    return max(1, round(n * _SCALE))


def fs(n):
    return max(10, round(n * _SCALE))


# ── Settings menu spec ───────────────────────────────────────────────────────
SETTINGS_SPEC = [
    ("section", "Speed"),
    {"key": "poll_interval_ms", "label": "Poll interval (ms)", "kind": "range",
     "lo": 5, "hi": 150, "step": 1, "int": True,
     "desc": "How often the screen is re-checked. Lower = reacts sooner."},
    {"key": "key_hold_ms", "label": "Key hold (ms)", "kind": "range",
     "lo": 5, "hi": 80, "step": 1, "int": True,
     "desc": "Duration of each keypress. Lower = faster (too low drops keys)."},
    {"key": "between_keys_ms", "label": "Delay between keys (ms)", "kind": "range",
     "lo": 5, "hi": 120, "step": 1, "int": True,
     "desc": "Pause after each key. Lower = faster navigation."},
    {"key": "loop_pace_s", "label": "Delay between loops (s)", "kind": "slider",
     "lo": 0.0, "hi": 1.0, "step": 0.01, "int": False,
     "desc": "Pause between one search and the next. Lower = more attempts per minute."},
    {"key": "buyout_select_delay_ms", "label": "Confirm delay (ms)", "kind": "slider",
     "lo": 0, "hi": 500, "step": 5, "int": True,
     "desc": "Extra wait before confirming the purchase. 0 = maximum speed."},

    ("section", "Match search"),
    {"key": "match_threshold_ah_landing", "label": "Match: Landing", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the Auction House landing screen. Recommended ~0.80 (matches strong)."},
    {"key": "match_threshold_search", "label": "Match: Search", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the Search screen. Recommended ~0.80 (matches strong)."},
    {"key": "match_threshold_results", "label": "Match: Results", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the results list (cars found). Recommended ~0.80 (matches strong)."},
    {"key": "match_threshold_results_empty", "label": "Match: Empty results", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the 'no auctions' screen. Recommended ~0.80 (matches strong)."},
    {"key": "match_threshold_sold", "label": "Match: SOLD stamp", "kind": "slider",
     "lo": 0.40, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "How strongly the SOLD stamp must match to skip a sold car. Lower if sold cars slip through; higher if it wrongly marks cars as sold. Recommended ~0.70."},

    ("section", "Match buy"),
    {"key": "match_threshold_auction_options", "label": "Match: Auction options", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the auction options menu. Recommended ~0.80 (matches strong)."},
    {"key": "match_threshold_player_options", "label": "Match: Player options", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for your own listing menu (sold cars). Recommended ~0.80 (matches strong)."},
    {"key": "match_threshold_buy_out", "label": "Match: Buy Out", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the Buy Out confirm screen. Moving background = matches WEAK, recommended ~0.60. Higher makes the buyout stall."},
    {"key": "match_threshold_buyout_progress", "label": "Match: Buyout progress", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the buyout 'in progress' screen. Moving background = matches WEAK, recommended ~0.60."},

    ("section", "Match collect"),
    {"key": "match_threshold_buyout_success", "label": "Match: Buyout success", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the 'purchase successful' screen. Recommended ~0.78."},
    {"key": "match_threshold_buyout_failed", "label": "Match: Buyout failed", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the 'purchase failed' screen. Recommended ~0.78."},
    {"key": "match_threshold_claim_car", "label": "Match: Claim car", "kind": "slider",
     "lo": 0.50, "hi": 0.95, "step": 0.01, "int": False,
     "desc": "Threshold for the Claim/Collect car screen. Recommended ~0.78."},

    ("section", "Auto-stop"),
    {"key": "auto_stop_enabled", "label": "Auto-stop", "kind": "toggle",
     "desc": "Stops the bot when the limits below are reached."},
    {"key": "max_cars", "label": "Cars to buy", "kind": "slider",
     "lo": 1, "hi": 100, "step": 1, "int": True,
     "desc": "How many cars to buy before stopping."},
    {"key": "max_minutes", "label": "Maximum duration (min)", "kind": "slider",
     "lo": 1, "hi": 600, "step": 1, "int": False,
     "desc": "Maximum minutes of runtime before stopping."},

    ("section", "Behavior"),
    {"key": "jitter_maxbid", "label": "Update Max Bid", "kind": "toggle",
     "exclusive_group": "jitter_field",
     "desc": "Before every search, nudges Max Bid by \u00b11 (moves up 2 rows) to refresh the list and avoid already-sold cars. Turning this on switches off Max Buyout."},
    {"key": "jitter_maxbuyout", "label": "Update Max Buyout", "kind": "toggle",
     "exclusive_group": "jitter_field",
     "desc": "Same as above but acts on Max Buyout (moves up 1 row). Turning this on switches off Max Bid. If both are off, the price is not updated."},
    {"key": "collect_after_buyout", "label": "Collect after buyout", "kind": "toggle",
     "desc": "Immediately collects the car you bought (slower but automatic)."},
    {"key": "notify_sound", "label": "Notification sound", "kind": "toggle",
     "desc": "Windows beep on every successful purchase."},
    {"key": "notify_toast", "label": "Windows notification", "kind": "toggle",
     "desc": "Windows toast notification on every purchase."},
    {"key": "overlay_capturable", "label": "Show overlay in captures", "kind": "toggle",
     "desc": "Turn this on ONLY to take screenshots: with this on the overlay becomes visible in captures/screenshots, but it may cover the screen areas the tool reads to work. Keep it off while the sniper is running."},
    {"key": "match_score_logging", "label": "Diagnostic Mode", "kind": "toggle",
     "desc": "Logs the real match score of all 12 thresholds (11 screens + SOLD) for every frame to logs/match_diag.log, to help you calibrate the match thresholds. Slightly slower; keep it off during normal sniping."},

    ("section", "Safety"),
    {"key": "timeout_results_s", "label": "Results timeout (s)", "kind": "slider",
     "lo": 2, "hi": 30, "step": 0.5, "int": False,
     "desc": "Maximum wait for results after a search."},
    {"key": "timeout_outcome_s", "label": "Outcome timeout (s)", "kind": "slider",
     "lo": 5, "hi": 60, "step": 1, "int": False,
     "desc": "Maximum wait for the purchase outcome."},
    {"key": "timeout_claim_s", "label": "Collect timeout (s)", "kind": "slider",
     "lo": 5, "hi": 60, "step": 1, "int": False,
     "desc": "Maximum wait for collecting the car."},
    {"key": "timeout_generic_s", "label": "Generic timeout (s)", "kind": "slider",
     "lo": 2, "hi": 30, "step": 0.5, "int": False,
     "desc": "Maximum wait for other screen transitions."},
    {"key": "buyout_confirm_window_s", "label": "Buyout confirm window (s)", "kind": "slider",
     "lo": 0.0, "hi": 3.0, "step": 0.05, "int": False,
     "desc": "Wait for the outcome after the confirm Enter."},
    {"key": "buyout_open_wait_s", "label": "Buyout open wait (s)", "kind": "slider",
     "lo": 0.0, "hi": 5.0, "step": 0.1, "int": False,
     "desc": "How long it waits for the buy-out screen to open."},
    {"key": "collect_claim_wait_s", "label": "Collect: pause after confirm (s)", "kind": "slider",
     "lo": 0.0, "hi": 1.5, "step": 0.05, "int": False,
     "desc": "Pause after the Enter on car collect. Lower = faster collect."},
    {"key": "collect_unknown_wait_s", "label": "Collect: transition pause (s)", "kind": "slider",
     "lo": 0.0, "hi": 1.0, "step": 0.05, "int": False,
     "desc": "Pause when the screen is transitioning during collect."},

    ("section", "Customization Language"),
    {"key": "language", "label": "Language", "kind": "dropdown",
     "options": "languages",
     "desc": "Change the interface language. Applies live."},
    {"key": "game_language", "label": "Game language", "kind": "dropdown",
     "options": "languages",
     "desc": "The language Forza Horizon 6 runs in. The tool matches the "
             "on-screen templates for this language."},

    ("section", "Customization Appearance"),
    {"key": "ui_scale", "label": "UI scale", "kind": "slider",
     "lo": 0.7, "hi": 1.4, "step": 0.05, "int": False,
     "desc": "Drag to resize. Applies live."},

    ("section", "Customization Keybinds"),
    {"key": "hotkey_start_stop", "label": "Start/stop key", "kind": "keybind",
     "desc": "Click, then press the key you want. Applies live. (Esc cancels.)"},
    {"key": "hotkey_panic", "label": "Panic key", "kind": "keybind",
     "desc": "Stops the bot and closes the tool. Click, then press a key. Applies live."},
]

SECTION_GROUPS = {
    "Match": ["Match search", "Match buy", "Match collect"],
    "Customization": ["Customization Language", "Customization Appearance",
                      "Customization Keybinds"],
}
_CHILD_TO_GROUP = {c: g for g, cs in SECTION_GROUPS.items() for c in cs}

NAV = [
    ("status",   "status",   "Status"),
    ("settings", "settings", "Settings"),
    ("logs",     "logs",     "Logs"),
    ("help",     "help",     "Help"),
    ("about",    "info",     "Info"),
]


def _child_label(name: str) -> str:
    for g in SECTION_GROUPS:
        if name.startswith(g + " "):
            return name[len(g) + 1:].capitalize()
    return name


def _fmt(val, is_int):
    if val is None:
        return ""
    if is_int:
        return str(int(round(val)))
    return f"{val:.2f}".rstrip("0").rstrip(".")


def _coerce(val, lo, hi, step, is_int):
    val = max(lo, min(hi, val))
    val = round((val - lo) / step) * step + lo
    val = max(lo, min(hi, val))
    return int(round(val)) if is_int else round(val, 4)


import re as _re

# ── Colour model (customisable theme) ────────────────────────────────────────

def _parse_color(s):
    if isinstance(s, QtGui.QColor):
        return QtGui.QColor(s)
    if not isinstance(s, str):
        return QtGui.QColor("#000000")
    t = s.strip()
    m = _re.fullmatch(r"#([0-9a-fA-F]{3,8})", t)
    if m:
        h = m.group(1)
        try:
            if len(h) == 3:
                r, g, b = (int(c * 2, 16) for c in h); a = 255
            elif len(h) == 4:
                r, g, b, a = (int(c * 2, 16) for c in h)
            elif len(h) == 6:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16); a = 255
            elif len(h) == 8:
                r, g, b, a = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
            else:
                return QtGui.QColor("#000000")
            return QtGui.QColor(r, g, b, a)
        except Exception:
            return QtGui.QColor("#000000")
    m = _re.fullmatch(r"rgba?\(([^)]*)\)", t, _re.IGNORECASE)
    if m:
        try:
            parts = [p.strip() for p in m.group(1).split(",")]
            r, g, b = (max(0, min(255, int(round(float(p))))) for p in parts[:3])
            a = 255
            if len(parts) >= 4:
                ap = parts[3]
                if ap.endswith("%"):
                    a = round(float(ap[:-1]) / 100.0 * 255)
                else:
                    f = float(ap)
                    a = round(f * 255) if f <= 1 else round(f)
            return QtGui.QColor(r, g, b, max(0, min(255, int(a))))
        except Exception:
            return QtGui.QColor("#000000")
    c = QtGui.QColor(t)
    return c if c.isValid() else QtGui.QColor("#000000")


def _color_to_css(c):
    if not isinstance(c, QtGui.QColor):
        c = _parse_color(c)
    if c.alpha() >= 255:
        return "#%02X%02X%02X" % (c.red(), c.green(), c.blue())
    return "rgba(%d, %d, %d, %.4g%%)" % (
        c.red(), c.green(), c.blue(), c.alpha() / 255.0 * 100.0)


def _color_to_hex(c):
    if not isinstance(c, QtGui.QColor):
        c = _parse_color(c)
    if c.alpha() >= 255:
        return "#%02X%02X%02X" % (c.red(), c.green(), c.blue())
    return "#%02X%02X%02X%02X" % (c.red(), c.green(), c.blue(), c.alpha())


def _qc(spec):
    return _parse_color(spec)


def _shift_value(c, dv):
    h, s, v, a = c.getHsvF()
    if h < 0:
        h = 0.0
    v = max(0.0, min(1.0, v + dv))
    return QtGui.QColor.fromHsvF(h, s, v, a)


COLOR_ROLES = [
    ("color_primary",   "Primary",        "Main accent.",          _PRIMARY),
    ("color_secondary", "Secondary",      "Paused bar and dot.",   _SECONDARY),
    ("color_text_dim",  "Secondary text", "Dim text.",             _TEXT_2),
    ("color_btn_bg",    "Button",         "Button background.",    _BTN_BG),
    ("color_btn_fg",    "Button text",    "Button label.",         _BTN_FG),
    ("color_btn_hover", "Button hover",   "Button hover.",         _BTN_HV),
    ("color_bg",        "Background",     "Window background.",    _BG),
    ("color_card",      "Panel",          "Cards and panels.",     _CARD),
    ("color_nav_active", "Selected item", "Active item highlight.", _NAV_ACT),
    ("color_control",   "Controls",       "Outlines and tracks.",  _TRACK),
]
_COLOR_DEFAULTS = {k: d for k, _l, _d, d in COLOR_ROLES}


def _apply_theme_from_cfg(cfg):
    global _PRIMARY, _SECONDARY, _TEXT_2, _BTN_BG, _BTN_FG, _BTN_HV
    global _BORDER, _ROG, _DIM, _FAINT
    global _BG, _BG_HDR, _BG_MID, _NAV_BG, _CARD, _NAV_ACT
    global _TRACK, _DIVIDER

    def role(key):
        val = getattr(cfg, key, None) if cfg is not None else None
        if not val:
            val = _COLOR_DEFAULTS[key]
        return _color_to_css(_parse_color(val))

    _PRIMARY   = role("color_primary")
    _SECONDARY = role("color_secondary")
    _TEXT_2    = role("color_text_dim")
    _BTN_BG    = role("color_btn_bg")
    _BTN_FG    = role("color_btn_fg")
    _BTN_HV    = role("color_btn_hover")
    _bg_base = _parse_color(role("color_bg"))
    _BG      = _color_to_css(_bg_base)
    _BG_HDR  = _color_to_css(_shift_value(_bg_base, -0.0235))
    _NAV_BG  = _color_to_css(_shift_value(_bg_base, -0.0118))
    _BG_MID  = _color_to_css(_shift_value(_bg_base,  0.0157))
    _CARD    = role("color_card")
    _NAV_ACT = role("color_nav_active")
    _TRACK = _DIVIDER = role("color_control")
    _BORDER  = _ROG = _PRIMARY
    _DIM     = _FAINT = _TEXT_2


def _inject_color_settings():
    size_title = [{"kind": "note", "label": "Size"}]
    rows = [{"kind": "note", "label": "Colors"}]
    rows += [{"key": k, "label": lbl, "kind": "color", "desc": desc}
             for (k, lbl, desc, _default) in COLOR_ROLES]
    try:
        idx = next(i for i, s in enumerate(SETTINGS_SPEC)
                   if isinstance(s, dict) and s.get("key") == "ui_scale")
        SETTINGS_SPEC[idx:idx] = size_title
        idx = next(i for i, s in enumerate(SETTINGS_SPEC)
                   if isinstance(s, dict) and s.get("key") == "ui_scale")
        SETTINGS_SPEC[idx + 1:idx + 1] = rows
    except StopIteration:
        SETTINGS_SPEC.extend(rows)


_inject_color_settings()


# ── Icon (vector, recolorable) ───────────────────────────────────────────────
class Icon(QtWidgets.QWidget):
    def __init__(self, name, color=_DIM, size=22, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = color
        self._sz = size
        self.setFixedSize(size, size)

    def set_color(self, color):
        if color != self._color:
            self._color = color
            self.update()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        c = _qc(self._color)
        w = self.width()
        pen = QtGui.QPen(c, max(1.5, w * 0.09))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        m = w * 0.14
        r = QRectF(m, m, w - 2 * m, w - 2 * m)
        n = self._name
        if n == "status":
            cx = cy = w / 2.0
            R = (w - 2 * m) / 2.0
            ring = R * 0.60
            gap = R * 0.30
            p.drawEllipse(QtCore.QPointF(cx, cy), ring, ring)
            p.drawLine(QtCore.QLineF(cx, cy - R, cx, cy - gap))
            p.drawLine(QtCore.QLineF(cx, cy + gap, cx, cy + R))
            p.drawLine(QtCore.QLineF(cx - R, cy, cx - gap, cy))
            p.drawLine(QtCore.QLineF(cx + R, cy, cx + gap, cy))
        elif n == "settings":
            ys = (w * 0.30, w * 0.5, w * 0.70)
            knobs = (0.66, 0.36, 0.58)
            for y, kx in zip(ys, knobs):
                p.drawLine(int(m), int(y), int(w - m), int(y))
                p.setBrush(c)
                p.drawEllipse(QPoint(int(m + (w - 2 * m) * kx), int(y)),
                              int(w * 0.07), int(w * 0.07))
                p.setBrush(Qt.NoBrush)
        elif n == "logs":
            for y in (w * 0.32, w * 0.5, w * 0.68):
                p.drawLine(int(m), int(y), int(w - m), int(y))
        elif n == "help":
            p.drawEllipse(r)
            f = QtGui.QFont(_UI, int(w * 0.42))
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "?")
        elif n == "info":
            p.drawEllipse(r)
            f = QtGui.QFont(_UI, int(w * 0.46))
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "i")
        elif n == "close":
            p.drawLine(int(m), int(m), int(w - m), int(w - m))
            p.drawLine(int(w - m), int(m), int(m), int(w - m))
        p.end()


class HoverIcon(Icon):
    def __init__(self, name, color=_DIM, hover=_ROG, size=22, parent=None):
        super().__init__(name, color=color, size=size, parent=parent)
        self._base = color
        self._hover = hover

    def enterEvent(self, _e):
        self.set_color(self._hover)

    def leaveEvent(self, _e):
        self.set_color(self._base)


class _Cover(QtWidgets.QWidget):
    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), _qc(_BG))
        p.end()


# ── Toggle switch (animated pill) ────────────────────────────────────────────
class ToggleSwitch(QtWidgets.QWidget):
    def __init__(self, value=False, command=None, parent=None):
        super().__init__(parent)
        self._value = bool(value)
        self._command = command
        self._W, self._H = px(46), px(26)
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if self._value else 0.0
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(130)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, v):
        self._pos = float(v)
        self.update()

    def get(self):
        return self._value

    def set(self, v, emit=False):
        v = bool(v)
        if v == self._value:
            return
        self._value = v
        self._animate_to(1.0 if v else 0.0)
        if emit and self._command:
            self._command(self._value)

    def _animate_to(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def mousePressEvent(self, _e):
        self._value = not self._value
        self._animate_to(1.0 if self._value else 0.0)
        if self._command:
            self._command(self._value)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        track = _qc(_ROG if self._value else _TRACK)
        p.setBrush(track)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        margin = h * 0.16
        d = h - 2 * margin
        x0 = margin
        x1 = w - margin - d
        kx = x0 + (x1 - x0) * self._pos
        p.setBrush(_qc("#ffffff"))
        p.drawEllipse(QRectF(kx, margin, d, d))
        p.end()


# ── Slider ───────────────────────────────────────────────────────────────────
class Slider(QtWidgets.QWidget):
    def __init__(self, value, lo, hi, step, is_int, width, on_change=None,
                 parent=None):
        super().__init__(parent)
        self._lo, self._hi, self._step, self._int = lo, hi, step, is_int
        self._on_change = on_change
        self._H = px(32)
        self._knob = px(19)
        self._track = px(9)
        self.setFixedSize(int(width), self._H)
        self.setCursor(Qt.PointingHandCursor)
        self._value = _coerce(value if value is not None else lo,
                              lo, hi, step, is_int)

    def get(self):
        return self._value

    def set_value(self, v):
        self._value = _coerce(v, self._lo, self._hi, self._step, self._int)
        self.update()

    def _x0(self):
        return self._knob / 2 + 1

    def _tw(self):
        return self.width() - self._knob - 2

    def _value_from_x(self, x):
        tw = self._tw()
        frac = 0.0 if tw <= 0 else (x - self._x0()) / tw
        frac = max(0.0, min(1.0, frac))
        val = self._lo + frac * (self._hi - self._lo)
        return _coerce(val, self._lo, self._hi, self._step, self._int)

    def _set_from_event(self, e):
        nv = self._value_from_x(e.position().x())
        if nv != self._value:
            self._value = nv
            self.update()
        if self._on_change:
            self._on_change(self._value)

    def mousePressEvent(self, e):
        self._set_from_event(e)

    def mouseMoveEvent(self, e):
        self._set_from_event(e)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        cy = self.height() / 2
        x0 = self._x0()
        tw = self._tw()
        pen = QtGui.QPen(_qc(_TRACK), self._track)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QtCore.QPointF(x0, cy), QtCore.QPointF(x0 + tw, cy))
        frac = 0.0 if self._hi == self._lo else \
            (self._value - self._lo) / (self._hi - self._lo)
        frac = max(0.0, min(1.0, frac))
        kx = x0 + tw * frac
        pen2 = QtGui.QPen(_qc(_ROG), self._track)
        pen2.setCapStyle(Qt.RoundCap)
        p.setPen(pen2)
        p.drawLine(QtCore.QPointF(x0, cy), QtCore.QPointF(kx, cy))
        p.setPen(Qt.NoPen)
        p.setBrush(_qc(_ROG))
        p.drawEllipse(QtCore.QPointF(kx, cy), self._knob / 2, self._knob / 2)
        p.end()


# ── Animated state bar ───────────────────────────────────────────────────────
class StateBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._H = px(10)
        self.setFixedHeight(self._H)
        self._state = "idle"
        self._accent = _ROG
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        if state in ("running", "paused"):
            self._accent = _ROG if state == "running" else _SECONDARY
            self._phase = 0.0
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _advance(self):
        self._phase += 0.018
        if self._phase > 1.3:
            self._phase = -0.3
        self.update()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        if self._state not in ("running", "paused"):
            return
        path = QtGui.QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        p.setClipPath(path)
        p.fillRect(self.rect(), _qc(_BG_MID))
        center = self._phase * w
        band = w * 0.45
        grad = QtGui.QLinearGradient(center - band, 0, center + band, 0)
        mid = _qc(_BG_MID)
        acc = _qc(self._accent)
        grad.setColorAt(0.0, mid)
        grad.setColorAt(0.5, acc)
        grad.setColorAt(1.0, mid)
        p.fillRect(self.rect(), grad)
        p.end()


# ── Pill button ──────────────────────────────────────────────────────────────
class PillButton(QtWidgets.QWidget):
    def __init__(self, text, command=None, height=None, base=_BTN_BG,
                 hover=_BTN_HV, fg=_BTN_FG, parent=None):
        super().__init__(parent)
        self._text = text
        self._command = command
        self._base, self._hover, self._fg = base, hover, fg
        self._cur = base
        self._h = height or px(46)
        self.setFixedHeight(self._h)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Fixed)

    def set_command(self, cmd):
        self._command = cmd

    def set_mode(self, text, base, hover, fg):
        self._text, self._base, self._hover, self._fg = text, base, hover, fg
        self._cur = base
        self.update()

    def enterEvent(self, _e):
        self._cur = self._hover
        self.update()

    def leaveEvent(self, _e):
        self._cur = self._base
        self.update()

    def mousePressEvent(self, _e):
        if self._command:
            self._command()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        p.setBrush(_qc(self._cur))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), px(12), px(12))
        f = QtGui.QFont(_UI, fs(13))
        f.setBold(True)
        p.setFont(f)
        p.setPen(_qc(self._fg))
        p.drawText(self.rect(), Qt.AlignCenter, self._text)
        p.end()


# ── Logging handler ──────────────────────────────────────────────────────────
class _OverlayLogHandler(logging.Handler):
    def __init__(self, overlay):
        super().__init__()
        self._ov = overlay

    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            try:
                msg = record.getMessage()
            except Exception:
                return
        self._ov.log(msg)


# ── Thread-safe bridge ───────────────────────────────────────────────────────
class _Bridge(QObject):
    status = Signal(str, object)
    running = Signal(bool)
    stats = Signal(int, int, int)
    logmsg = Signal(str)
    quit = Signal()


# ── Nav row ──────────────────────────────────────────────────────────────────
class NavRow(QtWidgets.QWidget):
    def __init__(self, label, icon=None, indent=0, on_click=None,
                 height=None, compact=False, parent=None):
        super().__init__(parent)
        self._active = False
        self._hover = False
        self._on_click = on_click
        self._icon = icon
        self._fit_px = fs(13)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(height or px(44))
        lay = QtWidgets.QHBoxLayout(self)
        lay.setSpacing(px(8))
        self._lbl = QtWidgets.QLabel(label)
        self._lbl.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                QtWidgets.QSizePolicy.Preferred)
        self._lbl.setMinimumWidth(0)
        self._lbl.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{self._fit_px}px;"
            "font-weight:bold; background:transparent;")
        if compact:
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addStretch(1)
            if icon is not None:
                lay.addWidget(icon, 0, Qt.AlignCenter)
            lay.addStretch(1)
            self._lbl.hide()
        else:
            lay.setContentsMargins(px(14) + indent, 0, px(8), 0)
            if icon is not None:
                lay.addWidget(icon, 0, Qt.AlignVCenter)
            lay.addWidget(self._lbl, 1)

    def set_active(self, active):
        self._active = active
        self._refresh()

    def _refresh(self):
        hot = self._active or self._hover
        self._lbl.setStyleSheet(
            f"color:{_ROG if hot else _DIM}; font-family:'Sora','Segoe UI';"
            f"font-size:{self._fit_px}px; font-weight:bold; background:transparent;")
        if self._icon is not None:
            self._icon.set_color(_ROG if hot else _DIM)
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit_font()

    def _fit_font(self):
        if self._lbl.isHidden():
            return
        avail = self._lbl.width()
        if avail <= 0:
            return
        base, floor = fs(13), fs(9)
        f = QtGui.QFont()
        f.setFamilies(["Sora", "Segoe UI"])
        f.setBold(True)
        size = base
        while size > floor:
            f.setPixelSize(size)
            if QtGui.QFontMetrics(f).horizontalAdvance(self._lbl.text()) <= avail:
                break
            size -= 1
        if size != self._fit_px:
            self._fit_px = size
            self._refresh()

    def enterEvent(self, _e):
        self._hover = True
        self._refresh()

    def leaveEvent(self, _e):
        self._hover = False
        self._refresh()

    def mousePressEvent(self, _e):
        if self._on_click:
            self._on_click()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        if self._active:
            p.fillRect(self.rect(), _qc(_NAV_ACT))
            p.fillRect(QRect(0, 0, px(3), self.height()), _qc(_ROG))
        p.end()


# ── Colour picker ────────────────────────────────────────────────────────────
def _paint_checker(p, rect, cell=None):
    cell = cell or px(6)
    p.fillRect(rect, _qc("#4a4a4a"))
    p.setPen(Qt.NoPen)
    p.setBrush(_qc("#6a6a6a"))
    x0, y0 = int(rect.left()), int(rect.top())
    nx = int(rect.width()) // cell + 1
    ny = int(rect.height()) // cell + 1
    for iy in range(ny):
        for ix in range(nx):
            if (ix + iy) % 2 == 0:
                p.drawRect(x0 + ix * cell, y0 + iy * cell, cell, cell)


def _clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


class ColorButton(QtWidgets.QWidget):
    def __init__(self, value, on_open=None, width=None, parent=None):
        super().__init__(parent)
        self._value = _color_to_hex(_parse_color(value))
        self._on_open = on_open
        self.setFixedHeight(px(34))
        if width:
            self.setFixedWidth(int(width))
        self.setCursor(Qt.PointingHandCursor)

    def get(self):
        return self._value

    def set_color(self, value):
        self._value = _color_to_hex(_parse_color(value))
        self.update()

    def mousePressEvent(self, _e):
        if self._on_open:
            self._on_open(self)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rad = px(8)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), rad, rad)
        p.fillPath(path, _qc(_CARD))
        f = QtGui.QFont(_MONO, fs(12))
        p.setFont(f)
        p.setPen(_qc(_DIM))
        p.drawText(QRectF(px(10), 0, w - px(10), h),
                   Qt.AlignVCenter | Qt.AlignLeft, self._value.upper())
        chip = QRectF(w - px(40), px(5), px(32), h - px(10))
        cp = QtGui.QPainterPath()
        cp.addRoundedRect(chip, px(5), px(5))
        p.save()
        p.setClipPath(cp)
        col = _qc(self._value)
        if col.alpha() < 255:
            _paint_checker(p, chip, px(5))
        p.fillRect(chip, col)
        p.restore()
        p.setPen(QtGui.QPen(_qc(_DIVIDER), max(1, px(1))))
        p.setBrush(Qt.NoBrush)
        p.drawPath(cp)
        p.drawPath(path)
        p.end()


class _DropdownItem(QtWidgets.QWidget):
    def __init__(self, value, label, selected, on_click, parent=None):
        super().__init__(parent)
        self._value = value
        self._label = label
        self._selected = selected
        self._hover = False
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(px(32))

    def enterEvent(self, _e):
        self._hover = True
        self.update()

    def leaveEvent(self, _e):
        self._hover = False
        self.update()

    def mousePressEvent(self, _e):
        if self._on_click:
            self._on_click(self._value)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        hot = self._hover or self._selected
        if hot:
            path = QtGui.QPainterPath()
            path.addRoundedRect(
                QRectF(0, 0, self.width(), self.height()), px(6), px(6))
            p.fillPath(path, _qc(_NAV_ACT))
        p.setFont(QtGui.QFont(_UI, fs(13)))
        p.setPen(_qc(_ROG if hot else _DIM))
        p.drawText(self.rect(), Qt.AlignCenter, self._label)
        p.end()


class _DropdownPopup(QtWidgets.QFrame):
    def __init__(self, anchor, options, current, on_choose, on_close):
        super().__init__(anchor.window())
        self.setWindowFlags(Qt.Popup)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._on_choose = on_choose
        self._on_close = on_close
        self.setStyleSheet(
            f"background:{_CARD}; border:1px solid {_DIVIDER};"
            f"border-radius:{px(8)}px;")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(4), px(4), px(4), px(4))
        lay.setSpacing(px(2))
        for v, lbl in options:
            lay.addWidget(_DropdownItem(
                v, lbl, selected=(v == current), on_click=self._pick))

    def _pick(self, value):
        self.close()
        if self._on_choose:
            self._on_choose(value)

    def hideEvent(self, e):
        if self._on_close:
            self._on_close()
        super().hideEvent(e)

    def show_below(self, anchor):
        self.setFixedWidth(anchor.width())
        gp = anchor.mapToGlobal(QPoint(0, anchor.height() + px(4)))
        self.move(gp)
        self.show()


class Dropdown(QtWidgets.QWidget):
    def __init__(self, value, options, on_change=None, width=None, parent=None):
        super().__init__(parent)
        self._options = [(str(v), str(lbl)) for v, lbl in options]
        self._value = str(value)
        if not any(v == self._value for v, _ in self._options) and self._options:
            self._value = self._options[0][0]
        self._on_change = on_change
        self._popup = None
        self._closed_at = 0.0
        self.setFixedHeight(px(34))
        if width:
            self.setFixedWidth(int(width))
        self.setCursor(Qt.PointingHandCursor)

    def get(self):
        return self._value

    def set_value(self, value):
        self._value = str(value)
        self.update()

    def _label(self):
        for v, lbl in self._options:
            if v == self._value:
                return lbl
        return self._value

    def mousePressEvent(self, _e):
        self._toggle()

    def _toggle(self):
        if (time.monotonic() - self._closed_at) < 0.15:
            return
        if self._popup is not None and self._popup.isVisible():
            self._popup.close()
            return
        self._open_popup()

    def _open_popup(self):
        popup = _DropdownPopup(self, self._options, self._value,
                               self._choose, self._on_popup_closed)
        self._popup = popup
        popup.show_below(self)

    def _on_popup_closed(self):
        self._closed_at = time.monotonic()
        self._popup = None

    def _choose(self, value):
        value = str(value)
        if value == self._value:
            return
        self._value = value
        self.update()
        if self._on_change:
            self._on_change(value)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rad = px(8)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), rad, rad)
        p.fillPath(path, _qc(_CARD))
        f = QtGui.QFont(_UI, fs(13))
        p.setFont(f)
        p.setPen(_qc(_DIM))
        p.drawText(QRectF(px(28), 0, w - px(56), h),
                   Qt.AlignVCenter | Qt.AlignHCenter, self._label())
        cx, cy = w - px(18), h / 2
        s = px(4)
        chev = QtGui.QPainterPath()
        chev.moveTo(cx - s, cy - s / 2)
        chev.lineTo(cx, cy + s / 2)
        chev.lineTo(cx + s, cy - s / 2)
        pen = QtGui.QPen(_qc(_ROG), max(1, px(2)))
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(chev)
        p.setPen(QtGui.QPen(_qc(_DIVIDER), max(1, px(1))))
        p.drawPath(path)
        p.end()


# ── Keybind capture helpers ───────────────────────────────────────────────────

_QT_SPECIAL_TOKENS = {
    Qt.Key_Escape: "<esc>",
    Qt.Key_Space: "<space>",
    Qt.Key_Return: "<enter>",
    Qt.Key_Enter: "<enter>",
    Qt.Key_Tab: "<tab>",
    Qt.Key_Backspace: "<backspace>",
    Qt.Key_Delete: "<delete>",
    Qt.Key_Insert: "<insert>",
    Qt.Key_Home: "<home>",
    Qt.Key_End: "<end>",
    Qt.Key_PageUp: "<page_up>",
    Qt.Key_PageDown: "<page_down>",
    Qt.Key_Up: "<up>",
    Qt.Key_Down: "<down>",
    Qt.Key_Left: "<left>",
    Qt.Key_Right: "<right>",
    Qt.Key_CapsLock: "<caps_lock>",
    Qt.Key_NumLock: "<num_lock>",
    Qt.Key_ScrollLock: "<scroll_lock>",
    Qt.Key_Pause: "<pause>",
    Qt.Key_Print: "<print_screen>",
    Qt.Key_Menu: "<menu>",
}

_QT_PURE_MODIFIERS = {
    Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_AltGr,
    Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R,
}


def _hotkey_token_for_key(key) -> str | None:
    if Qt.Key_F1 <= key <= Qt.Key_F35:
        return f"<f{key - Qt.Key_F1 + 1}>"
    if key in _QT_SPECIAL_TOKENS:
        return _QT_SPECIAL_TOKENS[key]
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key).lower()
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    return None


def hotkey_from_qt_event(event) -> str | None:
    key = event.key()
    if key in _QT_PURE_MODIFIERS or key == 0:
        return None
    token = _hotkey_token_for_key(key)
    if token is None:
        return None
    mods = event.modifiers()
    prefix = []
    if mods & Qt.ControlModifier:
        prefix.append("<ctrl>")
    if mods & Qt.AltModifier:
        prefix.append("<alt>")
    if mods & Qt.ShiftModifier:
        prefix.append("<shift>")
    if mods & Qt.MetaModifier:
        prefix.append("<cmd>")
    return "+".join(prefix + [token])


_TOKEN_LABELS = {
    "esc": "Esc", "space": "Space", "enter": "Enter", "tab": "Tab",
    "backspace": "Backspace", "delete": "Del", "insert": "Ins",
    "home": "Home", "end": "End", "page_up": "PgUp", "page_down": "PgDn",
    "up": "\u2191", "down": "\u2193", "left": "\u2190", "right": "\u2192",
    "caps_lock": "Caps", "num_lock": "NumLk", "scroll_lock": "ScrLk",
    "pause": "Pause", "print_screen": "PrtSc", "menu": "Menu",
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Win",
}


def hotkey_label(hotkey: str) -> str:
    if not hotkey:
        return "\u2014"
    parts = []
    for raw in str(hotkey).split("+"):
        tok = raw.strip()
        inner = tok[1:-1] if tok.startswith("<") and tok.endswith(">") else tok
        inner = inner.strip()
        if inner in _TOKEN_LABELS:
            parts.append(_TOKEN_LABELS[inner])
        elif inner.startswith("f") and inner[1:].isdigit():
            parts.append("F" + inner[1:])
        else:
            parts.append(inner.upper())
    return " + ".join(p for p in parts if p)


class KeybindButton(QtWidgets.QWidget):
    def __init__(self, value, on_capture=None, width=None, parent=None,
                 on_active=None):
        super().__init__(parent)
        self._value = str(value or "")
        self._on_capture = on_capture
        self._on_active = on_active
        self._capturing = False
        self.setFixedHeight(px(34))
        if width:
            self.setFixedWidth(int(width))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def get(self):
        return self._value

    def set_value(self, value):
        self._value = str(value or "")
        self.update()

    def _start_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self.setFocus(Qt.MouseFocusReason)
        self.grabKeyboard()
        if self._on_active:
            self._on_active(True)
        self.update()

    def _end_capture(self):
        if not self._capturing:
            return
        self._capturing = False
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        if self._on_active:
            self._on_active(False)
        self.update()

    def mousePressEvent(self, _e):
        if self._capturing:
            self._end_capture()
        else:
            self._start_capture()

    def keyPressEvent(self, e):
        if not self._capturing:
            super().keyPressEvent(e)
            return
        if e.key() == Qt.Key_Escape:
            self._end_capture()
            return
        if e.key() in _QT_PURE_MODIFIERS:
            return
        hk = hotkey_from_qt_event(e)
        if hk is None:
            return
        self._value = hk
        self._end_capture()
        if self._on_capture:
            self._on_capture(hk)

    def focusOutEvent(self, e):
        self._end_capture()
        super().focusOutEvent(e)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rad = px(8)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), rad, rad)
        p.fillPath(path, _qc(_NAV_ACT if self._capturing else _CARD))
        border = _qc(_ROG if self._capturing else _DIVIDER)
        p.setPen(QtGui.QPen(border, max(1, px(1))))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        if self._capturing:
            text, col = "Press a key\u2026", _ROG
            f = QtGui.QFont(_UI, fs(12))
        else:
            text, col = hotkey_label(self._value), _DIM
            f = QtGui.QFont(_MONO, fs(13))
        p.setFont(f)
        p.setPen(_qc(col))
        p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, text)
        p.end()


class _SVField(QtWidgets.QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._h, self._s, self._v = 0.0, 1.0, 1.0
        self.setMinimumSize(px(210), px(150))
        self.setCursor(Qt.CrossCursor)

    def set_hsv(self, h, s, v):
        self._h, self._s, self._v = h, s, v
        self.update()

    def _pick(self, e):
        self._s = _clamp01(e.position().x() / max(1, self.width()))
        self._v = 1.0 - _clamp01(e.position().y() / max(1, self.height()))
        self.changed.emit()
        self.update()

    def mousePressEvent(self, e):
        self._pick(e)

    def mouseMoveEvent(self, e):
        self._pick(e)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, px(8), px(8))
        p.setClipPath(path)
        p.fillRect(rect, QtGui.QColor.fromHsvF(min(0.9999, self._h), 1.0, 1.0))
        gx = QtGui.QLinearGradient(0, 0, w, 0)
        gx.setColorAt(0.0, _qc("#ffffff"))
        gx.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
        p.fillRect(rect, gx)
        gy = QtGui.QLinearGradient(0, 0, 0, h)
        gy.setColorAt(0.0, QtGui.QColor(0, 0, 0, 0))
        gy.setColorAt(1.0, _qc("#000000"))
        p.fillRect(rect, gy)
        p.setClipping(False)
        cx = self._s * w
        cy = (1.0 - self._v) * h
        ring = _qc("#000000") if self._v > 0.55 and self._s < 0.55 \
            else _qc("#ffffff")
        p.setPen(QtGui.QPen(ring, max(1.5, px(2))))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QtCore.QPointF(cx, cy), px(6), px(6))
        p.end()


class _HueBar(QtWidgets.QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._h = 0.0
        self.setFixedWidth(px(20))
        self.setMinimumHeight(px(150))
        self.setCursor(Qt.PointingHandCursor)

    def set_hue(self, h):
        self._h = h
        self.update()

    def _pick(self, e):
        self._h = _clamp01(e.position().y() / max(1, self.height()))
        if self._h > 0.9999:
            self._h = 0.9999
        self.changed.emit()
        self.update()

    def mousePressEvent(self, e):
        self._pick(e)

    def mouseMoveEvent(self, e):
        self._pick(e)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, w / 2, w / 2)
        p.setClipPath(path)
        g = QtGui.QLinearGradient(0, 0, 0, h)
        for i in range(7):
            t = i / 6.0
            g.setColorAt(t, QtGui.QColor.fromHsvF(min(0.9999, t), 1.0, 1.0))
        p.fillRect(rect, g)
        p.setClipping(False)
        cy = self._h * h
        p.setPen(QtGui.QPen(_qc("#ffffff"), max(1.5, px(2))))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, cy - px(3), w - 2, px(6)), px(3), px(3))
        p.end()


class _AlphaBar(QtWidgets.QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._a = 1.0
        self._col = _qc("#ff0028")
        self.setFixedWidth(px(20))
        self.setMinimumHeight(px(150))
        self.setCursor(Qt.PointingHandCursor)

    def set_alpha(self, a):
        self._a = a
        self.update()

    def set_color(self, c):
        self._col = _qc(c)
        self._col.setAlpha(255)
        self.update()

    def _pick(self, e):
        self._a = 1.0 - _clamp01(e.position().y() / max(1, self.height()))
        self.changed.emit()
        self.update()

    def mousePressEvent(self, e):
        self._pick(e)

    def mouseMoveEvent(self, e):
        self._pick(e)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, w / 2, w / 2)
        p.setClipPath(path)
        _paint_checker(p, rect, px(5))
        top = QtGui.QColor(self._col); top.setAlpha(255)
        bot = QtGui.QColor(self._col); bot.setAlpha(0)
        g = QtGui.QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, top)
        g.setColorAt(1.0, bot)
        p.fillRect(rect, g)
        p.setClipping(False)
        cy = (1.0 - self._a) * h
        p.setPen(QtGui.QPen(_qc("#ffffff"), max(1.5, px(2))))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, cy - px(3), w - 2, px(6)), px(3), px(3))
        p.end()


class ColorPickerPopup(QtWidgets.QWidget):
    def __init__(self, value, default_hex, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._default = default_hex
        self._committed = False
        self._guard = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool
                            | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        col = _parse_color(value)
        h, s, v, a = col.getHsvF()
        if h < 0:
            h = 0.0

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QtWidgets.QFrame()
        card.setObjectName("pick")
        card.setStyleSheet(
            f"#pick{{background:{_BG_MID}; border:1px solid {_PRIMARY};"
            f"border-radius:{px(12)}px;}}")
        outer.addWidget(card)
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(px(14), px(14), px(14), px(14))
        lay.setSpacing(px(10))

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(px(10))
        self._sv = _SVField()
        self._sv.set_hsv(h, s, v)
        top.addWidget(self._sv, 1)
        self._hue = _HueBar()
        self._hue.set_hue(h)
        top.addWidget(self._hue)
        self._alpha = _AlphaBar()
        self._alpha.set_alpha(a)
        self._alpha.set_color(col)
        top.addWidget(self._alpha)
        lay.addLayout(top)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(8))
        self._preview = QtWidgets.QFrame()
        self._preview.setFixedSize(px(34), px(34))
        row.addWidget(self._preview)
        self._hex = QtWidgets.QLineEdit()
        self._hex.setStyleSheet(
            f"background:{_CARD}; color:{_DIM}; border:1px solid {_DIVIDER};"
            f"border-radius:{px(6)}px; padding:{px(6)}px;"
            f"font-family:'Fira Code','Consolas'; font-size:{fs(13)}px;")
        self._hex.editingFinished.connect(self._hex_done)
        self._hex.textEdited.connect(self._hex_edited)
        row.addWidget(self._hex, 1)
        lay.addLayout(row)

        bottom = QtWidgets.QHBoxLayout()
        reset = QtWidgets.QLabel("Reset")
        reset.setCursor(Qt.PointingHandCursor)
        reset.setStyleSheet(
            f"color:{_TEXT_2}; font-family:'Sora','Segoe UI';"
            f"font-size:{fs(12)}px; font-weight:bold; background:transparent;")
        reset.mousePressEvent = lambda _e: self._reset()
        bottom.addWidget(reset)
        bottom.addStretch(1)
        done = PillButton("Done", height=px(34), base=_BTN_BG,
                          hover=_BTN_HV, fg=_BTN_FG,
                          command=self._commit_and_close)
        done.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                           QtWidgets.QSizePolicy.Fixed)
        done.setFixedWidth(px(110))
        bottom.addWidget(done)
        lay.addLayout(bottom)

        self.setFixedWidth(px(300))
        self._sv.changed.connect(self._from_sv)
        self._hue.changed.connect(self._from_hue)
        self._alpha.changed.connect(self._from_alpha)
        self._h, self._s, self._v, self._a = h, s, v, a
        self._refresh(emit=False)

    def _color(self):
        c = QtGui.QColor.fromHsvF(min(0.9999, _clamp01(self._h)),
                                  _clamp01(self._s), _clamp01(self._v))
        c.setAlphaF(_clamp01(self._a))
        return c

    def _refresh(self, emit=True):
        c = self._color()
        self._alpha.set_color(c)
        self._preview.setStyleSheet(
            f"background:{_color_to_css(c)}; border:1px solid {_DIVIDER};"
            f"border-radius:{px(8)}px;")
        self._guard = True
        self._hex.setText(_color_to_hex(c).upper())
        self._guard = False
        if emit and self._on_change:
            self._on_change(c, False)

    def _from_sv(self):
        self._s, self._v = self._sv._s, self._sv._v
        self._refresh()

    def _from_hue(self):
        self._h = self._hue._h
        self._sv.set_hsv(self._h, self._s, self._v)
        self._refresh()

    def _from_alpha(self):
        self._a = self._alpha._a
        self._refresh()

    def _hex_edited(self, _t):
        if self._guard:
            return
        c = _parse_color(self._hex.text())
        if not c.isValid():
            return
        h, s, v, a = c.getHsvF()
        if h < 0:
            h = self._h
        self._h, self._s, self._v, self._a = h, s, v, a
        self._sv.set_hsv(h, s, v)
        self._hue.set_hue(h)
        self._alpha.set_alpha(a)
        self._alpha.set_color(c)
        self._preview.setStyleSheet(
            f"background:{_color_to_css(c)}; border:1px solid {_DIVIDER};"
            f"border-radius:{px(8)}px;")
        if self._on_change:
            self._on_change(c, False)

    def _hex_done(self):
        if self._on_change:
            self._on_change(self._color(), False)

    def _reset(self):
        c = _parse_color(self._default)
        h, s, v, a = c.getHsvF()
        if h < 0:
            h = 0.0
        self._h, self._s, self._v, self._a = h, s, v, a
        self._sv.set_hsv(h, s, v)
        self._hue.set_hue(h)
        self._alpha.set_alpha(a)
        self._refresh()

    def show_at(self, anchor_widget):
        self.adjustSize()
        g = anchor_widget.mapToGlobal(QPoint(0, 0))
        aw = anchor_widget.width()
        pw, ph = self.width(), self.sizeHint().height()
        scr = (QtWidgets.QApplication.screenAt(g)
               or QtWidgets.QApplication.primaryScreen())
        av = scr.availableGeometry()
        x = g.x() - pw - px(10)
        if x < av.left() + 8:
            x = g.x() + aw + px(10)
        x = max(av.left() + 8, min(x, av.right() - pw - 8))
        y = g.y()
        y = max(av.top() + 8, min(y, av.bottom() - ph - 8))
        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self.activateWindow()
        QtWidgets.QApplication.instance().installEventFilter(self)

    def eventFilter(self, _obj, ev):
        if ev.type() == QtCore.QEvent.MouseButtonPress:
            try:
                gp = ev.globalPosition().toPoint()
            except Exception:
                gp = ev.globalPos()
            if not self.frameGeometry().contains(gp):
                QtCore.QTimer.singleShot(0, self._commit_and_close)
        return False

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self._commit_and_close()
        else:
            super().keyPressEvent(e)

    def _dismiss(self):
        if self._committed:
            return
        self._committed = True
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        self.close()

    def _commit_and_close(self):
        if self._committed:
            return
        self._committed = True
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        if self._on_change:
            self._on_change(self._color(), True)
        self.close()


class Overlay:
    def __init__(self, cfg=None, on_save=None, hide_from_capture: bool = True,
                 on_hotkeys_changed=None):
        self._cfg = cfg
        self._on_save = on_save
        self._on_hotkeys_changed = on_hotkeys_changed
        self._on_game_lang_changed = None
        self._hide_from_capture = hide_from_capture
        self._toggle_cb = None

        self._page = "status"
        self._cur_section = None
        self._status_src = "ready to start"
        self._status_kwargs = {}
        self._settings_open = True
        self._group_expanded = {g: False for g in SECTION_GROUPS}
        self._setting_widgets = {}
        self._excl_group = {}
        self._sec_index = {}
        self._value_labels = {}
        self._nav_rows = {}
        self._sec_rows = {}
        self._logs = collections.deque(maxlen=300)
        self._running = False
        self._active = False
        self._started = None
        self._ready = False
        self._drag_off = None
        self._autosave_timer = None
        self._scale_timer = None
        self._theme_timer = None
        self._color_popup = None
        self._active_color_key = None
        self._hotkey_footer = None
        self._on_capture_active = None

        _set_scale(getattr(cfg, "ui_scale", 1.0) if cfg is not None else 1.0)
        locales.set_language(getattr(cfg, "language", "en") if cfg is not None else "en")
        _apply_theme_from_cfg(cfg)

        try:
            _set_process_dpi_aware()
        except Exception:
            pass
        try:
            QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except Exception:
            pass
        self._app = QtWidgets.QApplication.instance() \
            or QtWidgets.QApplication(sys.argv)
        _install_qt_msg_filter()
        _load_fonts()
        self._app.setQuitOnLastWindowClosed(False)
        try:
            self._app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        except Exception:
            pass
        try:
            if _UI in QtGui.QFontDatabase.families():
                self._app.setFont(QtGui.QFont(_UI))
        except Exception:
            pass

        self._win = QtWidgets.QWidget()
        self._win.setWindowTitle("AuctionSniper - V.2")
        self._win.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self._win.setAttribute(Qt.WA_TranslucentBackground, False)
        self._win.setAttribute(Qt.WA_NoSystemBackground, False)
        self._win.setAutoFillBackground(True)
        _wp = self._win.palette()
        _wp.setColor(QtGui.QPalette.Window, _qc(_BG))
        self._win.setPalette(_wp)
        self._win.closeEvent = self._on_close_event

        self._bridge = _Bridge()
        self._bridge.status.connect(self._apply_status)
        self._bridge.running.connect(self._apply_running)
        self._bridge.stats.connect(self._apply_stats)
        self._bridge.logmsg.connect(self._add_log)
        self._bridge.quit.connect(self._do_quit)

        self._build_ui()
        self._apply_page_geometry(initial=True)
        self._ready = True

        self._tick_timer = QTimer(self._win)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

    # ── UI construction ──────────────────────────────────────────────────
    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self._win)
        outer.setContentsMargins(0, 0, 0, 0)

        self._frame = QtWidgets.QFrame()
        self._frame.setObjectName("frame")
        self._frame.setStyleSheet(
            f"#frame{{background:{_BG}; border:1px solid {_BORDER};}}")
        outer.addWidget(self._frame)

        root = QtWidgets.QVBoxLayout(self._frame)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        strip = QtWidgets.QFrame()
        strip.setFixedHeight(px(3))
        strip.setStyleSheet(f"background:{_ROG};")
        root.addWidget(strip)

        root.addWidget(self._build_header())

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._rail = QtWidgets.QFrame()
        self._rail.setStyleSheet(f"background:{_NAV_BG};")
        self._rail_lay = QtWidgets.QVBoxLayout(self._rail)
        self._rail_lay.setContentsMargins(0, px(10), 0, px(10))
        self._rail_lay.setSpacing(px(2))
        body.addWidget(self._rail)

        self._content = QtWidgets.QWidget()
        self._content.setStyleSheet(f"background:{_BG};")
        self._content_lay = QtWidgets.QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(0, 0, 0, 0)
        self._content_lay.setSpacing(0)
        body.addWidget(self._content, 0)
        root.addLayout(body, 1)

        self._pages = {
            "status": self._build_status_page(),
            "settings": self._build_settings_page(),
            "logs": self._build_logs_page(),
            "help": self._build_help_page(),
            "about": self._build_about_page(),
        }
        for w in self._pages.values():
            w.setParent(self._content)
            w.hide()
        self._page_in_holder = None
        self._wide_h = None

        self._toast_timer = QTimer(self._win)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast.hide)

        self._rebuild_rail()
        self._select_page(self._page, refit=False)

        old_cov = getattr(self, "_cover", None)
        if old_cov is not None:
            old_cov.deleteLater()
        self._cover = _Cover(self._win)
        self._cover.hide()
        self._win.resizeEvent = self._on_win_resize

    def _on_win_resize(self, _e):
        cov = getattr(self, "_cover", None)
        if cov is None:
            return
        if cov.isVisible():
            w = max(self._win.width(), cov.width())
            h = max(self._win.height(), cov.height())
            cov.setGeometry(0, 0, w, h)
        else:
            cov.setGeometry(0, 0, self._win.width(), self._win.height())

    def _build_header(self):
        head = QtWidgets.QFrame()
        head.setStyleSheet(f"background:{_BG_HDR};")
        head.mousePressEvent = self._drag_start
        head.mouseMoveEvent = self._drag_move
        lay = QtWidgets.QHBoxLayout(head)
        lay.setContentsMargins(px(14), px(9), px(10), px(9))
        lay.setSpacing(px(6))
        logo = Icon("status", color=_ROG, size=px(26))
        logo.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(logo)
        title = QtWidgets.QLabel(
            f"<span style='color:{_DIM}'>Auction</span>"
            f"<span style='color:{_ROG}'>Sniper</span>")
        title.setTextFormat(Qt.RichText)
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title.setStyleSheet(
            "font-family:'Sora','Segoe UI';"
            f"font-size:{fs(18)}px; font-weight:bold; background:transparent;")
        lay.addWidget(title)
        badge = QtWidgets.QLabel("V2.1")
        badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(px(15))
        badge.setStyleSheet(
            f"background:{_ROG}; color:#ffffff; font-family:'Sora','Segoe UI';"
            f"font-size:{fs(8)}px; font-weight:bold; border-radius:{px(3)}px;"
            f"padding:0px {px(4)}px;")
        lay.addWidget(badge)
        lay.addSpacing(px(8))
        self._toast = QtWidgets.QLabel(tr("Saved \u2713"))
        self._toast.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._toast.setStyleSheet(
            f"color:{_ROG}; font-family:'Sora','Segoe UI'; font-size:{fs(11)}px;"
            "font-weight:bold; background:transparent;")
        self._toast.hide()
        lay.addWidget(self._toast)
        lay.addStretch(1)
        close = HoverIcon("close", color=_DIM, hover=_ROG, size=px(18))
        close.setCursor(Qt.PointingHandCursor)
        close.mousePressEvent = lambda _e: self._win.close()
        lay.addWidget(close)
        self._dot = logo
        return head

    # ── Rail ──────────────────────────────────────────────────────────────
    def _rail_entries(self):
        entries = []
        emitted_group = set()
        for spec in SETTINGS_SPEC:
            if not (isinstance(spec, tuple) and spec[0] == "section"):
                continue
            name = spec[1]
            grp = _CHILD_TO_GROUP.get(name)
            if grp:
                if grp not in emitted_group:
                    emitted_group.add(grp)
                    entries.append(("group", grp))
                if self._group_expanded.get(grp):
                    entries.append(("sub", name))
            else:
                entries.append(("section", name))
        return entries

    def _rebuild_rail(self):
        while self._rail_lay.count():
            it = self._rail_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        self._nav_rows = {}
        self._sec_rows = {}
        self._rail_lay.setContentsMargins(0, px(10), 0, px(10))
        self._rail_lay.setSpacing(px(2))
        wide = (self._page != "status")
        self._rail.setFixedWidth(px(150) if wide else px(64))

        settings_expanded = (self._page == "settings" and self._settings_open)
        for key, icon_name, label in NAV:
            if key == "settings" and self._cfg is None:
                continue
            ic = Icon(icon_name, color=_DIM, size=px(32))
            if key == "settings":
                cb = self._on_settings_nav
            else:
                cb = (lambda k=key: self._nav_click(k))
            row = NavRow(tr(label), icon=ic, on_click=cb, height=px(46),
                         compact=not wide)
            row.set_active(self._page == key)
            self._rail_lay.addWidget(row)
            self._nav_rows[key] = row
            if key == "settings" and settings_expanded:
                for kind, name in self._rail_entries():
                    if kind == "group":
                        gr = NavRow(tr(name), indent=px(22),
                                    on_click=lambda g=name: self._toggle_group(g),
                                    height=px(40))
                        gr.set_active(self._cur_section in SECTION_GROUPS.get(name, []))
                        self._rail_lay.addWidget(gr)
                        self._sec_rows["group:" + name] = gr
                    elif kind == "sub":
                        sr = NavRow(tr(_child_label(name)), indent=px(40),
                                    on_click=lambda n=name: self._show_section(n),
                                    height=px(38))
                        sr.set_active(self._cur_section == name)
                        self._rail_lay.addWidget(sr)
                        self._sec_rows[name] = sr
                    else:
                        sr = NavRow(tr(name), indent=px(22),
                                    on_click=lambda n=name: self._show_section(n),
                                    height=px(40))
                        sr.set_active(self._cur_section == name)
                        self._rail_lay.addWidget(sr)
                        self._sec_rows[name] = sr
        self._rail_lay.addStretch(1)

    def _nav_click(self, key):
        if key == self._page:
            return
        self._select_page(key)

    def _on_settings_nav(self):
        if self._page == "settings":
            self._settings_open = not self._settings_open
            self._rebuild_rail()
            self._apply_page_geometry()
        else:
            self._settings_open = True
            self._select_page("settings")

    def _refresh_rail_active(self):
        for key, row in self._nav_rows.items():
            row.set_active(self._page == key)
        for name, row in self._sec_rows.items():
            if name.startswith("group:"):
                g = name.split(":", 1)[1]
                row.set_active(self._cur_section in SECTION_GROUPS.get(g, []))
            else:
                row.set_active(self._cur_section == name)

    def _distribute_nav_compact(self):
        if self._page != "status":
            return
        keys = [k for k, _, _ in NAV
                if not (k == "settings" and self._cfg is None)]
        rows = [self._nav_rows[k] for k in keys if k in self._nav_rows]
        n = len(rows)
        if n < 2 or not hasattr(self, "_btn"):
            return
        try:
            item_h = rows[0].height()
            rail_top = self._rail.mapTo(self._frame, QPoint(0, 0)).y()
            y0 = self._phase_lbl.mapTo(
                self._frame, QPoint(0, self._phase_lbl.height() // 2)).y()
            sy = self._btn.mapTo(
                self._frame, QPoint(0, self._btn.height() // 2)).y()
        except Exception:
            return
        if sy <= y0:
            return
        center_gap = (sy - y0) / (n - 1)
        spacing = int(round(center_gap - item_h))
        spacing = max(px(2), spacing)
        top = int(round(y0 - rail_top - item_h / 2))
        top = max(0, top)
        m = self._rail_lay.contentsMargins()
        self._rail_lay.setContentsMargins(m.left(), top, m.right(), m.bottom())
        self._rail_lay.setSpacing(spacing)
        self._win.layout().activate()

    def _toggle_group(self, group):
        self._group_expanded[group] = not self._group_expanded.get(group, False)
        if self._group_expanded[group]:
            kids = SECTION_GROUPS.get(group, [])
            if kids:
                self._cur_section = kids[0]
                self._sec_stack.setCurrentIndex(self._sec_index[kids[0]])
                self._settings_sub.setText(tr(_child_label(kids[0])))
        self._rebuild_rail()
        self._apply_page_geometry()

    # ── Pages ──────────────────────────────────────────────────────────────
    def _build_status_page(self):
        page = QtWidgets.QWidget()
        page.setFixedWidth(px(330))
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(px(10), px(12), px(10), px(18))
        lay.setSpacing(0)

        line = QtWidgets.QHBoxLayout()
        line.setSpacing(px(6))
        self._phase_lbl = QtWidgets.QLabel(tr("IDLE"))
        self._phase_lbl.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(15)}px;"
            "font-weight:bold; background:transparent;")
        sep = QtWidgets.QLabel("/")
        sep.setStyleSheet(f"color:{_DIVIDER}; font-size:{fs(12)}px; background:transparent;")
        self._status_lbl = QtWidgets.QLabel(tr("ready to start"))
        self._status_lbl.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(10)}px; background:transparent;")
        line.addWidget(self._phase_lbl)
        line.addWidget(sep)
        line.addWidget(self._status_lbl)
        line.addStretch(1)
        lay.addLayout(line)

        self._bar = StateBar()
        lay.addSpacing(px(10))
        lay.addWidget(self._bar)
        lay.addSpacing(px(14))

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(px(9))
        grid.setVerticalSpacing(px(9))
        cells = (
            ("BOUGHT", "_bought", _IT_GREEN),
            ("SEARCHES", "_searches", _ROG),
            ("FAILED", "_fails", _RED_STAT),
            ("ACTIVE TIME", "_time", _ROG),
        )
        for i, (caption, attr, color) in enumerate(cells):
            r, c = divmod(i, 2)
            card = QtWidgets.QFrame()
            card.setStyleSheet(f"background:{_CARD}; border-radius:{px(16)}px;")
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(px(14), px(12), px(14), px(12))
            cl.setSpacing(px(2))
            val = QtWidgets.QLabel("00:00" if attr == "_time" else "0")
            val.setStyleSheet(
                f"color:{color}; font-family:'Sora','Segoe UI'; font-size:{fs(21)}px;"
                "font-weight:bold; background:transparent;")
            cap = QtWidgets.QLabel(tr(caption))
            cap.setStyleSheet(
                f"color:{_FAINT}; font-family:'Sora','Segoe UI'; font-size:{fs(9)}px;"
                "font-weight:bold; background:transparent;")
            cl.addWidget(val)
            cl.addWidget(cap)
            card.setMinimumHeight(px(88))
            grid.addWidget(card, r, c)
            self._value_labels[attr] = val
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        lay.addSpacing(px(15))
        self._btn = PillButton(tr("START"), base=_BTN_BG, hover=_BTN_HV, fg=_BTN_FG)
        lay.addWidget(self._btn)

        lay.addSpacing(px(12))
        start = hotkey_label(getattr(self._cfg, "hotkey_start_stop", "<f8>")
                             if self._cfg is not None else "<f8>")
        panic = hotkey_label(getattr(self._cfg, "hotkey_panic", "<f9>")
                             if self._cfg is not None else "<f9>")
        footer = QtWidgets.QLabel(
            f"{start}  {tr('start / stop')}      \u00b7      {panic}  {tr('panic / quit')}")
        footer.setObjectName("hotkeyFooter")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(10)}px; background:transparent;")
        self._hotkey_footer = footer
        lay.addWidget(footer)
        lay.addStretch(1)
        return page

    def _page_header(self, lay, title, subtitle):
        t = QtWidgets.QLabel(tr(title))
        t.setStyleSheet(
            f"color:{_ROG}; font-family:'Sora','Segoe UI'; font-size:{fs(26)}px;"
            "font-weight:bold; background:transparent;")
        lay.addWidget(t)
        sub = QtWidgets.QLabel(tr(subtitle) if subtitle else "")
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(12)}px; background:transparent;")
        lay.addWidget(sub)
        return sub

    def _build_settings_page(self):
        page = QtWidgets.QWidget()
        page.setFixedWidth(px(600))
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(px(10), px(12), px(10), px(18))
        lay.setSpacing(px(2))
        if self._cfg is None:
            msg = QtWidgets.QLabel(tr("Settings unavailable."))
            msg.setStyleSheet(f"color:{_DIM}; font-size:{fs(10)}px;")
            lay.addWidget(msg)
            lay.addStretch(1)
            return page

        self._settings_sub = self._page_header(lay, "Settings", "")
        lay.addSpacing(px(20))

        self._sec_stack = QtWidgets.QStackedWidget()
        lay.addWidget(self._sec_stack, 1)

        sections = []
        cur = None
        for spec in SETTINGS_SPEC:
            if isinstance(spec, tuple) and spec[0] == "section":
                cur = (spec[1], [])
                sections.append(cur)
            else:
                if cur is None:
                    cur = ("General", [])
                    sections.append(cur)
                cur[1].append(spec)

        for name, specs in sections:
            sec = QtWidgets.QWidget()
            sl = QtWidgets.QVBoxLayout(sec)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(px(16))
            for spec in specs:
                sl.addWidget(self._add_setting_row(spec))
            sl.addStretch(1)
            self._sec_index[name] = self._sec_stack.addWidget(sec)

        if sections:
            self._cur_section = sections[0][0]
            self._settings_sub.setText(tr(_child_label(sections[0][0])))
        return page

    def _add_setting_row(self, spec):
        if spec.get("kind") == "note":
            row = QtWidgets.QWidget()
            v = QtWidgets.QVBoxLayout(row)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(px(2))
            if spec.get("label"):
                lab = QtWidgets.QLabel(tr(spec["label"]))
                lab.setStyleSheet(
                    f"color:{_ROG}; font-family:'Sora','Segoe UI'; font-size:{fs(14)}px;"
                    "font-weight:bold; background:transparent;")
                v.addWidget(lab)
            if spec.get("desc"):
                d = QtWidgets.QLabel(tr(spec["desc"]))
                d.setWordWrap(True)
                d.setStyleSheet(
                    f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(13)}px;"
                    " background:transparent;")
                v.addWidget(d)
            return row
        key, kind = spec["key"], spec["kind"]
        cur = getattr(self._cfg, key, None)
        row = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(px(12))

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(px(2))
        lab = QtWidgets.QLabel(tr(spec["label"]))
        lab.setWordWrap(True)
        lab.setStyleSheet(
            f"color:{_ROG}; font-family:'Sora','Segoe UI'; font-size:{fs(14)}px;"
            "font-weight:bold; background:transparent;")
        desc = QtWidgets.QLabel(tr(spec["desc"]))
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(13)}px; background:transparent;")
        left.addWidget(lab)
        left.addWidget(desc)
        left_box = QtWidgets.QWidget()
        left_box.setLayout(left)
        left_box.setFixedWidth(px(308))
        h.addWidget(left_box, 0, Qt.AlignTop)
        h.addStretch(1)

        ctrl = QtWidgets.QVBoxLayout()
        ctrl.setSpacing(px(4))
        ctrl.setAlignment(Qt.AlignTop | Qt.AlignRight)
        slider_w = px(160)
        ctrl_w = px(26) + px(6) + slider_w + px(6) + px(46)

        if kind == "toggle":
            grp = spec.get("exclusive_group")

            def cmd(v, k=key, g=grp):
                if g and v:
                    for ok, (okind, ow) in self._setting_widgets.items():
                        if (okind == "toggle" and ok != k
                                and self._excl_group.get(ok) == g):
                            ow.set(False)
                if k == "overlay_capturable":
                    self._set_capturable(v)
                self._autosave()
            tg = ToggleSwitch(value=bool(cur), command=cmd)
            wrap = QtWidgets.QWidget()
            wrap.setFixedWidth(ctrl_w)
            wl = QtWidgets.QHBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.addStretch(1)
            wl.addWidget(tg)
            ctrl.addWidget(wrap, 0, Qt.AlignRight)
            self._setting_widgets[key] = ("toggle", tg)
            if grp:
                self._excl_group[key] = grp

        elif kind == "slider":
            ctrl.addWidget(self._make_slider_line(
                key, cur, spec, slider_w, tag=""), 0, Qt.AlignRight)
            self._setting_widgets[key] = ("slider", self._last_slider)

        elif kind == "range":
            lo_cur, hi_cur = (cur if isinstance(cur, (tuple, list))
                              else (spec["lo"], spec["hi"]))
            sliders = []
            for sub, sval in (("min", lo_cur), ("max", hi_cur)):
                ctrl.addWidget(self._make_slider_line(
                    key + ":" + sub, sval, spec, slider_w, tag=sub),
                    0, Qt.AlignRight)
                sliders.append(self._last_slider)
            self._setting_widgets[key] = ("range", tuple(sliders))

        elif kind == "text":
            ent = QtWidgets.QLineEdit("" if cur is None else str(cur))
            ent.setFixedWidth(ctrl_w)
            ent.setStyleSheet(
                f"background:{_CARD}; color:{_ROG}; border:1px solid {_DIVIDER};"
                f"border-radius:{px(4)}px; padding:{px(4)}px; font-family:'Sora','Segoe UI';"
                f"font-size:{fs(13)}px;")
            ent.textEdited.connect(lambda _t: self._autosave_soon())
            ent.editingFinished.connect(self._autosave)
            ctrl.addWidget(ent, 0, Qt.AlignRight)
            self._setting_widgets[key] = ("text", ent)

        elif kind == "color":
            default_hex = _COLOR_DEFAULTS.get(key, "#000000")
            btn = ColorButton(
                cur if cur else default_hex,
                on_open=lambda b, k=key, d=default_hex:
                    self._open_color_picker(k, b, d),
                width=ctrl_w)
            ctrl.addWidget(btn, 0, Qt.AlignRight)
            self._setting_widgets[key] = ("color", btn)

        elif kind == "keybind":
            btn = KeybindButton(
                cur,
                on_capture=lambda v, k=key: self._on_keybind_captured(k, v),
                on_active=self._on_keybind_capture_active,
                width=ctrl_w)
            ctrl.addWidget(btn, 0, Qt.AlignRight)
            self._setting_widgets[key] = ("keybind", btn)

        elif kind == "dropdown":
            opts = spec.get("options")
            if opts == "languages":
                opts = list(locales.available())
            else:
                opts = list(opts or [])
            if key == "language":
                on_change = self._on_language_changed
            elif key == "game_language":
                on_change = self._on_game_language_changed
            else:
                on_change = lambda _v: self._autosave()
            dd = Dropdown(cur, opts, on_change=on_change, width=ctrl_w)
            ctrl.addWidget(dd, 0, Qt.AlignRight)
            self._setting_widgets[key] = ("dropdown", dd)

        h.addLayout(ctrl)
        return row

    def _make_slider_line(self, vkey, value, spec, slider_w, tag=""):
        cont = QtWidgets.QWidget()
        cont.setFixedWidth(px(46) + px(6) + slider_w + px(6) + px(26))
        line = QtWidgets.QHBoxLayout(cont)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(px(6))
        vlab = QtWidgets.QLabel(_fmt(value, spec["int"]))
        vlab.setFixedWidth(px(46))
        vlab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        vlab.setStyleSheet(
            f"color:{_ROG}; font-family:'Sora','Segoe UI'; font-size:{fs(13)}px;"
            "font-weight:bold; background:transparent;")
        tg = QtWidgets.QLabel(tag)
        tg.setFixedWidth(px(26))
        tg.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tg.setStyleSheet(f"color:{_DIM}; font-size:{fs(11)}px; background:transparent;")
        sl = Slider(value, spec["lo"], spec["hi"], spec["step"], spec["int"],
                    slider_w,
                    on_change=lambda v, lb=vlab, i=spec["int"], k=vkey:
                        self._on_slider_change(lb, v, i, k))
        line.addWidget(vlab)
        line.addWidget(sl)
        line.addWidget(tg)
        self._last_slider = sl
        return cont

    def _build_logs_page(self):
        page = QtWidgets.QWidget()
        page.setFixedWidth(px(600))
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(px(10), px(12), px(10), px(18))
        lay.setSpacing(px(8))
        self._page_header(lay, "Logs", "Safe to share: no keys or personal data.")

        bar = QtWidgets.QHBoxLayout()
        self._log_filter = QtWidgets.QLineEdit()
        self._log_filter.setStyleSheet(
            f"background:{_CARD}; color:{_ROG}; border:1px solid {_DIVIDER};"
            f"border-radius:{px(4)}px; padding:{px(3)}px; font-family:'Sora','Segoe UI';"
            f"font-size:{fs(12)}px;")
        self._log_filter.textChanged.connect(self._render_logs)
        bar.addWidget(self._log_filter, 1)
        copy = PillButton(tr("COPY"), height=px(34), command=self._copy_logs,
                          base=_BTN_BG, hover=_BTN_HV, fg=_BTN_FG)
        copy.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                           QtWidgets.QSizePolicy.Fixed)
        copy.setFixedWidth(px(96))
        bar.addWidget(copy)
        lay.addLayout(bar)

        self._log_text = QtWidgets.QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(
            f"background:{_CARD}; color:{_DIM}; border-radius:{px(14)}px;"
            f"padding:{px(6)}px; font-family:'Fira Code','Consolas','Courier New';"
            f"font-size:{fs(13)}px;")
        lay.addWidget(self._log_text, 1)
        self._render_logs()
        return page

    def _build_help_page(self):
        page = QtWidgets.QWidget()
        page.setFixedWidth(px(600))
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(px(10), px(12), px(10), px(18))
        lay.setSpacing(px(2))
        self._page_header(lay, "Help", "Quick start and troubleshooting.")
        lay.addSpacing(px(10))
        blocks = [
            ("Step 1 \u2013 Open the Auction House", [
                "Launch Forza Horizon 6 and go to the Auction House on the "
                "festival site.",
            ]),
            ("Step 2 \u2013 Configure the search", [
                "Open Search Auctions and set the filters:",
                "\u2022 Make and Model of the car you want.",
                "\u2022 Maximum buyout price as a safety limit. The bot buys the "
                "first matching car without checking the price, so this is the "
                "most you can spend per car. Set it carefully.",
                "Go back so the screen shows the main Auction House Screen. "
                "That's where the bot expects to start.",
            ]),
            ("Step 3 \u2013 Start the sniper", [
                "Right-click AuctionSniper.exe and run as administrator. A small "
                "overlay will appear in the top-right corner of the screen.",
                "Go back to FH6, press F8 or Start, and let it run.",
                "To stop: press F8 again, F9 for emergency stop, or click STOP "
                "on the overlay.",
            ]),
        ]
        for title, lines in blocks:
            tl = QtWidgets.QLabel(tr(title))
            tl.setStyleSheet(
                f"color:{_ROG}; font-family:'Sora','Segoe UI'; font-size:{fs(14)}px;"
                "font-weight:bold; background:transparent;")
            lay.addSpacing(px(10))
            lay.addWidget(tl)
            for ln in lines:
                if isinstance(ln, tuple):
                    text = tr(ln[0], **ln[1])
                else:
                    text = tr(ln)
                wl = QtWidgets.QLabel(text)
                wl.setWordWrap(True)
                wl.setStyleSheet(
                    f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(13)}px; background:transparent;")
                lay.addWidget(wl)
        lay.addStretch(1)
        return page

    def _build_about_page(self):
        page = QtWidgets.QWidget()
        page.setFixedWidth(px(600))
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(px(10), px(12), px(10), px(18))
        lay.setSpacing(px(4))
        self._page_header(lay, "Info", "")
        body = QtWidgets.QLabel(tr(
            "This is an updated and improved version of Frosty's FH6 Auction Sniper. " \
            "It is completely unrelated to Frosty's paid V2. " \
            "If you need support or want to contribute to "
            "the tool's development, feel free to join the dedicated Discord server."))
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(13)}px; background:transparent;")
        lay.addWidget(body)
        lay.addSpacing(px(10))
        btn = PillButton(tr("Join the Discord"), height=px(40),
                         base=_BTN_BG, hover=_BTN_HV, fg=_BTN_FG,
                         command=lambda: webbrowser.open("https://discord.gg/4fbQ7yNns8"))
        btn.setFixedWidth(px(220))
        wrap = QtWidgets.QHBoxLayout()
        wrap.addStretch(1)
        wrap.addWidget(btn)
        wrap.addStretch(1)
        lay.addLayout(wrap)
        lay.addSpacing(px(14))
        vt = QtWidgets.QLabel(tr("Version"))
        vt.setStyleSheet(
            f"color:{_ROG}; font-family:'Sora','Segoe UI'; font-size:{fs(14)}px;"
            "font-weight:bold; background:transparent;")
        lay.addWidget(vt)
        vv = QtWidgets.QLabel("V.2.1.0  \u00b7  Created by d1ablo")
        vv.setStyleSheet(
            f"color:{_DIM}; font-family:'Sora','Segoe UI'; font-size:{fs(13)}px; background:transparent;")
        lay.addWidget(vv)
        lay.addStretch(1)
        return page

    # ── Page / section switching ─────────────────────────────────────────
    def _select_page(self, key, refit=True):
        if key not in self._pages:
            return
        same = (key == self._page_in_holder)
        self._page = key
        if not same:
            if self._page_in_holder is not None and \
                    self._page_in_holder in self._pages:
                old = self._pages[self._page_in_holder]
                self._content_lay.removeWidget(old)
                old.hide()
            page = self._pages[key]
            self._content_lay.addWidget(page)
            page.show()
            self._page_in_holder = key
        self._rebuild_rail()
        if key == "settings" and self._cur_section:
            idx = self._sec_index.get(self._cur_section)
            if idx is not None:
                self._sec_stack.setCurrentIndex(idx)
        if key == "logs":
            self._render_logs()
        if refit:
            self._apply_page_geometry()

    def _show_section(self, name):
        if name not in self._sec_index:
            return
        self._cur_section = name
        self._sec_stack.setCurrentIndex(self._sec_index[name])
        self._settings_sub.setText(tr(_child_label(name)))
        self._refresh_rail_active()
        self._apply_page_geometry()

    # ── Geometry: window auto-fits content; we only position it ────────────
    def _worst_rail_height(self):
        nav_n = len([1 for k, _, _ in NAV
                     if not (k == "settings" and self._cfg is None)])
        h = px(10) * 2 + nav_n * px(46)
        rows = nav_n
        if self._cfg is not None:
            seen = set()
            for spec in SETTINGS_SPEC:
                if not (isinstance(spec, tuple) and spec[0] == "section"):
                    continue
                name = spec[1]
                grp = _CHILD_TO_GROUP.get(name)
                if grp:
                    if grp not in seen:
                        seen.add(grp)
                        h += px(40)
                        rows += 1
                    h += px(38)
                    rows += 1
                else:
                    h += px(40)
                    rows += 1
        h += px(2) * max(0, rows - 1)
        return h

    def _equalize_wide_pages(self):
        wide_keys = ("settings", "logs", "help", "about")
        saved = self._page_in_holder
        if saved and saved in self._pages:
            self._content_lay.removeWidget(self._pages[saved])
            self._pages[saved].hide()
            self._page_in_holder = None
        probe = QtWidgets.QWidget()
        probe.setAttribute(Qt.WA_DontShowOnScreen, True)
        pl = QtWidgets.QVBoxLayout(probe)
        pl.setContentsMargins(0, 0, 0, 0)
        probe.resize(px(600) + 20, 1400)
        probe.show()
        maxh = 0
        for k in wide_keys:
            pg = self._pages[k]
            pg.setMinimumHeight(0)
            pg.setMaximumHeight(16777215)
            pl.addWidget(pg)
            pg.show()
            pl.activate()
            QtWidgets.QApplication.processEvents()
            need = max(pg.sizeHint().height(),
                       pg.layout().minimumSize().height())
            maxh = max(maxh, need)
            pl.removeWidget(pg)
            pg.setParent(self._content)
            pg.hide()
        probe.deleteLater()
        maxh = max(maxh, self._worst_rail_height())
        for k in wide_keys:
            self._pages[k].setFixedHeight(maxh)
        self._wide_h = maxh
        if saved and saved in self._pages:
            self._content_lay.addWidget(self._pages[saved])
            self._pages[saved].show()
            self._page_in_holder = saved

    def _screen_at(self, point=None):
        if point is None:
            point = self._win.frameGeometry().center()
        s = self._app.screenAt(point)
        return s or self._win.screen() or self._app.primaryScreen()

    def _virtual_rect(self):
        s = self._win.screen() or self._app.primaryScreen()
        return s.virtualGeometry()

    def _clamp_position(self):
        geo = self._screen_at().availableGeometry()
        w, h = self._win.width(), self._win.height()
        g = self._win.geometry()
        x = min(g.left(), geo.right() - w - 8)
        x = max(geo.left() + 8, x)
        y = min(g.top(), geo.bottom() - h - 8)
        y = max(geo.top() + 8, y)
        if x != g.left() or y != g.top():
            self._win.move(int(x), int(y))

    def _apply_page_geometry(self, initial=False):
        if initial or not self._win.isVisible():
            self._geometry_pass(initial=True)
        else:
            QTimer.singleShot(0, lambda: self._geometry_pass(initial=False))

    def _geometry_pass(self, initial=False):
        try:
            self._geometry_pass_impl(initial=initial)
        except Exception:
            logging.getLogger("fh6").exception("geometry pass failed")

    def _geometry_pass_impl(self, initial=False):
        if self._wide_h is None and self._win.isVisible():
            self._equalize_wide_pages()
        old = self._win.geometry()
        self._win.layout().activate()
        sh = self._win.sizeHint()
        mh = self._win.minimumSizeHint()
        w = max(sh.width(), mh.width())
        h = max(sh.height(), mh.height())
        if initial or not self._win.isVisible():
            screen = self._app.primaryScreen()
        else:
            screen = self._screen_at(old.center())
        geo = screen.availableGeometry()
        if initial or not self._win.isVisible():
            x = geo.right() - w - 24
            y = geo.top() + 24
        else:
            x = old.right() + 1 - w
            y = old.top()
        x = min(x, geo.right() - w - 8)
        x = max(geo.left() + 8, x)
        y = min(y, geo.bottom() - h - 8)
        y = max(geo.top() + 8, y)
        target = QRect(int(x), int(y), int(w), int(h))
        animate = self._win.isVisible() and not initial
        self._set_geometry(target, animate)
        if not animate:
            QTimer.singleShot(0, self._finalize_after_layout)

    def _set_geometry(self, rect, animate):
        if not animate:
            self._win.setGeometry(rect)
            return
        old = self._win.geometry()
        growing = (rect.width() > old.width() + 1
                   or rect.height() > old.height() + 1)
        cov = getattr(self, "_cover", None)
        if cov is not None and growing:
            cov.setGeometry(0, 0, max(old.width(), rect.width()),
                            max(old.height(), rect.height()))
            cov.show()
            cov.raise_()
        anim = getattr(self, "_geo_anim", None)
        if anim is not None:
            anim.stop()
        anim = QtCore.QPropertyAnimation(self._win, b"geometry")
        anim.setDuration(190)
        anim.setStartValue(old)
        anim.setEndValue(rect)
        anim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        anim.finished.connect(self._finalize_after_layout)
        self._geo_anim = anim
        anim.start()

    def _finalize_after_layout(self):
        try:
            self._distribute_nav_compact()
            self._clamp_position()
            cov = getattr(self, "_cover", None)
            if cov is not None:
                cov.hide()
        except Exception:
            logging.getLogger("fh6").exception("finalize layout failed")

    # ── Drag ──────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_off = e.globalPosition().toPoint() - self._win.pos()

    def _drag_move(self, e):
        if self._drag_off is None:
            return
        target = e.globalPosition().toPoint() - self._drag_off
        vr = self._virtual_rect()
        w, h = self._win.width(), self._win.height()
        x = max(vr.left(), min(target.x(), vr.right() - w))
        y = max(vr.top(), min(target.y(), vr.bottom() - h))
        self._win.move(int(x), int(y))

    # ── Status / state ────────────────────────────────────────────────────
    def _set_button(self, running):
        self._btn.set_mode(tr("STOP") if running else tr("START"),
                           _BTN_BG, _BTN_HV, _BTN_FG)

    def _retint(self):
        src = (self._status_src or "").lower()
        if not self._running:
            phase, color, bar = "IDLE", _DIM, "idle"
        elif "paused" in src:
            phase, color, bar = "PAUSED", _SECONDARY, "paused"
        else:
            phase, color, bar = "ACTIVE", _ROG, "running"
        self._phase_lbl.setText(tr(phase))
        self._phase_lbl.setStyleSheet(
            f"color:{color}; font-family:'Sora','Segoe UI'; font-size:{fs(15)}px;"
            "font-weight:bold; background:transparent;")
        self._dot.set_color(color)
        self._bar.set_state(bar)

    @QtCore.Slot(str, object)
    def _apply_status(self, msg, kwargs=None):
        self._status_src = msg
        self._status_kwargs = dict(kwargs or {})
        self._status_lbl.setText(tr(msg, **self._status_kwargs))
        self._retint()

    @QtCore.Slot(bool)
    def _apply_running(self, running):
        self._running = bool(running)
        self._set_button(self._running)
        self._active = self._running
        if self._running and self._started is None:
            self._started = time.monotonic()
            self._value_labels["_time"].setText("00:00")
        self._retint()

    @QtCore.Slot(int, int, int)
    def _apply_stats(self, searches, bought, fails):
        self._value_labels["_searches"].setText(str(searches))
        self._value_labels["_bought"].setText(str(bought))
        self._value_labels["_fails"].setText(str(fails))

    def _tick(self):
        if self._active and self._started is not None:
            m, s = divmod(int(time.monotonic() - self._started), 60)
            self._value_labels["_time"].setText(f"{m:02d}:{s:02d}")

    # ── Settings persistence ──────────────────────────────────────────────
    def _on_slider_change(self, label, v, is_int, key=None):
        label.setText(_fmt(v, is_int))
        self._autosave_soon()
        if key == "ui_scale":
            self._scale_soon(v)

    def _collect(self):
        out = {}
        for key, (kind, w) in self._setting_widgets.items():
            if kind == "range":
                out[key] = (kind, (w[0].get(), w[1].get()))
            elif kind == "text":
                out[key] = (kind, w.text())
            else:
                out[key] = (kind, w.get())
        return out

    @staticmethod
    def _apply_collected(cfg, collected):
        for key, (kind, val) in collected.items():
            if kind == "toggle":
                setattr(cfg, key, bool(val))
            elif kind == "slider":
                setattr(cfg, key, val)
            elif kind == "range":
                a, b = val
                lo, hi = (a, b) if a <= b else (b, a)
                setattr(cfg, key, (lo, hi))
            elif kind == "text":
                setattr(cfg, key, str(val).strip())
            elif kind == "color":
                setattr(cfg, key, str(val).strip())
            elif kind == "keybind":
                setattr(cfg, key, str(val).strip())
            elif kind == "dropdown":
                setattr(cfg, key, str(val))

    def _autosave(self):
        if self._cfg is None or not self._ready:
            return
        self._apply_collected(self._cfg, self._collect())
        if self._on_save:
            try:
                self._on_save(self._cfg)
            except Exception:
                pass
        self._show_toast()

    def _on_keybind_captured(self, key, value):
        if self._cfg is not None:
            setattr(self._cfg, key, str(value))
        if self._on_save:
            try:
                self._on_save(self._cfg)
            except Exception:
                pass
        if self._on_hotkeys_changed:
            try:
                self._on_hotkeys_changed(self._cfg)
            except Exception:
                pass
        self._refresh_hotkey_hints()
        self._show_toast(tr("Bound: {label}", label=hotkey_label(value)))

    def set_hotkeys_changed(self, callback):
        self._on_hotkeys_changed = callback

    def set_game_language_changed(self, callback):
        self._on_game_lang_changed = callback

    def _on_game_language_changed(self, _code):
        self._autosave()
        if self._on_game_lang_changed:
            try:
                self._on_game_lang_changed(self._cfg)
            except Exception:
                logging.getLogger("fh6").exception(
                    "reload templates for game language failed")

    def _on_language_changed(self, code):
        if self._cfg is not None:
            setattr(self._cfg, "language", str(code))
        locales.set_language(str(code))
        if self._on_save:
            try:
                self._on_save(self._cfg)
            except Exception:
                pass
        self._rebuild_all()
        self._show_toast()

    def _on_keybind_capture_active(self, active):
        if self._on_capture_active:
            try:
                self._on_capture_active(bool(active))
            except Exception:
                logging.getLogger("fh6").exception(
                    "hotkey suspend/resume failed")

    def set_capture_active_cb(self, callback):
        self._on_capture_active = callback

    def _refresh_hotkey_hints(self):
        if self._cfg is None:
            return
        start = hotkey_label(getattr(self._cfg, "hotkey_start_stop", ""))
        panic = hotkey_label(getattr(self._cfg, "hotkey_panic", ""))
        lbl = None
        page = self._pages.get("status") if hasattr(self, "_pages") else None
        if page is not None:
            try:
                lbl = page.findChild(QtWidgets.QLabel, "hotkeyFooter")
            except Exception:
                lbl = None
        if lbl is None:
            lbl = getattr(self, "_hotkey_footer", None)
        if lbl is not None:
            try:
                lbl.setText(f"{start}  {tr('start / stop')}      \u00b7      "
                            f"{panic}  {tr('panic / quit')}")
            except Exception:
                pass

    def _autosave_soon(self, delay=450):
        if not self._ready:
            return
        if self._autosave_timer is None:
            self._autosave_timer = QTimer(self._win)
            self._autosave_timer.setSingleShot(True)
            self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(delay)

    def _show_toast(self, text=None):
        if text is None:
            text = tr("Saved \u2713")
        self._toast.setText(text)
        self._toast.show()
        self._toast_timer.start(1300)

    # ── Live UI scale ─────────────────────────────────────────────────────
    def _scale_soon(self, value):
        if self._scale_timer is None:
            self._scale_timer = QTimer(self._win)
            self._scale_timer.setSingleShot(True)
            self._scale_timer.timeout.connect(self._do_scale)
        self._pending_scale = value
        self._scale_timer.start(300)

    def _do_scale(self):
        value = max(UI_SCALE_MIN, min(UI_SCALE_MAX, float(self._pending_scale)))
        if abs(value - _SCALE) < 1e-3:
            return
        if self._cfg is not None:
            setattr(self._cfg, "ui_scale", value)
        _set_scale(value)
        self._wide_h = None
        self._rebuild_all()

    def _rebuild_all(self):
        status_src = self._status_src
        status_kwargs = dict(self._status_kwargs)
        running = self._running
        section = self._cur_section
        page = self._page
        old_layout = self._win.layout()
        if old_layout is not None:
            trash = QtWidgets.QWidget()
            trash.setLayout(old_layout)
            trash.deleteLater()
        self._setting_widgets = {}
        self._excl_group = {}
        self._sec_index = {}
        self._value_labels = {}
        self._nav_rows = {}
        self._sec_rows = {}
        self._page = page
        self._cur_section = section
        self._build_ui()
        if section and section in self._sec_index:
            self._cur_section = section
            self._sec_stack.setCurrentIndex(self._sec_index[section])
            self._settings_sub.setText(tr(_child_label(section)))
        self._apply_running(running)
        self._apply_status(status_src, status_kwargs)
        if self._toggle_cb is not None:
            self._btn.set_command(self._toggle_cb)
        self._select_page(page, refit=False)
        self._apply_page_geometry()
        if self._color_popup is not None and self._color_popup.isVisible():
            self._color_popup.raise_()
        if self._on_save and self._cfg is not None:
            try:
                self._on_save(self._cfg)
            except Exception:
                pass

    # ── Live colour theme ─────────────────────────────────────────────────
    def _open_color_picker(self, key, button, default_hex):
        if self._color_popup is not None:
            try:
                self._color_popup._dismiss()
            except Exception:
                pass
            self._color_popup = None
        self._active_color_key = key
        popup = ColorPickerPopup(
            button.get(), default_hex,
            on_change=lambda c, final, k=key: self._set_role_color(k, c, final),
            parent=self._win)
        self._color_popup = popup
        popup.destroyed.connect(lambda *_: self._clear_popup_ref(popup))
        popup.show_at(button)

    def _clear_popup_ref(self, popup):
        if self._color_popup is popup:
            self._color_popup = None
            self._active_color_key = None

    def _set_role_color(self, key, qcolor, final):
        hexs = _color_to_hex(qcolor)
        if self._cfg is not None:
            setattr(self._cfg, key, hexs)
        _apply_theme_from_cfg(self._cfg)
        w = self._setting_widgets.get(key)
        if w and w[0] == "color":
            try:
                w[1].set_color(hexs)
            except Exception:
                pass
        if final:
            if self._theme_timer is not None:
                self._theme_timer.stop()
            self._rebuild_all()
            self._show_toast()
        else:
            self._theme_soon()

    def _theme_soon(self, delay=180):
        if self._theme_timer is None:
            self._theme_timer = QTimer(self._win)
            self._theme_timer.setSingleShot(True)
            self._theme_timer.timeout.connect(self._rebuild_all)
        self._theme_timer.start(delay)

    # ── Logs ────────────────────────────────────────────────────────────────
    @QtCore.Slot(str)
    def _add_log(self, msg):
        self._logs.append((time.strftime("%H:%M:%S"), str(msg)))
        if self._page == "logs":
            self._render_logs()

    def _render_logs(self):
        if not hasattr(self, "_log_text"):
            return
        flt = self._log_filter.text().strip().lower()
        rows = list(self._logs)
        if not rows:
            self._log_text.setPlainText(tr("  no events yet."))
            return
        lines = []
        for ts, msg in rows:
            line = f"{ts}  {msg}"
            if flt and flt not in line.lower():
                continue
            lines.append(line)
        self._log_text.setPlainText("\n".join(lines))
        sb = self._log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _copy_logs(self):
        text = "\n".join(f"{ts}  {msg}" for ts, msg in self._logs)
        QtWidgets.QApplication.clipboard().setText(text)

    # ── Windows: capture exclusion + rounded corners ──────────────────────
    def _hwnd(self):
        try:
            return int(self._win.winId())
        except Exception:
            return 0

    def _set_capturable(self, capturable):
        if not sys.platform.startswith("win"):
            return
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(
                self._hwnd(), 0x00 if capturable else 0x11)
        except Exception:
            pass

    def _exclude_from_capture(self):
        self._set_capturable(False)

    def _round_window_corners(self):
        if not sys.platform.startswith("win"):
            return
        try:
            val = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                self._hwnd(), 33, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

    def _on_close_event(self, e):
        try:
            self._app.quit()
        except Exception:
            pass
        e.accept()

    # ── Public API (thread-safe) ──────────────────────────────────────────
    def set_status(self, msg, kwargs=None):
        self._bridge.status.emit(str(msg), dict(kwargs or {}))

    def set_running(self, running):
        self._bridge.running.emit(bool(running))

    def set_stats(self, searches, bought, fails):
        self._bridge.stats.emit(int(searches), int(bought), int(fails))

    def log(self, msg):
        self._bridge.logmsg.emit(str(msg))

    def attach_logging(self, logger=None, level=logging.INFO,
                       fmt="%(message)s"):
        handler = _OverlayLogHandler(self)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(fmt))
        target = logger if logger is not None else logging.getLogger()
        target.addHandler(handler)
        self._log_handler = handler
        return handler

    def on_toggle(self, callback):
        self._toggle_cb = callback
        self._btn.set_command(callback)

    def set_stats_safe(self, *a):
        self.set_stats(*a)

    def run(self):
        self._win.show()
        if not self._hide_from_capture:
            self._set_capturable(True)
        else:
            self._exclude_from_capture()
        self._round_window_corners()
        QTimer.singleShot(0, lambda: self._apply_page_geometry(initial=True))
        self._app.exec()

    def close(self):
        try:
            self._win.close()
        except Exception:
            pass

    @QtCore.Slot()
    def _do_quit(self):
        try:
            self._win.close()
        except Exception:
            pass
        try:
            self._app.quit()
        except Exception:
            pass

    def request_close(self):
        self._bridge.quit.emit()

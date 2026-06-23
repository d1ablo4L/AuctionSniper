from __future__ import annotations
import logging
from enum import Enum, auto
from pathlib import Path
import cv2
import numpy as np

_diag = logging.getLogger("fh6_matchdiag")


class Screen(Enum):
    UNKNOWN = auto()
    SEARCH_CONFIG = auto()
    RESULTS_HAS_CARS = auto()
    RESULTS_EMPTY = auto()
    AUCTION_OPTIONS = auto()
    PLAYER_OPTIONS = auto()
    BUY_OUT = auto()
    BUYOUT_PROGRESS = auto()
    BUYOUT_SUCCESS = auto()
    BUYOUT_FAILED = auto()
    CLAIM_CAR = auto()
    AH_LANDING = auto()


TEMPLATE_SCREENS: dict[str, Screen] = {
    "search.png": Screen.SEARCH_CONFIG,
    "auction_details.png": Screen.RESULTS_HAS_CARS,
    "no_auctions.png": Screen.RESULTS_EMPTY,
    "auction_options.png": Screen.AUCTION_OPTIONS,
    "player_options.png": Screen.PLAYER_OPTIONS,
    "buy_out.png": Screen.BUY_OUT,
    "buy_out_bgoff.png": Screen.BUY_OUT,
    "buy_out_progress.png": Screen.BUYOUT_PROGRESS,
    "buy_out_progress_bgoff.png": Screen.BUYOUT_PROGRESS,
    "buyout_successful.png": Screen.BUYOUT_SUCCESS,
    "buyout_failed.png": Screen.BUYOUT_FAILED,
    "claim_car.png": Screen.CLAIM_CAR,
    "ah_landing.png": Screen.AH_LANDING,
}


SCREEN_THRESHOLD_KEYS: dict[Screen, str] = {
    Screen.SEARCH_CONFIG:    "match_threshold_search",
    Screen.RESULTS_HAS_CARS: "match_threshold_results",
    Screen.RESULTS_EMPTY:    "match_threshold_results_empty",
    Screen.AUCTION_OPTIONS:  "match_threshold_auction_options",
    Screen.PLAYER_OPTIONS:   "match_threshold_player_options",
    Screen.BUY_OUT:          "match_threshold_buy_out",
    Screen.BUYOUT_PROGRESS:  "match_threshold_buyout_progress",
    Screen.BUYOUT_SUCCESS:   "match_threshold_buyout_success",
    Screen.BUYOUT_FAILED:    "match_threshold_buyout_failed",
    Screen.CLAIM_CAR:        "match_threshold_claim_car",
    Screen.AH_LANDING:       "match_threshold_ah_landing",
}

DEFAULT_MATCH_THRESHOLD = 0.80


def thresholds_from_config(cfg) -> dict:
    default = getattr(cfg, "match_threshold", DEFAULT_MATCH_THRESHOLD)
    out = {}
    for scr, key in SCREEN_THRESHOLD_KEYS.items():
        v = getattr(cfg, key, None)
        out[scr] = default if v is None else v
    return out


# ── Template matching ─────────────────────────────────────────────────────────
def _gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def match_template(scene: np.ndarray, template: np.ndarray) -> float:
    s, t = _gray(scene), _gray(template)
    if t.shape[0] > s.shape[0] or t.shape[1] > s.shape[1]:
        return 0.0
    result = cv2.matchTemplate(s, t, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return float(max_val)


_DOWNSCALED_TEMPLATES: dict[int, np.ndarray] = {}


def _small(tmpl: np.ndarray) -> np.ndarray:
    key = id(tmpl)
    cached = _DOWNSCALED_TEMPLATES.get(key)
    if cached is None:
        cached = _downscale(tmpl)
        _DOWNSCALED_TEMPLATES[key] = cached
    return cached


def _resolve_template(primary_dir, name, fallback_dir):
    p = Path(primary_dir) / name
    if p.exists():
        return p
    if fallback_dir is not None:
        fp = Path(fallback_dir) / name
        if fp.exists():
            logging.getLogger("fh6").warning(
                "template '%s' not found in %s: using fallback %s",
                name, primary_dir, fallback_dir)
            return fp
    return p


def load_templates(template_dir, fallback_dir=None) -> dict:
    _DOWNSCALED_TEMPLATES.clear()
    out = {}
    for name in TEMPLATE_SCREENS:
        if _has_bgoff_variant(name):
            continue
        path = _resolve_template(template_dir, name, fallback_dir)
        img = cv2.imread(str(path))
        if img is None:
            raise FileNotFoundError(f"template missing: {path}")
        gray = _gray(img)
        out[name] = gray
        _DOWNSCALED_TEMPLATES[id(gray)] = _downscale(gray)
    global _SOLD_TEMPLATE, _SOLD_MASK
    sold_path = _resolve_template(template_dir, SOLD_TEMPLATE_NAME, fallback_dir)
    sold_img = cv2.imread(str(sold_path))
    if sold_img is None:
        raise FileNotFoundError(f"template missing: {sold_path}")
    _SOLD_TEMPLATE = _gray(sold_img)
    _SOLD_MASK = _sold_mask_from(sold_img)
    return out


def _has_bgoff_variant(name: str) -> bool:
    if name.endswith("_bgoff.png"):
        return False
    sibling = name[:-len(".png")] + "_bgoff.png"
    return sibling in TEMPLATE_SCREENS


_RESULTS_PRIORITY = ("auction_details.png", "no_auctions.png")
_MATCH_SCALE = 0.5


def _downscale(img: np.ndarray) -> np.ndarray:
    return cv2.resize(img, None, fx=_MATCH_SCALE, fy=_MATCH_SCALE,
                      interpolation=cv2.INTER_AREA)


TEMPLATE_REGIONS = {
    "search.png":                (472, 223, 1448, 471),
    "auction_details.png":       (889,  64, 1920, 294),
    "no_auctions.png":           (700, 410, 1780, 720),
    "auction_options.png":       (546, 276, 1374, 526),
    "player_options.png":        (580, 230, 1340, 486),
    "buy_out.png":               (520, 470, 1400, 620),
    "buy_out_bgoff.png":         (520, 470, 1400, 620),
    "buy_out_progress.png":      (520, 470, 1400, 620),
    "buy_out_progress_bgoff.png":(520, 470, 1400, 620),
    "buyout_successful.png":     (539, 334, 1374, 612),
    "buyout_failed.png":         (546, 378, 1374, 631),
    "claim_car.png":             (538, 359, 1374, 615),
    "ah_landing.png":            (16,   89,  387, 291),
}

_FULL_RES_TEMPLATES = {
    "buy_out.png", "buy_out_bgoff.png",
    "buy_out_progress.png", "buy_out_progress_bgoff.png",
}


def screen_scores(scene_bgr, templates: dict, targets=None) -> dict:
    if targets is not None:
        wanted = set(_RESULTS_PRIORITY)
        wanted |= {n for n, scr in TEMPLATE_SCREENS.items() if scr in targets}
        templates = {n: t for n, t in templates.items() if n in wanted}
    gray = _gray(scene_bgr)
    h, w = gray.shape[:2]
    scores = {}
    for name, tmpl in templates.items():
        region = TEMPLATE_REGIONS.get(name)
        if region:
            x1, y1, x2, y2 = region
            crop = gray[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        else:
            crop = gray
        if name in _FULL_RES_TEMPLATES:
            scores[name] = match_template(crop, tmpl)
        else:
            scores[name] = match_template(_downscale(crop), _small(tmpl))
    return scores


def identify_screen(scene_bgr, templates: dict, threshold: float,
                    targets=None, thresholds=None) -> Screen:
    scores = screen_scores(scene_bgr, templates, targets=targets)

    def _thr(name: str) -> float:
        if thresholds:
            return thresholds.get(TEMPLATE_SCREENS[name], threshold)
        return threshold

    for name in _RESULTS_PRIORITY:
        if scores.get(name, 0.0) >= _thr(name):
            return TEMPLATE_SCREENS[name]
    best_screen, best_margin, found = Screen.UNKNOWN, 0.0, False
    for name, score in scores.items():
        t = _thr(name)
        if score >= t:
            margin = score - t
            if not found or margin > best_margin:
                best_screen, best_margin, found = (
                    TEMPLATE_SCREENS[name], margin, True)
    return best_screen


# ── Confirm button detection ──────────────────────────────────────────────────
CONFIRM_ROW = (548, 714, 1372, 772)
_CONFIRM_V_THRESH = 130
_CONFIRM_V_COUNT = 500


def is_confirm_highlighted(scene_bgr, region=CONFIRM_ROW) -> bool:
    x1, y1, x2, y2 = region
    crop = scene_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    v = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2]
    _, bright = cv2.threshold(v, _CONFIRM_V_THRESH, 255, cv2.THRESH_BINARY)
    return int(cv2.countNonZero(bright)) > _CONFIRM_V_COUNT


# ── SOLD stamp detection (template matching) ──────────────────────────────────
SOLD_TEMPLATE_NAME = "sold.png"
_SOLD_MATCH_DEFAULT = 0.70
_SOLD_TEMPLATE = None
_SOLD_MASK = None

SOLD_STAMP_REGION = (90, 185, 300, 295)

SOLD_STAMP_REGIONS = (
    SOLD_STAMP_REGION,
    (90, 387, 300, 497),
    (90, 589, 300, 699),
    (90, 791, 300, 901),
)


def _sold_mask_from(bgr) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([18, 90, 120], np.uint8),
                    np.array([42, 255, 255], np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    m = cv2.dilate(m, np.ones((5, 5), np.uint8))
    return m


def _sold_score(scene_gray, region) -> float:
    if _SOLD_TEMPLATE is None:
        return 0.0
    x1, y1, x2, y2 = region
    h, w = scene_gray.shape[:2]
    crop = scene_gray[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    th, tw = _SOLD_TEMPLATE.shape[:2]
    if crop.shape[0] < th or crop.shape[1] < tw:
        return 0.0
    res = cv2.matchTemplate(crop, _SOLD_TEMPLATE, cv2.TM_CCOEFF_NORMED,
                            mask=_SOLD_MASK)
    res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
    return float(cv2.minMaxLoc(res)[1])


def is_card_sold(scene_bgr, threshold=_SOLD_MATCH_DEFAULT,
                 region=SOLD_STAMP_REGION) -> bool:
    return _sold_score(_gray(scene_bgr), region) >= threshold


def sold_slots(scene_bgr, threshold=_SOLD_MATCH_DEFAULT) -> tuple:
    gray = _gray(scene_bgr)
    return tuple(_sold_score(gray, r) >= threshold for r in SOLD_STAMP_REGIONS)


CARD_PANEL_REGIONS = (
    (320, 175, 900, 345),
    (320, 377, 900, 547),
    (320, 579, 900, 749),
    (320, 781, 900, 951),
)
_CARD_PRESENT_MIN = 150.0


def _card_present(scene_gray, region) -> bool:
    x1, y1, x2, y2 = region
    h, w = scene_gray.shape[:2]
    crop = scene_gray[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    if crop.size == 0:
        return False
    return float(crop.mean()) >= _CARD_PRESENT_MIN


def first_buyable_slot(scene_bgr, threshold=_SOLD_MATCH_DEFAULT) -> int:
    gray = _gray(scene_bgr)
    for i, (panel, sold_region) in enumerate(
            zip(CARD_PANEL_REGIONS, SOLD_STAMP_REGIONS), start=1):
        if not _card_present(gray, panel):
            break
        if _sold_score(gray, sold_region) < threshold:
            return i
    return 0


# ── Diagnostica soglie (DA DISATTIVARE PER LA RELEASE) ────────────────────────
def _card_panel_means(scene_gray) -> tuple:
    h, w = scene_gray.shape[:2]
    out = []
    for x1, y1, x2, y2 in CARD_PANEL_REGIONS:
        crop = scene_gray[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        out.append(float(crop.mean()) if crop.size else 0.0)
    return tuple(out)


def log_match_diagnostics(scene_bgr, templates: dict, cfg) -> None:
    thresholds = thresholds_from_config(cfg)

    scores = screen_scores(scene_bgr, templates, targets=None)
    by_screen: dict[Screen, float] = {}
    for name, sc in scores.items():
        scr = TEMPLATE_SCREENS[name]
        if sc > by_screen.get(scr, -1.0):
            by_screen[scr] = sc

    parts = []
    for scr, _key in SCREEN_THRESHOLD_KEYS.items():
        sc = by_screen.get(scr, 0.0)
        thr = thresholds.get(scr, DEFAULT_MATCH_THRESHOLD)
        flag = "*" if sc >= thr else " "
        parts.append(f"{scr.name}:{sc:.3f}/{thr:.2f}{flag}")
    _diag.info("match | %s", "  ".join(parts))

    gray = _gray(scene_bgr)
    sold_thr = getattr(cfg, "match_threshold_sold", _SOLD_MATCH_DEFAULT)
    sold = tuple(_sold_score(gray, r) for r in SOLD_STAMP_REGIONS)
    bright = _card_panel_means(gray)
    sold_str = "  ".join(
        f"slot{i}:{s:.3f}{'*' if s >= sold_thr else ' '}"
        for i, s in enumerate(sold, 1))
    bright_str = " ".join(f"{b:.0f}" for b in bright)
    _diag.info("sold (thr %.2f) | %s | card_bright[min %.0f] %s",
               sold_thr, sold_str, _CARD_PRESENT_MIN, bright_str)

from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.json")


@dataclass
class Config:
    match_threshold_search: float = 0.80
    match_threshold_results: float = 0.80
    match_threshold_results_empty: float = 0.80
    match_threshold_auction_options: float = 0.80
    match_threshold_player_options: float = 0.80
    match_threshold_buy_out: float = 0.60
    match_threshold_buyout_progress: float = 0.60
    match_threshold_buyout_success: float = 0.78
    match_threshold_buyout_failed: float = 0.78
    match_threshold_claim_car: float = 0.78
    match_threshold_ah_landing: float = 0.80
    match_threshold_sold: float = 0.70
    key_hold_ms: tuple = (10, 20)
    between_keys_ms: tuple = (10, 20)
    poll_interval_ms: tuple = (15, 30)
    buyout_select_delay_ms: int = 0
    buyout_confirm_window_s: float = 0.35
    buyout_open_wait_s: float = 2.5
    collect_claim_wait_s: float = 1.0
    collect_unknown_wait_s: float = 1.0
    timeout_results_s: float = 12.0
    timeout_outcome_s: float = 25.0
    timeout_claim_s: float = 30.0
    timeout_generic_s: float = 20.0
    loop_pace_s: float = 0.10
    auto_stop_enabled: bool = True
    max_cars: int = 1
    max_minutes: float = 180.0
    collect_after_buyout: bool = True
    notify_sound: bool = True
    notify_toast: bool = True
    match_score_logging: bool = False
    overlay_capturable: bool = False
    ui_scale: float = 1.0
    language: str = "en"
    game_language: str = "en"
    color_primary: str = "#FF0028"
    color_secondary: str = "#f0a83c"
    color_text_dim: str = "#7a3535"
    color_btn_bg: str = "#0e0000"
    color_btn_fg: str = "#FF0028"
    color_btn_hover: str = "#2b0005"
    color_bg: str = "#080000"
    color_card: str = "#0e0000"
    color_nav_active: str = "#170006"
    color_control: str = "#3a2222"
    search_jitter_enabled: bool = True
    search_jitter_steps: int = 1
    maxbid_rows_above_confirm: int = 2
    jitter_maxbid: bool = False
    jitter_maxbuyout: bool = False
    hotkey_start_stop: str = "<f8>"
    hotkey_panic: str = "<f9>"


_TUPLE_FIELDS = {
    name for name, f in Config.__dataclass_fields__.items()
    if isinstance(f.default, tuple)
}

_OBSOLETE_KEYS = {"window_title"}


def load_config(path=DEFAULT_CONFIG_PATH) -> Config:
    path = Path(path)
    if not path.exists():
        cfg = Config()
        save_config(cfg, path)
        return cfg
    data = json.loads(path.read_text(encoding="utf-8"))
    had_obsolete = bool(_OBSOLETE_KEYS & data.keys())
    for key in _OBSOLETE_KEYS:
        data.pop(key, None)
    for key in _TUPLE_FIELDS:
        if key in data and isinstance(data[key], list):
            data[key] = tuple(data[key])
    known = set(Config.__dataclass_fields__)
    cfg = Config(**{k: v for k, v in data.items() if k in known})
    for key, value in data.items():
        if key not in known:
            setattr(cfg, key, value)
    if had_obsolete or not known.issubset(data.keys()):
        save_config(cfg, path)
    return cfg


def save_config(cfg: Config, path=DEFAULT_CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    declared = set(Config.__dataclass_fields__)
    for key, value in cfg.__dict__.items():
        if key not in declared:
            data[key] = value
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

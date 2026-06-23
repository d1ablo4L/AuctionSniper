from __future__ import annotations
import ctypes
import logging
import threading
import time
import numpy as np
import cv2
import win32con
import win32gui

_log = logging.getLogger("fh6.capture")

GAME_WINDOW_TITLE = "Forza Horizon 6"

# ── DPI awareness ────────────────────────────────────────────────────────────
def _set_dpi_awareness():
    try:
        u = ctypes.windll.user32
        u.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        u.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
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


_set_dpi_awareness()

CANON = (1920, 1080)
_TARGET_RATIO = 16.0 / 9.0

_CAPTURE_FPS_CAP = 60

# ── Module state ──────────────────────────────────────────────────────────────
_camera = None
_camera_unavailable = False
_dxgi_got_frame = False         
_mss = None
_hwnd_cache: dict = {}
_capture_failing = False
_latest = None                 
_frame_id = 0
_worker_thread = None
_stop_worker = False


# ── Crop aspect ratio ─────────────────────────────────────────────────────────
def _crop_to_16_9(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    if h == 0:
        return frame
    actual_ratio = w / h
    if abs(actual_ratio - _TARGET_RATIO) < 0.02:
        return frame
    if actual_ratio > _TARGET_RATIO:
        new_w = int(round(h * _TARGET_RATIO))
        x0 = (w - new_w) // 2
        return frame[:, x0:x0 + new_w]
    new_h = int(round(w / _TARGET_RATIO))
    y0 = (h - new_h) // 2
    return frame[y0:y0 + new_h, :]


# ── Window helpers ────────────────────────────────────────────────────────────
def find_window(title: str) -> int:
    cached = _hwnd_cache.get(title)
    if cached and win32gui.IsWindow(cached):
        return cached
    matches = []

    def _collect(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            if win32gui.GetWindowText(hwnd).strip() == title:
                matches.append(hwnd)

    win32gui.EnumWindows(_collect, None)
    hwnd = matches[0] if matches else 0
    if hwnd:
        _hwnd_cache[title] = hwnd
    return hwnd


def client_rect(hwnd: int):
    cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
    width, height = cr - cl, cb - ct
    sx, sy = win32gui.ClientToScreen(hwnd, (cl, ct))
    return sx, sy, width, height


def using_dxgi() -> bool:
    return _camera is not None and not _camera_unavailable


# ── Capture backend ─────────────────────────────────────────────────────────
def _grab_dxgi(region):
    global _camera, _camera_unavailable
    if _camera_unavailable:
        return None
    try:
        import bettercam
        if _camera is None:
            _camera = bettercam.create(output_idx=0, output_color="BGR")
        frame = _camera.grab(region=region) if region else _camera.grab()
        return np.ascontiguousarray(frame) if frame is not None else None
    except Exception:
        _camera_unavailable = True
        return None


def _grab_mss(region):
    global _mss
    import mss
    if _mss is None:
        _mss = mss.mss()
    sct = _mss
    if region:
        area = {"left": region[0], "top": region[1],
                "width": region[2] - region[0],
                "height": region[3] - region[1]}
    else:
        area = sct.monitors[1]
    shot = sct.grab(area)
    return np.ascontiguousarray(np.array(shot)[:, :, :3])


def _region_for(window_title):
    if not window_title:
        return None
    hwnd = find_window(window_title)
    if not hwnd:
        return None
    x, y, w, h = client_rect(hwnd)
    if w > 0 and h > 0:
        return (x, y, x + w, y + h)
    return None


def _produce_frame(window_title) -> bool:
    global _latest, _frame_id, _capture_failing, _dxgi_got_frame
    region = _region_for(window_title)

    raw = _grab_dxgi(region)
    if raw is not None:
        _dxgi_got_frame = True
    elif _dxgi_got_frame and _latest is not None:
        return False

    if raw is None:
        try:
            raw = _grab_mss(region)
        except Exception as e:
            if not _capture_failing:
                _log.warning("capture failed: %s", e)
                _capture_failing = True
            return False

    if _capture_failing:
        _log.info("capture restored")
        _capture_failing = False

    raw = _crop_to_16_9(raw)
    if (raw.shape[1], raw.shape[0]) != CANON:
        raw = cv2.resize(raw, CANON, interpolation=cv2.INTER_AREA)

    _frame_id += 1
    _latest = (raw, _frame_id)
    return True


# ── Background capture worker ─────────────────────────────────────────────────
def _worker_alive() -> bool:
    return _worker_thread is not None and _worker_thread.is_alive()


def _worker_run(window_title):
    _log.info("capture worker started")
    min_dt = 1.0 / _CAPTURE_FPS_CAP if _CAPTURE_FPS_CAP else 0.0
    while not _stop_worker:
        t0 = time.perf_counter()
        try:
            produced = _produce_frame(window_title)
        except Exception:
            _log.exception("error in capture worker")
            time.sleep(0.05)
            continue
        if not produced:
            time.sleep(0.003)
            continue
        if min_dt:
            rest = min_dt - (time.perf_counter() - t0)
            if rest > 0:
                time.sleep(rest)
    _log.info("capture worker stopped")


def start_capture(window_title: str = GAME_WINDOW_TITLE) -> None:
    global _worker_thread, _stop_worker
    if _worker_alive():
        return
    _stop_worker = False
    _worker_thread = threading.Thread(
        target=_worker_run, args=(window_title,),
        name="fh6-capture", daemon=True)
    _worker_thread.start()


def stop_capture() -> None:
    global _stop_worker
    _stop_worker = True


# ── Public read API ───────────────────────────────────────────────────────────
def frame_id() -> int:
    snap = _latest
    return snap[1] if snap is not None else 0


def latest_frame(window_title: str | None = GAME_WINDOW_TITLE):
    if window_title and not _worker_alive():
        start_capture(window_title)

    snap = _latest
    if snap is None and _worker_alive():
        for _ in range(120):       
            time.sleep(0.005)
            snap = _latest
            if snap is not None:
                break
    if snap is None and not _worker_alive():
        _produce_frame(window_title)
        snap = _latest

    if snap is not None:
        return snap
    return (np.zeros((CANON[1], CANON[0], 3), dtype=np.uint8), 0)


def grab_screen(window_title: str | None = GAME_WINDOW_TITLE) -> np.ndarray:
    return latest_frame(window_title)[0]


# ── Focus / foreground ────────────────────────────────────────────────────────
def foreground_title() -> str:
    return win32gui.GetWindowText(win32gui.GetForegroundWindow())


def is_game_focused(expected_title: str = GAME_WINDOW_TITLE,
                    title_getter=foreground_title) -> bool:
    return title_getter().strip() == expected_title


def focus_window(title: str = GAME_WINDOW_TITLE) -> bool:
    hwnd = find_window(title)
    if not hwnd:
        return False
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False

from __future__ import annotations

import time
from dataclasses import dataclass

from PIL import ImageGrab
from pywinauto import Desktop

from .visual import wait_until_visually_ready


@dataclass(frozen=True)
class WindowInfo:
    handle: int
    title: str
    area: int


def _visible_windows() -> dict[int, WindowInfo]:
    found: dict[int, WindowInfo] = {}
    for win in Desktop(backend="uia").windows():
        try:
            if not win.is_visible():
                continue
            rect = win.rectangle()
            area = max(0, rect.width()) * max(0, rect.height())
            if area < 120_000:
                continue
            handle = int(win.handle)
            title = (win.window_text() or "").strip()
            found[handle] = WindowInfo(handle=handle, title=title, area=area)
        except Exception:
            continue
    return found


def snapshot_handles() -> set[int]:
    return set(_visible_windows())


def _grab_handle(handle: int):
    win = Desktop(backend="uia").window(handle=handle)
    rect = win.rectangle()
    bbox = (rect.left, rect.top, rect.right, rect.bottom)
    return ImageGrab.grab(bbox=bbox, all_screens=True)


def wait_for_aladin_cover(
    baseline_handles: set[int], timeout: float, manual_event=None, cancel_event=None, log=None
) -> str:
    deadline = time.perf_counter() + timeout
    first_new: int | None = None
    first_seen_at = 0.0
    seen_new: set[int] = set()

    while time.perf_counter() < deadline:
        if manual_event is not None and manual_event.is_set():
            manual_event.clear()
            return "수동 표지 확인"
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("측정이 취소되었습니다.")

        windows = _visible_windows()
        candidates = [
            info for handle, info in windows.items()
            if handle not in baseline_handles
            and "Microsoft Edge" not in info.title
            and "PLibrary" not in info.title
        ]
        candidates.sort(key=lambda w: w.area, reverse=True)

        for info in candidates:
            if info.handle not in seen_new:
                seen_new.add(info.handle)
                if log:
                    log(f"새 Windows 창 감지: {info.title or '(제목 없음)'}")
                if first_new is None:
                    first_new = info.handle
                    first_seen_at = time.perf_counter()
                elif info.handle != first_new:
                    ok = wait_until_visually_ready(
                        lambda h=info.handle: _grab_handle(h),
                        timeout=min(20.0, max(1.0, deadline - time.perf_counter())),
                        manual_event=manual_event,
                        cancel_event=cancel_event,
                    )
                    if ok:
                        return info.title or "알라딘 최종 뷰어"

        if first_new is not None and time.perf_counter() - first_seen_at >= 3.0:
            try:
                ok = wait_until_visually_ready(
                    lambda h=first_new: _grab_handle(h),
                    timeout=min(1.2, max(0.2, deadline - time.perf_counter())),
                    manual_event=manual_event,
                    cancel_event=cancel_event,
                    min_entropy=4.2,
                )
                if ok:
                    return windows.get(first_new, WindowInfo(first_new, "알라딘 뷰어", 0)).title
            except Exception:
                pass
        time.sleep(0.15)

    raise TimeoutError("알라딘 뷰어에서 책 표지를 제한 시간 안에 감지하지 못했습니다.")

from __future__ import annotations

import io
import time
from typing import Callable

from PIL import Image, ImageChops, ImageStat


def image_entropy(image: Image.Image) -> float:
    return image.convert("L").entropy()


def mean_difference(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a.convert("L"), b.convert("L"))
    return ImageStat.Stat(diff).mean[0]


def png_bytes_to_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def wait_until_visually_ready(
    capture: Callable[[], Image.Image],
    timeout: float,
    manual_event=None,
    cancel_event=None,
    min_entropy: float = 3.6,
    stable_delta: float = 1.8,
    interval: float = 0.18,
) -> bool:
    deadline = time.perf_counter() + timeout
    previous: Image.Image | None = None
    stable_hits = 0
    while time.perf_counter() < deadline:
        if manual_event is not None and manual_event.is_set():
            manual_event.clear()
            return True
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("측정이 취소되었습니다.")
        try:
            current = capture()
        except Exception:
            time.sleep(interval)
            continue
        entropy = image_entropy(current)
        if previous is not None and entropy >= min_entropy:
            delta = mean_difference(previous, current)
            if delta <= stable_delta:
                stable_hits += 1
                if stable_hits >= 2:
                    return True
            else:
                stable_hits = 0
        previous = current
        time.sleep(interval)
    return False

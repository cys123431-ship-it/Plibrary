from datetime import datetime
from pathlib import Path

from PIL import Image

from plibrary.models import MeasurementResult, Provider
from plibrary.storage import ResultStore
from plibrary.visual import image_entropy, mean_difference


def test_provider_labels():
    assert Provider.KYOBO.value == "교보문고"
    assert Provider.NURIMEDIA.value == "북레일(누리미디어)"


def test_result_store_writes_utf8_csv(tmp_path: Path):
    store = ResultStore(tmp_path)
    result = MeasurementResult("교보문고", "테스트 책", 1.2345, datetime(2026, 9, 10, 18, 0, 0))
    path = store.append(result)
    text = path.read_text(encoding="utf-8-sig")
    assert "교보문고" in text
    assert "1.234" in text


def test_visual_metrics():
    white = Image.new("RGB", (100, 100), "white")
    black = Image.new("RGB", (100, 100), "black")
    assert image_entropy(white) == 0.0
    assert mean_difference(white, black) > 200

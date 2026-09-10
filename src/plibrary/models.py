from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class Provider(str, Enum):
    KYOBO = "교보문고"
    BOOKCUBE = "북큐브"
    ALADIN = "알라딘"
    WOORI = "우리전자책"
    OPMS = "웅진(OPMS)"
    NURIMEDIA = "북레일(누리미디어)"


@dataclass(slots=True)
class MeasurementResult:
    provider: str
    book_title: str
    elapsed_seconds: float
    started_at: datetime
    status: str = "성공"
    note: str = ""

from __future__ import annotations

import time
from datetime import datetime

from .browser import BrowserController
from .models import MeasurementResult, Provider
from .windows_viewer import snapshot_handles, wait_for_aladin_cover


class ProviderRunner:
    def __init__(self, browser: BrowserController, log=None, manual_event=None, cancel_event=None) -> None:
        self.browser = browser
        self.log = log or (lambda _msg: None)
        self.manual_event = manual_event
        self.cancel_event = cancel_event

    def run(self, provider: Provider, title: str) -> MeasurementResult:
        if not self.browser.started:
            raise RuntimeError("먼저 'Edge 열기 / 로그인'을 눌러주세요.")
        if provider == Provider.NURIMEDIA and not title.strip():
            title = "내 삶의 길"
        if provider in (Provider.OPMS, Provider.NURIMEDIA):
            return self._loan_then_cover(provider, title)
        if provider == Provider.BOOKCUBE:
            return self._bookcube(title)
        if provider == Provider.ALADIN:
            return self._aladin(title)
        if provider in (Provider.KYOBO, Provider.WOORI):
            return self._simple_read(provider, title)
        raise ValueError(f"지원하지 않는 공급처입니다: {provider}")

    def _simple_read(self, provider: Provider, title: str) -> MeasurementResult:
        page, action = self.browser.action_locator(title, ["책읽기", "책 읽기"])
        before = self.browser.page_snapshot()
        started_at = datetime.now()
        start = time.perf_counter()
        self.browser.click_locator(page, action)
        self.log("측정 시작: 책읽기 클릭")
        self.browser.wait_for_cover(before, manual_event=self.manual_event, cancel_event=self.cancel_event)
        elapsed = time.perf_counter() - start
        self.log(f"표지 감지 완료: {elapsed:.3f}초")
        return MeasurementResult(provider.value, title, elapsed, started_at)

    def _bookcube(self, title: str) -> MeasurementResult:
        page, action = self.browser.action_locator(title, ["책읽기", "책 읽기"])
        before = self.browser.page_snapshot()
        started_at = datetime.now()
        start = time.perf_counter()
        self.browser.click_locator(page, action)
        self.log("측정 시작: 책읽기 클릭")
        self.browser.click_text(["웹 뷰어보기", "웹뷰어보기", "웹 뷰어 보기"], timeout=15.0)
        self.log("북큐브: 웹 뷰어보기 자동 클릭")
        self.browser.wait_for_cover(before, manual_event=self.manual_event, cancel_event=self.cancel_event)
        elapsed = time.perf_counter() - start
        self.log(f"표지 감지 완료: {elapsed:.3f}초")
        return MeasurementResult(Provider.BOOKCUBE.value, title, elapsed, started_at)

    def _aladin(self, title: str) -> MeasurementResult:
        page, action = self.browser.action_locator(title, ["책읽기", "책 읽기"])
        baseline_windows = snapshot_handles()
        started_at = datetime.now()
        start = time.perf_counter()
        self.browser.click_locator(page, action)
        self.log("측정 시작: 책읽기 클릭")
        self.browser.click_text(["뷰어로 보기", "뷰어로보기"], timeout=15.0)
        self.log("알라딘: 뷰어로 보기 자동 클릭, Windows 뷰어 감지 시작")
        title_seen = wait_for_aladin_cover(
            baseline_windows,
            timeout=90.0,
            manual_event=self.manual_event,
            cancel_event=self.cancel_event,
            log=self.log,
        )
        elapsed = time.perf_counter() - start
        self.log(f"알라딘 표지 감지 완료: {elapsed:.3f}초")
        return MeasurementResult(Provider.ALADIN.value, title, elapsed, started_at, note=title_seen)

    def _loan_then_cover(self, provider: Provider, title: str) -> MeasurementResult:
        if title.strip():
            self.log(f"도서 검색/확인: {title}")
            self.browser.search_for(title)
        page, action = self.browser.action_locator(title, ["대출하기", "대출 하기"])
        before = self.browser.page_snapshot()
        started_at = datetime.now()
        start = time.perf_counter()
        self.browser.click_locator(page, action)
        self.log("측정 시작: 대출하기 클릭")
        try:
            self.browser.click_text(["확인"], timeout=6.0)
            self.log("대출 완료 안내창: 확인 자동 클릭")
        except Exception:
            self.log("별도 HTML 확인 버튼 없음(브라우저 알림창은 자동 승인됨)")
        self.browser.wait_for_cover(before, manual_event=self.manual_event, cancel_event=self.cancel_event)
        elapsed = time.perf_counter() - start
        self.log(f"표지 감지 완료: {elapsed:.3f}초")
        return MeasurementResult(provider.value, title, elapsed, started_at)

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterable

from PIL import Image
from playwright.sync_api import Locator, Page, sync_playwright

from .visual import png_bytes_to_image, wait_until_visually_ready


LIBRARY_URL = "https://ebook.pcu.ac.kr/FxLibrary/"


class BrowserController:
    def __init__(self, profile_dir: Path, log=None) -> None:
        self.profile_dir = profile_dir
        self.log = log or (lambda _msg: None)
        self._pw = None
        self.context = None

    @property
    def started(self) -> bool:
        return self.context is not None

    def start(self) -> None:
        if self.started:
            page = self.active_page()
            page.bring_to_front()
            return
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self.context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="msedge",
            headless=False,
            no_viewport=True,
            accept_downloads=True,
            args=["--start-maximized", "--disable-features=msEdgeFirstRunExperience"],
        )
        self.context.on("page", self._hook_page)
        for p in self.context.pages:
            self._hook_page(p)
        page = self.context.pages[0] if self.context.pages else self.context.new_page()
        try:
            page.goto(LIBRARY_URL, wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            pass
        page.bring_to_front()
        self.log("Edge를 열었습니다. 처음 한 번 로그인하면 이 프로그램 전용 프로필에 로그인 상태가 유지됩니다.")

    def _hook_page(self, page: Page) -> None:
        try:
            page.on("dialog", lambda dialog: dialog.accept())
        except Exception:
            pass

    def close(self) -> None:
        try:
            if self.context is not None:
                self.context.close()
        finally:
            self.context = None
            if self._pw is not None:
                self._pw.stop()
            self._pw = None

    def active_page(self) -> Page:
        if not self.context:
            raise RuntimeError("먼저 Edge를 열어주세요.")
        pages = [p for p in self.context.pages if not p.is_closed()]
        if not pages:
            return self.context.new_page()
        return pages[-1]

    def pages(self) -> list[Page]:
        if not self.context:
            return []
        return [p for p in self.context.pages if not p.is_closed()]

    def page_snapshot(self) -> dict[int, str]:
        snap: dict[int, str] = {}
        for p in self.pages():
            try:
                snap[id(p)] = p.url
            except Exception:
                pass
        return snap

    def _frames(self) -> Iterable:
        for page in reversed(self.pages()):
            for frame in reversed(page.frames):
                yield page, frame

    def _candidate_locators(self, frame, text: str):
        pattern = re.compile(rf"^\s*{re.escape(text)}\s*$")
        yield frame.get_by_role("button", name=pattern)
        yield frame.get_by_role("link", name=pattern)
        yield frame.get_by_text(pattern)
        yield frame.locator(f'input[value="{text}"]')

    def find_text_locator(self, variants: list[str], timeout: float = 10.0) -> tuple[Page, Locator]:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            for page, frame in self._frames():
                for text in variants:
                    for locator in self._candidate_locators(frame, text):
                        try:
                            count = min(locator.count(), 6)
                            for i in range(count):
                                item = locator.nth(i)
                                if item.is_visible():
                                    return page, item
                        except Exception:
                            continue
            time.sleep(0.06)
        raise TimeoutError(f"버튼을 찾지 못했습니다: {' / '.join(variants)}")

    def find_action_near_title(self, title: str, actions: list[str], timeout: float = 4.0) -> tuple[Page, Locator] | None:
        if not title.strip():
            return None
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            for page, frame in self._frames():
                try:
                    title_loc = frame.get_by_text(title.strip(), exact=False)
                    if title_loc.count() == 0:
                        continue
                    for i in range(min(title_loc.count(), 4)):
                        t = title_loc.nth(i)
                        if not t.is_visible():
                            continue
                        for ancestor_depth in range(1, 6):
                            ancestor = t.locator(f"xpath=ancestor::*[{ancestor_depth}]")
                            for action in actions:
                                pattern = re.compile(rf"^\s*{re.escape(action)}\s*$")
                                for candidate in (
                                    ancestor.get_by_role("button", name=pattern),
                                    ancestor.get_by_role("link", name=pattern),
                                    ancestor.get_by_text(pattern),
                                ):
                                    try:
                                        if candidate.count() and candidate.first.is_visible():
                                            return page, candidate.first
                                    except Exception:
                                        pass
                except Exception:
                    continue
            time.sleep(0.08)
        return None

    def action_locator(self, title: str, actions: list[str]) -> tuple[Page, Locator]:
        near = self.find_action_near_title(title, actions)
        if near:
            return near
        return self.find_text_locator(actions, timeout=10.0)

    def click_locator(self, page: Page, locator: Locator) -> None:
        self._hook_page(page)
        locator.scroll_into_view_if_needed(timeout=2_000)
        locator.click(timeout=5_000)

    def click_text(self, variants: list[str], timeout: float = 10.0) -> None:
        page, locator = self.find_text_locator(variants, timeout=timeout)
        self.click_locator(page, locator)

    def text_visible(self, text: str) -> bool:
        for _page, frame in self._frames():
            try:
                loc = frame.get_by_text(text, exact=False)
                if loc.count() and any(loc.nth(i).is_visible() for i in range(min(loc.count(), 5))):
                    return True
            except Exception:
                continue
        return False

    def search_for(self, title: str) -> None:
        if not title.strip() or self.text_visible(title):
            return
        page = self.active_page()
        page.bring_to_front()
        possible = [
            'input[placeholder*="검색"]',
            'input[type="search"]',
            'input[name*="search"]',
            'input[id*="search"]',
            'input[name*="keyword"]',
            'input[id*="keyword"]',
            'input[name*="query"]',
            'input[id*="query"]',
        ]
        target = None
        for selector in possible:
            try:
                loc = page.locator(selector)
                for i in range(min(loc.count(), 8)):
                    if loc.nth(i).is_visible():
                        target = loc.nth(i)
                        break
            except Exception:
                pass
            if target:
                break
        if target is None:
            raise RuntimeError("검색 입력창을 자동으로 찾지 못했습니다. 검색 페이지를 열어둔 뒤 다시 측정해주세요.")
        target.fill(title)
        target.press("Enter")
        deadline = time.perf_counter() + 8.0
        while time.perf_counter() < deadline:
            if self.text_visible(title):
                return
            time.sleep(0.1)
        self.log("검색 결과에서 도서명을 확인하지 못했지만 대출하기 버튼 탐색을 계속합니다.")

    @staticmethod
    def _dom_cover_ready(page: Page) -> bool:
        script = """
        () => {
          const visible = (el) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
          };
          for (const img of document.images) {
            const r = img.getBoundingClientRect();
            if (visible(img) && img.complete && img.naturalWidth >= 160 && img.naturalHeight >= 200 && r.width >= 120 && r.height >= 160) {
              return true;
            }
          }
          for (const canvas of document.querySelectorAll('canvas')) {
            const r = canvas.getBoundingClientRect();
            if (visible(canvas) && r.width * r.height >= 90000 && r.width >= 220 && r.height >= 260) {
              return true;
            }
          }
          for (const el of document.querySelectorAll('object, embed')) {
            const r = el.getBoundingClientRect();
            if (visible(el) && r.width * r.height >= 90000) return true;
          }
          return false;
        }
        """
        try:
            for frame in page.frames:
                if frame.evaluate(script):
                    return True
        except Exception:
            pass
        return False

    def wait_for_cover(self, before: dict[int, str], timeout: float = 75.0, manual_event=None, cancel_event=None) -> Page:
        deadline = time.perf_counter() + timeout
        candidate: Page | None = None
        candidate_seen = 0.0

        while time.perf_counter() < deadline:
            if manual_event is not None and manual_event.is_set():
                manual_event.clear()
                return candidate or self.active_page()
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("측정이 취소되었습니다.")

            pages = self.pages()
            new_pages = [p for p in pages if id(p) not in before]
            changed_pages = [p for p in pages if id(p) in before and before[id(p)] != p.url]
            pool = list(reversed(new_pages or changed_pages))
            if pool and candidate is None:
                candidate = pool[0]
                candidate_seen = time.perf_counter()
                try:
                    candidate.bring_to_front()
                except Exception:
                    pass
                self.log(f"뷰어 창 감지: {candidate.url[:100]}")

            if candidate is not None:
                if self._dom_cover_ready(candidate):
                    try:
                        data = candidate.screenshot(timeout=2_500)
                        current = png_bytes_to_image(data)
                        if current.entropy() >= 3.2:
                            return candidate
                    except Exception:
                        if time.perf_counter() - candidate_seen > 0.4:
                            return candidate

                if time.perf_counter() - candidate_seen > 0.5:
                    def capture(p=candidate) -> Image.Image:
                        return png_bytes_to_image(p.screenshot(timeout=2_500))
                    try:
                        if wait_until_visually_ready(
                            capture,
                            timeout=min(0.8, max(0.2, deadline - time.perf_counter())),
                            manual_event=manual_event,
                            cancel_event=cancel_event,
                            min_entropy=4.6,
                        ):
                            return candidate
                    except Exception:
                        pass
            time.sleep(0.08)

        raise TimeoutError("새 뷰어 창에서 책 표지를 제한 시간 안에 감지하지 못했습니다.")

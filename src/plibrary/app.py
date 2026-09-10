from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .browser import BrowserController, LIBRARY_URL
from .models import Provider
from .providers import ProviderRunner
from .storage import ResultStore


APP_NAME = "PLibrary"


class BrowserWorker:
    def __init__(self, profile_dir: Path, on_log, on_result, on_error) -> None:
        self.on_log = on_log
        self.on_result = on_result
        self.on_error = on_error
        self.commands: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.manual_event = threading.Event()
        self.cancel_event = threading.Event()
        self.browser = BrowserController(profile_dir=profile_dir, log=on_log)
        self.thread = threading.Thread(target=self._run, daemon=True, name="PLibraryBrowserWorker")
        self.thread.start()

    def submit(self, command: str, **kwargs) -> None:
        self.commands.put((command, kwargs))

    def mark_cover(self) -> None:
        self.manual_event.set()

    def cancel(self) -> None:
        self.cancel_event.set()

    def _run(self) -> None:
        while True:
            command, kwargs = self.commands.get()
            try:
                if command == "open":
                    self.browser.start()
                    self.on_result(("opened", None))
                elif command == "measure":
                    self.cancel_event.clear()
                    self.manual_event.clear()
                    runner = ProviderRunner(
                        self.browser,
                        log=self.on_log,
                        manual_event=self.manual_event,
                        cancel_event=self.cancel_event,
                    )
                    result = runner.run(kwargs["provider"], kwargs.get("title", ""))
                    self.on_result(("measurement", result))
                elif command == "close":
                    self.browser.close()
                    return
            except Exception as exc:
                self.on_error(exc)


class PLibraryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PLibrary - 배재대 전자책 속도 측정기")
        self.geometry("760x610")
        self.minsize(700, 560)

        local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        app_dir = local_appdata / APP_NAME
        app_dir.mkdir(parents=True, exist_ok=True)
        self.store = ResultStore()
        self.worker = BrowserWorker(
            profile_dir=app_dir / "edge-profile",
            on_log=lambda msg: self.after(0, self._log, msg),
            on_result=lambda data: self.after(0, self._on_worker_result, data),
            on_error=lambda exc: self.after(0, self._on_worker_error, exc),
        )
        self.busy = False
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        pad = {"padx": 14, "pady": 8}
        header = ttk.Frame(self)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="PLibrary", font=("맑은 고딕", 20, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="Edge에서 전자책 동작 시작 버튼을 자동 클릭하고, 책 표지가 뜨는 순간까지 시간을 측정합니다.",
        ).pack(anchor="w", pady=(4, 0))

        form = ttk.LabelFrame(self, text="측정 설정")
        form.pack(fill="x", **pad)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="공급처").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.provider_var = tk.StringVar(value=Provider.KYOBO.value)
        self.provider_combo = ttk.Combobox(
            form,
            textvariable=self.provider_var,
            values=[p.value for p in Provider],
            state="readonly",
        )
        self.provider_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        self.provider_combo.bind("<<ComboboxSelected>>", self._provider_changed)

        ttk.Label(form, text="도서명").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        self.title_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.title_var).grid(row=1, column=1, sticky="ew", padx=10, pady=8)
        self.title_hint = ttk.Label(form, text="모바일에서 미리 대여한 공급처는 선택 사항입니다.")
        self.title_hint.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 8))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", **pad)
        self.open_btn = ttk.Button(buttons, text="1. Edge 열기 / 로그인", command=self._open_edge)
        self.open_btn.pack(side="left", padx=(0, 8))
        self.measure_btn = ttk.Button(buttons, text="2. 측정 시작", command=self._measure)
        self.measure_btn.pack(side="left", padx=(0, 8))
        self.manual_btn = ttk.Button(buttons, text="표지 감지 수동 종료", command=self._manual_cover)
        self.manual_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = ttk.Button(buttons, text="측정 취소", command=self.worker.cancel)
        self.cancel_btn.pack(side="left")

        status_frame = ttk.LabelFrame(self, text="현재 상태")
        status_frame.pack(fill="x", **pad)
        self.status_var = tk.StringVar(value="Edge를 열고 로그인한 뒤 공급처를 선택하세요.")
        ttk.Label(status_frame, textvariable=self.status_var, font=("맑은 고딕", 11, "bold")).pack(anchor="w", padx=10, pady=8)
        self.last_result_var = tk.StringVar(value="최근 측정: -")
        ttk.Label(status_frame, textvariable=self.last_result_var).pack(anchor="w", padx=10, pady=(0, 8))

        log_frame = ttk.LabelFrame(self, text="로그")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=15, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(footer, text="측정 CSV 폴더 열기", command=self._open_results).pack(side="left")
        ttk.Label(footer, text=f"전자책 사이트: {LIBRARY_URL}").pack(side="right")

    def _provider_changed(self, _event=None) -> None:
        provider = Provider(self.provider_var.get())
        if provider == Provider.NURIMEDIA:
            self.title_var.set("내 삶의 길")
            self.title_hint.config(text="북레일(누리미디어): 기본 측정 도서 '내 삶의 길'을 검색한 뒤 대출하기부터 측정합니다.")
        elif provider == Provider.OPMS:
            self.title_hint.config(text="웅진(OPMS): PC에 모바일 대여가 반영되지 않으므로 검색할 도서명을 입력하세요.")
        elif provider == Provider.ALADIN:
            self.title_hint.config(text="알라딘: 책읽기 → 뷰어로 보기 → Windows 뷰어/다운로드 → 최종 표지까지 측정합니다.")
        else:
            self.title_hint.config(text="모바일에서 미리 대여한 책을 화면에 띄워두면 도서명은 선택 사항입니다.")

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.open_btn.config(state=state)
        self.measure_btn.config(state=state)
        if status:
            self.status_var.set(status)

    def _open_edge(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "Edge를 여는 중...")
        self.worker.submit("open")

    def _measure(self) -> None:
        if self.busy:
            return
        provider = Provider(self.provider_var.get())
        title = self.title_var.get().strip()
        self._set_busy(True, f"{provider.value} 측정 중... 표지가 뜨면 자동 종료합니다.")
        self._log(f"--- {provider.value} 측정 요청 ---")
        self.worker.submit("measure", provider=provider, title=title)

    def _manual_cover(self) -> None:
        if self.busy:
            self.worker.mark_cover()
            self._log("사용자가 표지 표시를 수동 확인했습니다.")
        else:
            messagebox.showinfo("PLibrary", "측정 중에 자동 감지가 실패할 때 사용하는 버튼입니다.")

    def _on_worker_result(self, data) -> None:
        kind, payload = data
        self._set_busy(False)
        if kind == "opened":
            self.status_var.set("Edge 준비 완료. 로그인 후 측정할 책 화면을 준비하세요.")
            return
        if kind == "measurement":
            path = self.store.append(payload)
            title = payload.book_title or "(현재 화면의 도서)"
            self.last_result_var.set(f"최근 측정: {payload.provider} / {title} / {payload.elapsed_seconds:.3f}초")
            self.status_var.set("측정 완료 및 CSV 저장 완료")
            self._log(f"CSV 저장: {path}")

    def _on_worker_error(self, exc: Exception) -> None:
        self._set_busy(False, "측정 실패 - 로그를 확인하세요.")
        self._log(f"오류: {exc}")
        messagebox.showerror("PLibrary 오류", str(exc))

    def _log(self, message: str) -> None:
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _open_results(self) -> None:
        path = self.store.base_dir
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            subprocess.Popen(["explorer", str(path)])

    def _on_close(self) -> None:
        try:
            self.worker.cancel()
            self.worker.submit("close")
        finally:
            self.destroy()


def main() -> None:
    app = PLibraryApp()
    app.mainloop()


if __name__ == "__main__":
    main()

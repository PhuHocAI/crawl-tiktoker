import asyncio
import csv
import ctypes
import re
import sys
import threading
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from crawl import (
    OUTPUT_CSV,
    MAX_IDLE_SCROLL_ROUNDS,
    SCROLL_PAUSE_MS,
    crawl_tiktok_users,
)


class TikTokCrawlerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._set_window_icon()
        self.root.title("Tool Crawl BAY TÓC")
        self.root.geometry("980x620")

        self.query_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value=OUTPUT_CSV)
        self.idle_rounds_var = tk.StringVar(value=str(MAX_IDLE_SCROLL_ROUNDS))
        self.scroll_pause_var = tk.StringVar(value=str(SCROLL_PAUSE_MS))
        self.headless_var = tk.BooleanVar(value=False)
        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.stop_event = threading.Event()
        self.crawl_thread = None
        self.output_auto_mode = True
        documents_dir = Path.home() / "Documents"
        self.output_dir = documents_dir if documents_dir.exists() else Path.home()
        self.output_dir_var = tk.StringVar(value=f"Thư mục lưu: {self.output_dir}")

        self._build_ui()
        self._refresh_output_filename()

    def _set_window_icon(self):
        try:
            if sys.platform.startswith("win"):
                try:
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolcrawltiktok.app")
                except Exception:
                    pass

            if getattr(sys, "frozen", False):
                base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            else:
                base_dir = Path(__file__).resolve().parent

            icon_candidates = [base_dir / "icon.ico"]
            if getattr(sys, "frozen", False):
                icon_candidates.append(Path(sys.executable))

            icon_path = next((p for p in icon_candidates if p.exists()), None)
            if not icon_path:
                return

            self.root.iconbitmap(default=str(icon_path))

            if sys.platform.startswith("win"):
                try:
                    self.root.update_idletasks()
                    hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                    image_icon = 1
                    lr_loadfromfile = 0x00000010
                    icon_big = 1
                    icon_small = 0
                    wm_seticon = 0x0080
                    hicon = ctypes.windll.user32.LoadImageW(
                        0, str(icon_path), image_icon, 0, 0, lr_loadfromfile
                    )
                    if hicon:
                        ctypes.windll.user32.SendMessageW(hwnd, wm_seticon, icon_small, hicon)
                        ctypes.windll.user32.SendMessageW(hwnd, wm_seticon, icon_big, hicon)
                except Exception:
                    pass
        except Exception:
            pass

    def _build_ui(self):
        form = ttk.Frame(self.root, padding=12)
        form.pack(fill="x")

        ttk.Label(form, text="Từ khóa:").grid(row=0, column=0, sticky="w", pady=4)
        self.query_entry = ttk.Entry(form, textvariable=self.query_var, width=50)
        self.query_entry.grid(row=0, column=1, sticky="we", pady=4)
        self.query_entry.bind("<KeyRelease>", self._on_query_changed)

        ttk.Label(form, text="File CSV:").grid(row=1, column=0, sticky="w", pady=4)
        self.output_entry = ttk.Entry(form, textvariable=self.output_var, width=50)
        self.output_entry.grid(row=1, column=1, sticky="we", pady=4)
        self.output_entry.bind("<KeyRelease>", self._on_output_edited)
        ttk.Button(form, text="Chọn thư mục", command=self.choose_output_directory).grid(
            row=1, column=2, sticky="w", padx=(16, 0), pady=4
        )
        ttk.Label(form, textvariable=self.output_dir_var).grid(row=1, column=3, sticky="w", pady=4)

        ttk.Label(form, text="Idle rounds:").grid(row=0, column=2, sticky="w", padx=(16, 0), pady=4)
        ttk.Entry(form, textvariable=self.idle_rounds_var, width=10).grid(row=0, column=3, sticky="w", pady=4)

        ttk.Label(form, text="Scroll pause (ms):").grid(row=0, column=4, sticky="w", padx=(16, 0), pady=4)
        ttk.Entry(form, textvariable=self.scroll_pause_var, width=10).grid(row=0, column=5, sticky="w", pady=4)

        ttk.Checkbutton(form, text="Headless", variable=self.headless_var).grid(
            row=2, column=0, sticky="w", pady=4
        )
        ttk.Checkbutton(form, text="Tự động lướt", variable=self.auto_scroll_var).grid(
            row=2, column=1, sticky="w", pady=4, padx=(12, 0)
        )

        self.run_button = ttk.Button(form, text="Chạy crawl", command=self.run_crawl)
        self.run_button.grid(row=2, column=4, sticky="w", pady=8)

        self.stop_button = ttk.Button(form, text="Dừng crawl", command=self.stop_crawl, state="disabled")
        self.stop_button.grid(row=2, column=5, sticky="w", pady=8)

        ttk.Label(form, textvariable=self.status_var).grid(row=3, column=0, columnspan=6, sticky="w", pady=(4, 0))

        form.columnconfigure(1, weight=1)

        table_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        table_frame.pack(fill="both", expand=True)

        columns = ("Tên", "Username", "NumOfFollower", "NumOfLike")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)

        self.tree.column("Tên", width=280, anchor="w")
        self.tree.column("Username", width=220, anchor="w")
        self.tree.column("NumOfFollower", width=150, anchor="e")
        self.tree.column("NumOfLike", width=150, anchor="e")

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def _slugify_filename(self, text: str) -> str:
        text = text.strip().replace("đ", "d").replace("Đ", "D")
        normalized = unicodedata.normalize("NFD", text.lower())
        no_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        compact = re.sub(r"[^a-z0-9]+", "", no_accents)
        if not compact:
            compact = "demo"
        return f"{compact}.csv"

    def _refresh_output_filename(self):
        self.output_var.set(self._slugify_filename(self.query_var.get()))

    def _on_query_changed(self, _event=None):
        if self.output_auto_mode:
            self._refresh_output_filename()

    def _on_output_edited(self, _event=None):
        current_output = self.output_var.get().strip()
        auto_output = self._slugify_filename(self.query_var.get())
        self.output_auto_mode = current_output == auto_output

    def choose_output_directory(self):
        selected = filedialog.askdirectory(initialdir=str(self.output_dir), title="Chọn thư mục lưu CSV")
        if selected:
            self.output_dir = Path(selected)
            self.output_dir_var.set(f"Thư mục lưu: {self.output_dir}")

    def run_crawl(self):
        query = self.query_var.get().strip()
        output_name = self.output_var.get().strip()

        if not query:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập từ khóa.")
            return

        if not output_name:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập tên file CSV.")
            return

        output_path = Path(output_name)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".csv")

        if not output_path.is_absolute():
            output_path = self.output_dir / output_path.name

        output_csv = str(output_path)

        try:
            idle_rounds = int(self.idle_rounds_var.get().strip())
            scroll_pause_ms = int(self.scroll_pause_var.get().strip())
            if idle_rounds <= 0 or scroll_pause_ms < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Sai định dạng", "Idle rounds phải > 0 và Scroll pause phải >= 0.")
            return

        self.stop_event.clear()
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set(
            f"Đang crawl... (auto-scroll: {'bật' if self.auto_scroll_var.get() else 'tắt'})"
        )

        self.crawl_thread = threading.Thread(
            target=self._worker,
            args=(
                query,
                output_csv,
                idle_rounds,
                scroll_pause_ms,
                self.headless_var.get(),
                self.auto_scroll_var.get(),
            ),
            daemon=True,
        )
        self.crawl_thread.start()

    def stop_crawl(self):
        if self.crawl_thread and self.crawl_thread.is_alive():
            self.stop_event.set()
            self.status_var.set("Đang gửi yêu cầu dừng...")
            self.stop_button.configure(state="disabled")

    def _worker(
        self,
        query: str,
        output_csv: str,
        idle_rounds: int,
        scroll_pause_ms: int,
        headless: bool,
        auto_scroll_enabled: bool,
    ):
        try:
            count = asyncio.run(
                crawl_tiktok_users(
                    search_query=query,
                    output_csv=output_csv,
                    max_idle_scroll_rounds=idle_rounds,
                    scroll_pause_ms=scroll_pause_ms,
                    headless=headless,
                    auto_scroll_enabled=auto_scroll_enabled,
                    stop_event=self.stop_event,
                    progress_callback=lambda msg: self.root.after(0, self.status_var.set, msg),
                )
            )
            self.root.after(0, self._on_success, output_csv, count)
        except Exception as error:
            self.root.after(0, self._on_error, str(error))

    def _on_success(self, output_csv: str, count: int):
        if self.stop_event.is_set():
            self.status_var.set(f"Đã dừng: lưu tạm {count} user")
        else:
            self.status_var.set(f"Hoàn tất: {count} user")
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self._load_csv_preview(output_csv)

    def _on_error(self, error: str):
        self.status_var.set("Thất bại")
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        messagebox.showerror("Lỗi", error)

    def _load_csv_preview(self, output_csv: str):
        for item in self.tree.get_children():
            self.tree.delete(item)

        csv_path = Path(output_csv)
        if not csv_path.exists():
            messagebox.showwarning("Không thấy file", f"Không tìm thấy file: {output_csv}")
            return

        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                self.tree.insert(
                    "",
                    tk.END,
                    values=(
                        row.get("Tên", ""),
                        row.get("Username", ""),
                        row.get("NumOfFollower", ""),
                        row.get("NumOfLike", ""),
                    ),
                )


def main():
    root = tk.Tk()
    app = TikTokCrawlerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

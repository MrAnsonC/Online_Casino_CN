import json
import importlib
import os
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from Casino_Games import casino_games


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "saving_data.json")

WINDOW_BG = "#071713"
PANEL_BG = "#102923"
CARD_BG = "#17362e"
CARD_HOVER = "#245246"
GOLD = "#e7be63"
TEXT = "#f5f1e8"
MUTED = "#afc3ba"
DANGER = "#b94d4d"

# 与原 charge.py 一致。正式使用时建议改为哈希密码或独立管理员资料。
ADMINS = {
    "admin": "admin123",
}


def load_user_data() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def safe_balance(value) -> float:
    try:
        if value in (None, "None", ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class EntryRow(tk.Frame):
    def __init__(self, master, label: str, show: str = ""):
        super().__init__(master, bg=master.cget("bg"))
        tk.Label(
            self,
            text=label,
            width=11,
            anchor="e",
            font=("Microsoft YaHei UI", 11),
            bg=self.cget("bg"),
            fg=TEXT,
        ).pack(side="left", padx=(0, 12))

        self.entry = tk.Entry(
            self,
            show=show,
            font=("Microsoft YaHei UI", 12),
            bg="#eef3f0",
            fg="#17201c",
            insertbackground="#17201c",
            relief="flat",
            bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=9)



class MainMenuPage(tk.Frame):
    """主目录：直接按 SmallGamesPage 的导航页结构制作。"""

    BG = "#081a16"
    PANEL = "#102923"
    PANEL_2 = "#17362e"
    GOLD = "#e7be63"
    TEXT = "#f5f1e8"
    MUTED = "#afc3ba"

    def __init__(
        self,
        master: tk.Misc,
        username: str,
        balance: float,
        sections,
    ):
        super().__init__(master, bg=self.BG)
        self.username = username
        self.balance = float(balance)
        self.sections = sections

        self.current_category = "全部功能"
        self.balance_var = tk.StringVar()
        self.status_var = tk.StringVar(value="请选择功能")
        self.category_buttons = {}
        self.menu_cards = []
        self.menu_images = {}

        self._build_ui()
        self.show_category(self.current_category)

    def _build_ui(self) -> None:
        # ----- 顶部栏：结构、尺寸和 small_games.py 相同 -----
        top = tk.Frame(self, bg=self.PANEL, height=82)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(
            top,
            text="游戏中心主目录",
            font=("Microsoft YaHei UI", 23, "bold"),
            bg=self.PANEL,
            fg=self.GOLD,
        ).pack(side="left", padx=22)

        info = tk.Frame(top, bg=self.PANEL)
        info.pack(side="right", padx=25)
        tk.Label(
            info,
            text=f"玩家：{self.username}",
            font=("Microsoft YaHei UI", 11),
            bg=self.PANEL,
            fg=self.MUTED,
        ).pack(anchor="e")
        tk.Label(
            info,
            textvariable=self.balance_var,
            font=("Microsoft YaHei UI", 15, "bold"),
            bg=self.PANEL,
            fg=self.TEXT,
        ).pack(anchor="e")
        self._refresh_balance_label()

        # ----- 中间主体：small_games.py 的 sidebar + content -----
        body = tk.Frame(self, bg=self.BG)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=self.PANEL, width=205)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="功能分类",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg=self.PANEL,
            fg=self.GOLD,
        ).pack(anchor="w", padx=22, pady=(25, 15))

        for category in self.sections:
            category_button = tk.Button(
                sidebar,
                text=category,
                command=lambda name=category: self.show_category(name),
                anchor="w",
                font=("Microsoft YaHei UI", 12),
                bg=self.PANEL,
                fg=self.TEXT,
                activebackground=self.PANEL_2,
                activeforeground=self.GOLD,
                relief="flat",
                padx=22,
                pady=13,
                cursor="hand2",
            )
            category_button.pack(fill="x", padx=8, pady=2)
            self.category_buttons[category] = category_button

        content = tk.Frame(body, bg=self.BG)
        content.pack(side="left", fill="both", expand=True, padx=25, pady=20)

        self.category_title = tk.Label(
            content,
            text="",
            font=("Microsoft YaHei UI", 21, "bold"),
            bg=self.BG,
            fg=self.TEXT,
        )
        self.category_title.pack(anchor="w", pady=(0, 14))

        # ----- Canvas 卡片区：直接沿用 small_games.py -----
        self.menu_container = tk.Frame(content, bg=self.BG)
        self.menu_container.pack(fill="both", expand=True)

        self.menu_scrollbar = tk.Scrollbar(
            self.menu_container,
            orient="vertical",
        )

        self.menu_canvas = tk.Canvas(
            self.menu_container,
            bg=self.BG,
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self.menu_canvas.pack(side="left", fill="both", expand=True)

        self.menu_scrollbar.config(command=self.menu_canvas.yview)
        self.menu_canvas.config(yscrollcommand=self.menu_scrollbar.set)

        self.menu_frame = tk.Frame(self.menu_canvas, bg=self.BG)
        self.menu_canvas_window = self.menu_canvas.create_window(
            (0, 0),
            window=self.menu_frame,
            anchor="nw",
        )

        self.scrollbar_visible = False
        self.menu_frame.bind("<Configure>", self._on_menu_frame_configure)
        self.menu_canvas.bind("<Configure>", self._on_menu_canvas_configure)

        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel_linux, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel_linux, add="+")

        # ----- 底部状态栏：small_games.py 原布局 -----
        bottom = tk.Frame(self, bg=self.PANEL, height=45)
        bottom.pack(fill="x")
        bottom.pack_propagate(False)

        tk.Label(
            bottom,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 10),
            bg=self.PANEL,
            fg=self.MUTED,
        ).pack(side="left", padx=20)

    def _refresh_balance_label(self) -> None:
        self.balance_var.set(f"余额：${self.balance:,.2f}")

    def set_balance(self, balance: float) -> None:
        self.balance = float(balance)
        self._refresh_balance_label()

    def _get_menu_image_path(self, image_filename: str) -> Optional[str]:
        """优先按 small_games 规则读取 Picture；再兼容图片实际放置位置。"""
        preferred = os.path.join(BASE_DIR, "Picture", image_filename)
        if os.path.isfile(preferred):
            return preferred

        # 有些项目把导航图放在模块 Picture 或项目根目录；只匹配指定文件名，
        # 绝不使用其他 PNG 作为替代图。
        candidates = [
            os.path.join(BASE_DIR, image_filename),
            os.path.join(BASE_DIR, "Casino_Games", "Picture", image_filename),
            os.path.join(BASE_DIR, "Lotto", "Picture", image_filename),
            os.path.join(BASE_DIR, "Small_Games", "Picture", image_filename),
            os.path.join(BASE_DIR, "Slot_Machine", "Picture", image_filename),
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate

        target = image_filename.casefold()
        try:
            for root, _dirs, files in os.walk(BASE_DIR):
                for filename in files:
                    if filename.casefold() == target:
                        return os.path.join(root, filename)
        except OSError:
            pass
        return None

    def _load_menu_image(
        self,
        image_filename: str,
        max_width: int = 250,
        max_height: int = 150,
    ) -> Optional[tk.PhotoImage]:
        """复制 small_games.py 的 PNG 加载和缩放方式。"""
        image_path = self._get_menu_image_path(image_filename)
        if image_path is None:
            return None

        cache_key = f"{image_path}|{max_width}x{max_height}"
        if cache_key in self.menu_images:
            return self.menu_images[cache_key]

        try:
            if Image is not None and ImageTk is not None:
                image = Image.open(image_path).convert("RGBA")
                image.thumbnail((max_width, max_height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
            else:
                photo = tk.PhotoImage(file=image_path)
                width = max(photo.width(), 1)
                height = max(photo.height(), 1)
                scale = max(
                    (width + max_width - 1) // max_width,
                    (height + max_height - 1) // max_height,
                    1,
                )
                if scale > 1:
                    photo = photo.subsample(scale, scale)

            self.menu_images[cache_key] = photo
            return photo
        except (OSError, tk.TclError, ValueError):
            return None

    @staticmethod
    def _bind_to_all_children(
        widget: tk.Misc,
        sequence: str,
        callback: Callable,
    ) -> None:
        widget.bind(sequence, callback)
        for child in widget.winfo_children():
            MainMenuPage._bind_to_all_children(child, sequence, callback)

    def _set_card_background(self, card: tk.Frame, colour: str) -> None:
        try:
            card.config(bg=colour)
        except tk.TclError:
            return

        for child in card.winfo_children():
            try:
                child.config(bg=colour)
            except tk.TclError:
                pass

    def show_category(self, category: str) -> None:
        self.current_category = category
        self.category_title.config(text=category)

        for name, button in self.category_buttons.items():
            selected = name == category
            button.config(
                bg=self.PANEL_2 if selected else self.PANEL,
                fg=self.GOLD if selected else self.TEXT,
            )

        self.menu_canvas.yview_moveto(0)

        for widget in self.menu_frame.winfo_children():
            widget.destroy()

        for column in range(self.menu_frame.grid_size()[0]):
            self.menu_frame.grid_columnconfigure(column, weight=0, minsize=0)
        for row in range(self.menu_frame.grid_size()[1]):
            self.menu_frame.grid_rowconfigure(row, weight=0, minsize=0)

        self.menu_cards.clear()

        items = self.sections.get(category, self.sections.get("全部功能", []))

        column_count = 3
        for column in range(column_count):
            self.menu_frame.grid_columnconfigure(
                column,
                weight=1,
                uniform="games",
                minsize=185,
            )

        row_count = (len(items) + column_count - 1) // column_count
        for row in range(row_count):
            self.menu_frame.grid_rowconfigure(
                row,
                weight=0,
                minsize=240,
            )

        for index, (display_name, image_filename, command) in enumerate(items):
            row, column = divmod(index, column_count)
            normal_bg = self.PANEL_2
            hover_bg = "#245246"
            cursor = "arrow"

            card = tk.Frame(
                self.menu_frame,
                bg=normal_bg,
                bd=0,
                highlightthickness=1,
                highlightbackground="#2e5a4d",
                highlightcolor=self.GOLD,
                cursor=cursor,
            )
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=8,
                pady=8,
            )
            # small_games 原代码使用 grid_propagate；这里同时关闭 pack
            # propagation，避免竖图把卡片宽度重新压窄。
            card.grid_propagate(False)
            card.pack_propagate(False)

            image = self._load_menu_image(image_filename)

            image_area = tk.Frame(
                card,
                bg=normal_bg,
                height=180,
                cursor=cursor,
            )
            image_area.pack(fill="x", expand=True, padx=8, pady=(7, 0))
            image_area.pack_propagate(False)

            if image is not None:
                image_label = tk.Label(
                    image_area,
                    image=image,
                    bg=normal_bg,
                    bd=0,
                    cursor=cursor,
                )
                image_label.pack(expand=True)
            else:
                image_label = tk.Label(
                    image_area,
                    text="PNG",
                    font=("Microsoft YaHei UI", 15, "bold"),
                    bg=normal_bg,
                    fg="#6f9487",
                    bd=0,
                    cursor=cursor,
                )
                image_label.pack(expand=True)

            name_label = tk.Label(
                card,
                text=display_name,
                font=("Microsoft YaHei UI", 11, "bold"),
                bg=normal_bg,
                fg=self.TEXT,
                bd=0,
                cursor=cursor,
                wraplength=190,
            )
            name_label.pack(fill="x", padx=8, pady=(0, 8))

            self.menu_cards.append(card)

            def on_click(event, action=command, title=display_name):
                self.status_var.set(f"正在打开：{title}")
                action()

            def on_enter(event, current_card=card, colour=hover_bg):
                self._set_card_background(current_card, colour)
                current_card.config(highlightbackground=self.GOLD)

            def on_leave(event, current_card=card, colour=normal_bg):
                self._set_card_background(current_card, colour)
                current_card.config(highlightbackground="#2e5a4d")

            self._bind_to_all_children(card, "<Button-1>", on_click)
            self._bind_to_all_children(card, "<Enter>", on_enter)
            self._bind_to_all_children(card, "<Leave>", on_leave)

        self.after_idle(self._update_scrollbar_visibility)

    def _on_menu_frame_configure(self, event=None) -> None:
        bbox = self.menu_canvas.bbox("all")
        if bbox is None:
            self.menu_canvas.configure(scrollregion=(0, 0, 0, 0))
        else:
            self.menu_canvas.configure(scrollregion=bbox)
        self.after_idle(self._update_scrollbar_visibility)

    def _on_menu_canvas_configure(self, event) -> None:
        self.menu_canvas.itemconfigure(
            self.menu_canvas_window,
            width=max(event.width, 1),
        )
        self.after_idle(self._update_scrollbar_visibility)

    def _update_scrollbar_visibility(self) -> None:
        if not self.menu_canvas.winfo_exists():
            return

        self.menu_canvas.update_idletasks()
        content_height = self.menu_frame.winfo_reqheight()
        canvas_height = self.menu_canvas.winfo_height()
        needs_scrollbar = canvas_height > 1 and content_height > canvas_height

        if needs_scrollbar and not self.scrollbar_visible:
            self.menu_scrollbar.pack(side="right", fill="y")
            self.scrollbar_visible = True
        elif not needs_scrollbar and self.scrollbar_visible:
            self.menu_scrollbar.pack_forget()
            self.scrollbar_visible = False
            self.menu_canvas.yview_moveto(0)

        bbox = self.menu_canvas.bbox("all")
        if bbox is None:
            self.menu_canvas.configure(scrollregion=(0, 0, 0, 0))
        else:
            self.menu_canvas.configure(
                scrollregion=(0, 0, bbox[2], content_height)
            )

    def _event_is_inside_menu_area(self, event) -> bool:
        try:
            if not self.winfo_exists():
                return False
            widget = getattr(event, "widget", None)
            while widget is not None:
                if (
                    widget is self.menu_canvas
                    or widget is self.menu_frame
                    or widget is self.menu_container
                ):
                    return True
                widget = getattr(widget, "master", None)
            return False
        except (tk.TclError, AttributeError):
            return False

    def _on_mousewheel(self, event) -> Optional[str]:
        try:
            if not self.winfo_exists() or not self.scrollbar_visible:
                return None
            if not self._event_is_inside_menu_area(event):
                return None
            delta = int(-event.delta / 120)
            if delta == 0:
                delta = -1 if event.delta > 0 else 1
            self.menu_canvas.yview_scroll(delta * 4, "units")
            return "break"
        except tk.TclError:
            return None

    def _on_mousewheel_linux(self, event) -> Optional[str]:
        try:
            if not self.winfo_exists() or not self.scrollbar_visible:
                return None
            if not self._event_is_inside_menu_area(event):
                return None
            direction = -1 if event.num == 4 else 1
            self.menu_canvas.yview_scroll(direction * 4, "units")
            return "break"
        except tk.TclError:
            return None

class GameCenterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"游戏中心")
        self.geometry("1150x750+50+10")
        self.resizable(False, False)
        self.configure(bg=WINDOW_BG)
        self.protocol("WM_DELETE_WINDOW", self.close_application)

        self.users = []
        self.current_user: Optional[dict] = None
        self.username = ""
        self.balance = 0.0
        self.failed_attempts = {}

        self.current_page: Optional[tk.Widget] = None
        self.casino_page = None
        self.game_hub_page = None
        self.main_menu_images = {}

        self.show_welcome_page()

    def replace_page(self, page: tk.Widget) -> None:
        if self.current_page is not None and self.current_page.winfo_exists():
            self.current_page.destroy()
        self.current_page = page
        self.current_page.pack(fill="both", expand=True)

        # 游戏目录按右上角 X 时返回上一级，不销毁唯一的 Tk 根窗口。
        page_close = getattr(page, "on_close", None)
        if callable(page_close):
            self.protocol("WM_DELETE_WINDOW", page_close)
        else:
            self.protocol("WM_DELETE_WINDOW", self.close_application)

    def make_header(self, parent: tk.Widget, title: str, subtitle: str = "") -> tk.Frame:
        header = tk.Frame(parent, bg=PANEL_BG, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        text_area = tk.Frame(header, bg=PANEL_BG)
        text_area.pack(side="left", padx=34, pady=15)

        tk.Label(
            text_area,
            text=title,
            font=("Microsoft YaHei UI", 24, "bold"),
            bg=PANEL_BG,
            fg=GOLD,
        ).pack(anchor="w")

        if subtitle:
            tk.Label(
                text_area,
                text=subtitle,
                font=("Microsoft YaHei UI", 10),
                bg=PANEL_BG,
                fg=MUTED,
            ).pack(anchor="w", pady=(3, 0))

        return header

    def styled_button(
        self,
        master,
        text,
        command,
        width=18,
        bg=CARD_BG,
        fg=TEXT,
        font_size=12,
    ):
        button = tk.Button(
            master,
            text=text,
            command=command,
            width=width,
            font=("Microsoft YaHei UI", font_size, "bold"),
            bg=bg,
            fg=fg,
            activebackground=GOLD,
            activeforeground="#182018",
            relief="flat",
            bd=0,
            cursor="hand2",
            pady=13,
        )
        normal_bg = bg
        button.bind("<Enter>", lambda event: button.config(bg=CARD_HOVER))
        button.bind("<Leave>", lambda event: button.config(bg=normal_bg))
        return button

    # ---------------- 欢迎 / 登录 / 注册 ----------------

    def show_welcome_page(self):
        page = tk.Frame(self, bg=WINDOW_BG)
        self.make_header(page, "欢迎来到游戏中心", "登录后可进入赌场、刮刮乐及街机小游戏")

        center = tk.Frame(page, bg=WINDOW_BG)
        center.pack(expand=True)

        tk.Label(
            center,
            text="GAME CENTER",
            font=("Segoe UI", 34, "bold"),
            bg=WINDOW_BG,
            fg=TEXT,
        ).pack(pady=(0, 8))

        tk.Label(
            center,
            text="请选择登录或注册",
            font=("Microsoft YaHei UI", 13),
            bg=WINDOW_BG,
            fg=MUTED,
        ).pack(pady=(0, 28))

        buttons = tk.Frame(center, bg=WINDOW_BG)
        buttons.pack()
        self.styled_button(buttons, "登录", self.show_login_page).grid(
            row=0, column=0, padx=12
        )
        self.styled_button(buttons, "注册新账号", self.show_register_page).grid(
            row=0, column=1, padx=12
        )

        self.styled_button(
            center,
            "退出程序",
            self.close_application,
            bg="#50302f",
            width=38,
            font_size=11,
        ).pack(pady=(22, 0))

        self.replace_page(page)

    def show_login_page(self):
        page = tk.Frame(self, bg=WINDOW_BG)
        self.make_header(page, "用户登录", "每个账号最多允许三次连续失败")

        panel = tk.Frame(page, bg=PANEL_BG, padx=45, pady=38)
        panel.place(relx=0.5, rely=0.52, anchor="center", width=520, height=365)

        username_row = EntryRow(panel, "用户名")
        username_row.pack(fill="x", pady=9)
        password_row = EntryRow(panel, "密码", show="*")
        password_row.pack(fill="x", pady=9)

        status_var = tk.StringVar()
        tk.Label(
            panel,
            textvariable=status_var,
            font=("Microsoft YaHei UI", 10),
            bg=PANEL_BG,
            fg="#e08b83",
        ).pack(pady=(8, 4))

        buttons = tk.Frame(panel, bg=PANEL_BG)
        buttons.pack(pady=12)

        def submit(event=None):
            username = username_row.entry.get().strip()
            password = password_row.entry.get()
            if not username or not password:
                status_var.set("请输入用户名和密码。")
                return

            self.users = load_user_data()
            matched = next(
                (u for u in self.users if u.get("user_name") == username),
                None,
            )

            if matched and str(matched.get("lock", "False")) == "True":
                status_var.set(f"账号 {username} 已被锁定，请联系管理员。")
                return

            if matched and matched.get("password") == password:
                self.failed_attempts.pop(username, None)
                self.current_user = matched
                self.username = username
                self.balance = safe_balance(matched.get("cash"))
                self.show_main_menu()
                return

            attempts = self.failed_attempts.get(username, 0) + 1
            self.failed_attempts[username] = attempts
            remaining = max(0, 3 - attempts)

            if attempts >= 3:
                if matched:
                    matched["lock"] = "True"
                    save_user_data(self.users)
                status_var.set("登录失败三次，该账号已被锁定。")
            else:
                status_var.set(f"用户名或密码错误，还可尝试 {remaining} 次。")
            password_row.entry.delete(0, "end")

        self.styled_button(buttons, "登录", submit, width=13).grid(
            row=0, column=0, padx=8
        )
        self.styled_button(
            buttons,
            "返回",
            self.show_welcome_page,
            width=13,
            bg="#3d4a45",
        ).grid(row=0, column=1, padx=8)

        username_row.entry.bind("<Return>", lambda e: password_row.entry.focus_set())
        password_row.entry.bind("<Return>", submit)
        username_row.entry.focus_set()

        self.replace_page(page)

    def show_register_page(self):
        page = tk.Frame(self, bg=WINDOW_BG)
        self.make_header(page, "注册新账号", "用户名不可重复，密码需要输入两次确认")

        panel = tk.Frame(page, bg=PANEL_BG, padx=45, pady=32)
        panel.place(relx=0.5, rely=0.53, anchor="center", width=540, height=410)

        username_row = EntryRow(panel, "用户名")
        username_row.pack(fill="x", pady=7)
        password1_row = EntryRow(panel, "密码", show="*")
        password1_row.pack(fill="x", pady=7)
        password2_row = EntryRow(panel, "确认密码", show="*")
        password2_row.pack(fill="x", pady=7)

        status_var = tk.StringVar()
        tk.Label(
            panel,
            textvariable=status_var,
            font=("Microsoft YaHei UI", 10),
            bg=PANEL_BG,
            fg="#e08b83",
        ).pack(pady=(7, 2))

        def submit(event=None):
            username = username_row.entry.get().strip()
            password1 = password1_row.entry.get()
            password2 = password2_row.entry.get()

            if len(username) < 3:
                status_var.set("用户名至少需要 3 个字符。")
                return
            if not password1:
                status_var.set("密码不能为空。")
                return
            if password1 != password2:
                status_var.set("两次输入的密码不一致。")
                return

            users = load_user_data()
            if any(u.get("user_name") == username for u in users):
                status_var.set("用户名已存在，请选择其他用户名。")
                return

            users.append(
                {
                    "user_name": username,
                    "password": password1,
                    "cash": "0.00",
                    "lock": "False",
                }
            )
            save_user_data(users)
            messagebox.showinfo("注册成功", f"用户 {username} 注册成功。", parent=self)
            self.show_login_page()

        buttons = tk.Frame(panel, bg=PANEL_BG)
        buttons.pack(pady=13)
        self.styled_button(buttons, "注册", submit, width=13).grid(
            row=0, column=0, padx=8
        )
        self.styled_button(
            buttons,
            "返回",
            self.show_welcome_page,
            width=13,
            bg="#3d4a45",
        ).grid(row=0, column=1, padx=8)

        password2_row.entry.bind("<Return>", submit)
        username_row.entry.focus_set()
        self.replace_page(page)

    # ---------------- 主目录 ----------------

    def show_main_menu(self):
        self.reload_current_user()

        # 主目录继续沿用 SmallGamesPage 的页面结构和卡片规则，
        # 左侧增加“游戏”和“账号”分类；“全部功能”显示两类的合集。
        game_items = [
            ("赌场游戏", "Casino_Games.png", self.open_casino),
            ("街机小游戏", "Small_Games.png", self.open_small_games),
            ("刮刮乐", "Lotto.png", self.open_lotto),
            ("老虎机", "Slot_Machine.png", self.open_slot_machines),
        ]
        account_items = [
            ("账号服务", "Account.png", self.show_account_page),
            ("登出", "Logout.png", self.logout),
        ]
        sections = {
            "全部功能": game_items + account_items,
            "游戏": game_items,
            "账号": account_items,
        }

        page = MainMenuPage(
            master=self,
            username=self.username,
            balance=self.balance,
            sections=sections,
        )
        self.replace_page(page)

    def open_casino(self):
        page = casino_games.main(
            parent=self,
            balance=self.balance,
            user=self.username,
            on_back=self.return_from_casino,
            on_balance_change=self.set_balance,
        )
        self.casino_page = page
        self.replace_page(page)

    def return_from_casino(self, balance: float):
        self.set_balance(balance)
        self.casino_page = None
        self.show_main_menu()

    def open_lotto(self):
        self.open_game_hub("Lotto.lotto", "刮刮乐")

    def open_small_games(self):
        self.open_game_hub("Small_Games.small_games", "街机小游戏")

    def open_slot_machines(self):
        self.open_game_hub("Slot_Machine.slot_machine", "老虎机")

    def open_game_hub(self, module_name: str, title: str):
        """延迟加载 GUI 游戏目录，避免可选子游戏影响 index.py 启动。"""
        try:
            module = importlib.import_module(module_name)
            hub_main = getattr(module, "main", None)
            if not callable(hub_main):
                raise AttributeError(f"{module_name} 没有可调用的 main()")

            page = hub_main(
                parent=self,
                balance=self.balance,
                user=self.username,
                on_back=self.return_from_game_hub,
                on_balance_change=self.set_balance,
            )
            if not isinstance(page, tk.Widget):
                raise TypeError(f"{module_name}.main() 必须返回 Tkinter Widget/Frame")

            self.game_hub_page = page
            self.replace_page(page)
        except Exception as exc:
            messagebox.showerror(
                "启动失败",
                f"无法打开{title}：\n\n{type(exc).__name__}: {exc}",
                parent=self,
            )

    def return_from_game_hub(self, balance: float):
        self.set_balance(balance)
        self.game_hub_page = None
        self.show_main_menu()

    # ---------------- 账号服务 ----------------

    def show_account_page(self):
        self.reload_current_user()

        page = tk.Frame(self, bg=WINDOW_BG)
        self.make_header(page, "账号服务", f"账号：{self.username}")

        top = tk.Frame(page, bg=WINDOW_BG)
        top.pack(fill="x", padx=32, pady=(22, 5))

        self.styled_button(
            top,
            "← 返回主目录",
            self.show_main_menu,
            width=15,
            bg="#3d4a45",
            font_size=10,
        ).pack(side="left")

        tk.Label(
            top,
            text=f"余额：${self.balance:,.2f}",
            font=("Microsoft YaHei UI", 17, "bold"),
            bg=WINDOW_BG,
            fg=TEXT,
        ).pack(side="right")

        grid = tk.Frame(page, bg=WINDOW_BG)
        grid.pack(expand=True)

        services = [
            ("查询余额", self.show_balance),
            ("充值", lambda: self.show_money_dialog("charge")),
            ("更改密码", self.show_password_dialog),
            ("提款", lambda: self.show_money_dialog("withdraw")),
        ]

        for index, (title, command) in enumerate(services):
            row, column = divmod(index, 2)
            self.styled_button(
                grid,
                title,
                command,
                width=24,
                font_size=14,
            ).grid(row=row, column=column, padx=18, pady=18, ipady=12)

        self.replace_page(page)

    def show_balance(self):
        self.reload_current_user()
        messagebox.showinfo(
            "查询余额",
            f"你最新的余额为：${self.balance:,.2f}",
            parent=self,
        )
        self.show_account_page()

    def admin_verified(self, parent) -> bool:
        dialog = tk.Toplevel(self)
        dialog.title("管理员验证")
        dialog.geometry("430x285")
        dialog.resizable(False, False)
        dialog.transient(parent)
        dialog.grab_set()
        dialog.configure(bg=PANEL_BG)

        result = {"ok": False}
        attempts = {"count": 0}

        tk.Label(
            dialog,
            text="管理员验证",
            font=("Microsoft YaHei UI", 18, "bold"),
            bg=PANEL_BG,
            fg=GOLD,
        ).pack(pady=(22, 12))

        form = tk.Frame(dialog, bg=PANEL_BG)
        form.pack(fill="x", padx=42)

        admin_row = EntryRow(form, "管理员")
        admin_row.pack(fill="x", pady=6)
        password_row = EntryRow(form, "密码", show="*")
        password_row.pack(fill="x", pady=6)

        status_var = tk.StringVar()
        tk.Label(
            dialog,
            textvariable=status_var,
            font=("Microsoft YaHei UI", 9),
            bg=PANEL_BG,
            fg="#e08b83",
        ).pack(pady=4)

        def verify(event=None):
            name = admin_row.entry.get().strip()
            password = password_row.entry.get()
            if ADMINS.get(name) == password:
                result["ok"] = True
                dialog.destroy()
                return

            attempts["count"] += 1
            if attempts["count"] >= 3:
                messagebox.showerror("验证失败", "管理员验证失败三次。", parent=dialog)
                dialog.destroy()
            else:
                status_var.set(f"管理员账号或密码错误，还可尝试 {3-attempts['count']} 次。")
                password_row.entry.delete(0, "end")

        self.styled_button(dialog, "确认", verify, width=12, font_size=10).pack(
            pady=7
        )
        password_row.entry.bind("<Return>", verify)
        admin_row.entry.focus_set()
        self.wait_window(dialog)
        return result["ok"]

    def show_money_dialog(self, operation: str):
        title = "充值" if operation == "charge" else "提款"
        if not self.admin_verified(self):
            return

        amount_text = self.simple_input_dialog(
            title,
            f"当前余额：${self.balance:,.2f}\n请输入{title}金额：",
            password=False,
        )
        if amount_text is None:
            return

        try:
            amount = round(float(amount_text), 2)
        except ValueError:
            messagebox.showerror("金额错误", "请输入有效数字。", parent=self)
            return

        if amount <= 0:
            messagebox.showerror("金额错误", "金额必须大于 0。", parent=self)
            return

        if operation == "withdraw" and amount > self.balance:
            messagebox.showerror("余额不足", "提款金额不能超过当前余额。", parent=self)
            return

        if operation == "charge":
            self.balance += amount
        else:
            self.balance -= amount

        self.persist_current_user()
        messagebox.showinfo(
            f"{title}成功",
            f"{title}金额：${amount:,.2f}\n当前余额：${self.balance:,.2f}",
            parent=self,
        )
        self.show_account_page()

    def show_password_dialog(self):
        old_password = self.simple_input_dialog(
            "更改密码",
            "请输入当前密码：",
            password=True,
        )
        if old_password is None:
            return

        self.reload_current_user()
        if not self.current_user or self.current_user.get("password") != old_password:
            messagebox.showerror("密码错误", "当前密码不正确。", parent=self)
            return

        new_password = self.simple_input_dialog(
            "更改密码",
            "请输入新密码：",
            password=True,
        )
        if new_password is None:
            return
        if not new_password:
            messagebox.showerror("密码错误", "新密码不能为空。", parent=self)
            return

        confirm = self.simple_input_dialog(
            "更改密码",
            "请再次输入新密码：",
            password=True,
        )
        if confirm != new_password:
            messagebox.showerror("密码错误", "两次输入的新密码不一致。", parent=self)
            return

        self.current_user["password"] = new_password
        self.persist_current_user()
        messagebox.showinfo("修改成功", "密码已成功更改。", parent=self)

    def simple_input_dialog(self, title: str, prompt: str, password=False):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("430x245")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=PANEL_BG)

        result = {"value": None}

        tk.Label(
            dialog,
            text=prompt,
            font=("Microsoft YaHei UI", 11),
            bg=PANEL_BG,
            fg=TEXT,
            justify="center",
        ).pack(pady=(30, 14))

        entry = tk.Entry(
            dialog,
            show="*" if password else "",
            font=("Microsoft YaHei UI", 13),
            bg="#eef3f0",
            fg="#17201c",
            relief="flat",
            justify="center",
        )
        entry.pack(fill="x", padx=65, ipady=8)

        buttons = tk.Frame(dialog, bg=PANEL_BG)
        buttons.pack(pady=20)

        def accept(event=None):
            result["value"] = entry.get()
            dialog.destroy()

        self.styled_button(buttons, "确认", accept, width=10, font_size=10).grid(
            row=0, column=0, padx=6
        )
        self.styled_button(
            buttons,
            "取消",
            dialog.destroy,
            width=10,
            bg="#3d4a45",
            font_size=10,
        ).grid(row=0, column=1, padx=6)

        entry.bind("<Return>", accept)
        entry.focus_set()
        self.wait_window(dialog)
        return result["value"]

    # ---------------- 数据同步 / 退出 ----------------

    def reload_current_user(self):
        if not self.username:
            return
        self.users = load_user_data()
        self.current_user = next(
            (u for u in self.users if u.get("user_name") == self.username),
            self.current_user,
        )
        if self.current_user:
            self.balance = safe_balance(self.current_user.get("cash", self.balance))

    def persist_current_user(self):
        if not self.username:
            return
        users = load_user_data()
        matched = next(
            (u for u in users if u.get("user_name") == self.username),
            None,
        )
        if matched is None:
            return

        matched["cash"] = f"{self.balance:.2f}"
        if self.current_user:
            matched["password"] = self.current_user.get(
                "password",
                matched.get("password", ""),
            )
            matched["lock"] = self.current_user.get(
                "lock",
                matched.get("lock", "False"),
            )

        save_user_data(users)
        self.users = users
        self.current_user = matched

    def set_balance(self, balance: float):
        self.balance = safe_balance(balance)
        self.persist_current_user()

    def logout(self):
        self.persist_current_user()
        self.current_user = None
        self.username = ""
        self.balance = 0.0
        self.casino_page = None
        self.game_hub_page = None
        self.show_welcome_page()

    def close_application(self):
        if self.casino_page is not None and getattr(self.casino_page, "process", None):
            messagebox.showwarning(
                "游戏运行中",
                "请先关闭独立运行中的赌场游戏。",
                parent=self,
            )
            return
        if self.game_hub_page is not None and getattr(
            self.game_hub_page, "process", None
        ):
            messagebox.showwarning(
                "游戏运行中",
                "请先关闭当前运行中的游戏。",
                parent=self,
            )
            return

        self.persist_current_user()
        self.destroy()


def main():
    app = GameCenterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
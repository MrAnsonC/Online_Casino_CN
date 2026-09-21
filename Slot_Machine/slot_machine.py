import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("Cannot locate encrypted account storage")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
from A_Tools.Account import install_secure_json as _install_secure_json
_install_secure_json()
del _install_secure_json, _account_root, _AccountPath, _account_sys

import importlib
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk
except ImportError:
    Image = None
    ImageTk = None
from typing import Callable, Optional


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(THIS_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, "A_Tools/Account/saving_data.json")

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


def greeting_for(username: str) -> str:
    hour = datetime.now().hour
    period = "凌晨好" if hour < 6 else "早上好" if hour < 12 else "中午好" if hour < 18 else "晚上好"
    return f"{period}，{username}！"


def _ui_colour(master: tk.Misc, colour: str) -> str:
    resolver = getattr(master.winfo_toplevel(), "theme_colour", None)
    return resolver(colour) if callable(resolver) else colour


# 所有老虎机游戏统一使用单 Tk 窗口嵌入模式。
# EMBEDDED_GAME_MODULES 会在 GAME_SECTIONS 定义后自动生成，避免新增游戏时
# 忘记同步嵌入名单。
GAME_SECTIONS = {
    "老虎机": [
        ("数字老虎机", "Slot_Machine.Number_Slot_Machine", False),
        ("旋转扑克", "Slot_Machine.Poker_Slot_Machine", False),
        ("21 BELL老虎机", "Slot_Machine.21_Bell_Slot_Machine", False),
        ("21点老虎机", "Slot_Machine.Blackjack_Slot_Machine", False),
        ("现金老虎机", "Slot_Machine.Cash_Machine®", False),
        ("双倍钻石老虎机", "Slot_Machine.Double_Diamond_Machine®", False),
        ("最高奖金老虎机", "Slot_Machine.Top_Dollar_Machine®", False),
    ],
}


# 当前两个老虎机游戏都使用单 Tk 窗口嵌入模式。
# 保留旧式子进程兼容代码，但当前没有模块需要走该路径。
LEGACY_PROCESS_MODULES = set()

EMBEDDED_GAME_MODULES = {
    module_name
    for games in GAME_SECTIONS.values()
    for _display_name, module_name, maintenance in games
    if module_name and not maintenance and module_name not in LEGACY_PROCESS_MODULES
}


def load_users() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_users(users: list) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def update_balance(username: str, balance: float) -> None:
    users = load_users()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(balance):.2f}"
            save_users(users)
            return


def is_favorite(username: str, module_name: str) -> bool:
    if username == "TEMP_ACCOUNT":
        return False
    for user in load_users():
        if user.get("user_name") == username:
            return any(item.get("module") == module_name
                       for item in user.get("favorites", []) if isinstance(item, dict))
    return False


def toggle_favorite(username: str, display_name: str, module_name: str) -> tuple[bool, str]:
    if username == "TEMP_ACCOUNT":
        return False, "体验账号不会储存收藏。"
    users = load_users()
    for user in users:
        if user.get("user_name") != username:
            continue
        favorites = [
            {"module": str(item.get("module", "")).strip()}
            for item in user.get("favorites", []) if isinstance(item, dict)
            and str(item.get("module", "")).strip()
        ]
        existing = next((item for item in favorites if item.get("module") == module_name), None)
        if existing:
            favorites.remove(existing)
            active, message = False, f"已从我的最爱移除：{display_name}"
        elif len(favorites) >= 8:
            return False, "我的最爱最多只能储存 8 个游戏。"
        else:
            favorites.append({"module": module_name})
            active, message = True, f"已加入我的最爱：{display_name}"
        user["favorites"] = favorites
        save_users(users)
        return active, message
    return False, "找不到玩家资料，无法储存收藏。"


def read_balance(username: str, fallback: float = 0.0) -> float:
    for user in load_users():
        if user.get("user_name") == username:
            try:
                return float(user.get("cash", fallback))
            except (TypeError, ValueError):
                return fallback
    return fallback


def child_run(module_name: str, result_file: str, balance_text: str, username: str) -> int:
    """在全新的 Python 进程内运行一个旧式游戏模块。"""
    result = {
        "ok": False,
        "balance": 0.0,
        "error": "",
    }

    try:
        balance = float(balance_text)
        result["balance"] = balance

        module = importlib.import_module(module_name)
        game_main = getattr(module, "main", None)
        if not callable(game_main):
            raise AttributeError(f"{module_name} 没有可调用的 main(balance, user)")

        returned_balance = game_main(balance, username)
        if returned_balance is None:
            # 某些游戏直接写 A_Tools/Account/saving_data.json，不返回余额。
            returned_balance = read_balance(username, balance)

        result["balance"] = float(returned_balance)
        result["ok"] = True
        update_balance(username, result["balance"])

    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    try:
        with open(result_file, "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
    except OSError:
        pass

    return 0 if result["ok"] else 1


ROOT_BG = "#F7F3EA"
PANEL_BG = "#E6D9F2"
CARD_BG = "#DDF2E5"
CARD_HOVER = "#F6D0D8"
GOLD = "#111111"
TEXT = "#111111"
MUTED = "#111111"


def add_paper_art_ribbon(parent: tk.Misc, background: str) -> tk.Canvas:
    """绘制紫罗兰、薄荷绿与蜜桃粉的层叠纸艺装饰带。"""
    ribbon = tk.Canvas(parent, height=38, bg=background, highlightthickness=0, bd=0)
    ribbon.pack(fill="x")

    def redraw(event) -> None:
        width = max(event.width, 1)
        ribbon.delete("paper-art")
        ribbon.create_polygon(0, 0, width, 0, width, 16, width*.78, 12,
                              width*.58, 21, width*.34, 14, 0, 23,
                              fill="#CDB7EB", outline="", tags="paper-art")
        ribbon.create_polygon(0, 15, width*.25, 9, width*.49, 25,
                              width*.73, 13, width, 22, width, 38, 0, 38,
                              fill="#CDEEDD", outline="", tags="paper-art")
        ribbon.create_polygon(0, 29, width*.20, 19, width*.42, 31,
                              width*.66, 21, width*.84, 30, width, 24,
                              width, 38, 0, 38,
                              fill="#F7BEC9", outline="", tags="paper-art")
        ribbon.create_line(0, 28, width, 23, fill="#FFFFFF", width=1,
                           dash=(3, 5), tags="paper-art")
        ribbon.create_line(0, 36, width, 31, fill="#9DB7D0", width=2,
                           tags="paper-art")
        suits = (("♠", "#684C9C"), ("♥", "#C76078"),
                 ("♣", "#4E8A72"), ("♦", "#C76078"))
        for index, (suit, colour) in enumerate(suits):
            ribbon.create_text(width*(.16 + index*.22), 21 + (index % 2)*5,
                               text=suit, fill=colour,
                               font=("Segoe UI Symbol", 15, "bold"),
                               tags="paper-art")
    ribbon.bind("<Configure>", redraw)
    return ribbon


class EmbeddedGameHost(tk.Frame):
    """兼容旧式 ``root`` API 的 Frame。

    旧游戏通常会调用 ``title/geometry/resizable/protocol``。在嵌入模式下，
    这些操作不能再创建或调整新的 Tk 根窗口，因此在这里做兼容处理。
    """

    def __init__(self, master: "EmbeddedGamePage"):
        super().__init__(master, bg=ROOT_BG, highlightthickness=0, bd=0)
        self.page = master

    def title(self, text: Optional[str] = None):
        if text is not None:
            self.page.set_title(str(text))
        return self.page.title_var.get()

    def geometry(self, geometry_spec: Optional[str] = None):
        # 记录旧游戏期望的内容尺寸；超出主窗口时由宿主提供滚动条。
        if geometry_spec:
            match = re.match(r"(\d+)x(\d+)", str(geometry_spec))
            if match:
                self.page.set_requested_size(int(match.group(1)), int(match.group(2)))
        return f"{self.page.requested_width}x{self.page.requested_height}"

    def resizable(self, _width=None, _height=None):
        return (False, False)

    def protocol(self, name: str, callback=None):
        if name == "WM_DELETE_WINDOW" and callback is not None:
            self.page.set_close_handler(callback)
        return None

    def finish(self, balance: Optional[float] = None) -> None:
        self.page.finish(balance)


class EmbeddedGamePage(tk.Frame):
    """单窗口游戏页面壳，不额外显示“当前游戏”顶部标题长条。"""

    def __init__(
        self,
        master: tk.Misc,
        *,
        title: str,
        username: str,
        balance: float,
        on_back: Optional[Callable[[float], None]] = None,
        on_balance_change: Optional[Callable[[float], None]] = None,
    ):
        super().__init__(master, bg=ROOT_BG, highlightthickness=0, bd=0)
        self.username = username
        self.balance = float(balance)
        self.on_back_callback = on_back
        self.on_balance_change = on_balance_change
        self.close_handler: Optional[Callable[[], None]] = None
        self.game = None
        self._closed = False
        self._sync_job = None
        self.requested_width = 1150
        self.requested_height = 750

        # 保留 title_var 供旧游戏调用 root.title()；不额外绘制标题长条。
        # 这样嵌入式老虎机游戏与 casino_games.py 打开的赌场游戏一致，
        # 游戏内容会从窗口最上方开始并占满整个可用区域。
        self.title_var = tk.StringVar(value=title)
        self.balance_var = tk.StringVar()
        self._build_content_host()
        self._refresh_balance()

    def _build_content_host(self) -> None:
        container = tk.Frame(self, bg=ROOT_BG)
        container.pack(fill="both", expand=True)

        self.v_scroll = tk.Scrollbar(container, orient="vertical")
        self.h_scroll = tk.Scrollbar(container, orient="horizontal")
        self.canvas = tk.Canvas(
            container,
            bg=ROOT_BG,
            highlightthickness=0,
            bd=0,
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set,
        )
        self.v_scroll.configure(command=self.canvas.yview)
        self.h_scroll.configure(command=self.canvas.xview)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.host = EmbeddedGameHost(self)
        self.host_window = self.canvas.create_window(
            (0, 0), window=self.host, anchor="nw"
        )
        self.canvas.bind("<Configure>", self._layout_host)
        self.host.bind("<Configure>", self._update_scroll_region)

    def set_requested_size(self, width: int, height: int) -> None:
        self.requested_width = max(1, int(width))
        self.requested_height = max(1, int(height))
        self.after_idle(self._layout_host)

    def _layout_host(self, _event=None) -> None:
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        host_width = max(canvas_width, self.requested_width)
        host_height = max(canvas_height, self.requested_height)
        self.canvas.itemconfigure(
            self.host_window, width=host_width, height=host_height
        )
        self._update_scroll_region()

        need_v = self.requested_height > canvas_height
        need_h = self.requested_width > canvas_width
        if need_v and not self.v_scroll.winfo_ismapped():
            self.v_scroll.pack(side="right", fill="y")
        elif not need_v and self.v_scroll.winfo_ismapped():
            self.v_scroll.pack_forget()
            self.canvas.yview_moveto(0)
        if need_h and not self.h_scroll.winfo_ismapped():
            self.h_scroll.pack(side="bottom", fill="x", before=self.canvas)
        elif not need_h and self.h_scroll.winfo_ismapped():
            self.h_scroll.pack_forget()
            self.canvas.xview_moveto(0)

    def _update_scroll_region(self, _event=None) -> None:
        if hasattr(self, "canvas") and self.canvas.winfo_exists():
            bbox = self.canvas.bbox("all")
            self.canvas.configure(scrollregion=bbox or (0, 0, 0, 0))

    def set_title(self, title: str) -> None:
        self.title_var.set(title)

    def set_close_handler(self, callback: Callable[[], None]) -> None:
        self.close_handler = callback

    def attach_game(self, game) -> None:
        self.game = game
        self._schedule_balance_sync()

    def _schedule_balance_sync(self) -> None:
        if self._closed:
            return
        game_balance = getattr(self.game, "balance", self.balance)
        try:
            self.balance = float(game_balance)
        except (TypeError, ValueError):
            pass
        self._refresh_balance()
        self._sync_job = self.after(250, self._schedule_balance_sync)

    def _refresh_balance(self) -> None:
        self.balance_var.set(f"余额：${self.balance:,.2f}")

    def on_close(self) -> None:
        if self._closed:
            return
        if callable(self.close_handler):
            self.close_handler()
        else:
            self.finish()

    def finish(self, balance: Optional[float] = None) -> None:
        if self._closed:
            return
        self._closed = True

        if self._sync_job is not None:
            try:
                self.after_cancel(self._sync_job)
            except tk.TclError:
                pass
            self._sync_job = None

        if balance is None:
            balance = getattr(self.game, "balance", self.balance)
        try:
            self.balance = float(balance)
        except (TypeError, ValueError):
            pass

        if callable(self.on_balance_change):
            self.on_balance_change(self.balance)
        if callable(self.on_back_callback):
            self.on_back_callback(self.balance)
        else:
            # 嵌入接口缺少返回回调时，至少安全销毁当前页。
            try:
                tk.Frame.destroy(self)
            except tk.TclError:
                pass

    # index.py 的 replace_page() 会寻找页面的 on_close。
    on_back = on_close


class SlotMachinesPage(tk.Frame):
    """嵌入 index.py 唯一根窗口的老虎机选择页面。"""

    BG = "#F7F3EA"
    PANEL = "#E6D9F2"
    PANEL_2 = "#DDF2E5"
    GOLD = "#111111"
    TEXT = "#111111"
    MUTED = "#111111"
    RED = "#B84F6A"

    def __init__(
        self,
        master: tk.Misc,
        username: str,
        balance: float,
        on_back: Callable[[float], None],
        on_balance_change: Optional[Callable[[float], None]] = None,
        on_preferences: Optional[Callable[[], None]] = None,
        translator: Optional[Callable[[str], str]] = None,
    ):
        for name in ("BG", "PANEL", "PANEL_2", "GOLD", "TEXT", "MUTED", "RED"):
            setattr(self, name, _ui_colour(master, getattr(type(self), name)))
        self.SURFACE = _ui_colour(master, "#FFFFFF")
        self.HOVER = _ui_colour(master, "#F6D0D8")
        self.MAINTENANCE = _ui_colour(master, "#E7E1EC")
        self.CARD_BORDER = _ui_colour(master, "#B69ADD")
        self.MAINTENANCE_BORDER = _ui_colour(master, "#CEC5D5")
        super().__init__(master, bg=self.BG)
        self._uploaded_scope = True
        self.username = username
        self.balance = float(balance)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.on_preferences = on_preferences
        self.translator = translator

        self.current_category = "老虎机"
        self.process: Optional[subprocess.Popen] = None
        self.result_file: Optional[str] = None
        self.running_game_name = ""

        self.balance_var = tk.StringVar()
        self.status_var = tk.StringVar(value=self._tr("请选择老虎机"))
        self.category_buttons = {}
        self.game_cards = []
        self.game_images = {}
        self._closing = False
        self._scrollbar_job = None
        self._wheel_bindings = []
        self.bind("<Destroy>", self._on_page_destroy, add="+")

        self._build_ui()
        self.show_category(self.current_category)
        self._preferences_ready = True

    def _tr(self, text: str) -> str:
        if callable(self.translator):
            return self.translator(text)
        translator = getattr(self.winfo_toplevel(), "translate_ui", None)
        return translator(text) if callable(translator) else text

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg=self.PANEL, height=82)
        top.pack(fill="x")
        top.pack_propagate(False)

        title_text = self._tr("老虎机中心")
        title_size = 19 if len(title_text) > 16 else 23
        tk.Label(
            top,
            text=title_text,
            font=("Microsoft YaHei UI", title_size, "bold"),
            wraplength=250,
            justify="left",
            bg=self.PANEL,
            fg=self.GOLD,
        ).pack(side="left", padx=(22, 10))

        tk.Button(
            top,
            text=self._tr("← 返回主目录"),
            command=self.back_to_main,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.PANEL_2,
            fg=self.TEXT,
            activebackground=self.HOVER,
            activeforeground=self.TEXT,
            relief="flat",
            padx=12,
            pady=9,
            cursor="hand2",
            wraplength=155,
            justify="center",
        ).pack(side="left", padx=(0, 22), pady=18)

        tk.Label(top, text=self._tr(greeting_for(self.username)),
                 font=("Microsoft YaHei UI", 11, "bold"),
                 wraplength=220, justify="center",
                 bg=self.PANEL, fg=self.TEXT).place(
                     relx=0.62, rely=0.5, anchor="center"
                 )

        info = tk.Frame(top, bg=self.SURFACE, padx=18, pady=9,
                        highlightbackground="#CBBBDD", highlightthickness=1)
        info.pack(side="right", padx=25, pady=14)
        tk.Label(info, textvariable=self.balance_var,
                 font=("Microsoft YaHei UI", 14, "bold"),
                 bg=self.SURFACE, fg=self.TEXT).pack()
        self._refresh_balance_label()
        add_paper_art_ribbon(self, self.BG)

        body = tk.Frame(self, bg=self.BG)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=self.PANEL, width=230)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text=self._tr("游戏分类"),
            font=("Microsoft YaHei UI", 14, "bold"),
            bg=self.PANEL,
            fg=self.GOLD,
        ).pack(anchor="w", padx=22, pady=(25, 15))

        for category in GAME_SECTIONS:
            button = tk.Button(
                sidebar,
                text=self._tr(category),
                command=lambda name=category: self.show_category(name),
                anchor="w",
                justify="left",
                wraplength=180,
                font=("Microsoft YaHei UI", 12),
                bg=self.PANEL,
                fg=self.TEXT,
                activebackground=self.PANEL_2,
                activeforeground=self.GOLD,
                relief="flat",
                padx=16,
                pady=13,
                cursor="hand2",
            )
            button.pack(fill="x", padx=8, pady=2)
            self.category_buttons[category] = button

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

        # 游戏列表使用 Canvas 承载，以便在当前分类内容过多时滚动。
        # 滚动条默认隐藏，只有当前分类的内容超过可视区域时才显示。
        self.games_container = tk.Frame(content, bg=self.BG)
        self.games_container.pack(fill="both", expand=True)

        self.games_scrollbar = tk.Scrollbar(
            self.games_container,
            orient="vertical",
        )

        self.games_canvas = tk.Canvas(
            self.games_container,
            bg=self.BG,
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self.games_canvas.pack(side="left", fill="both", expand=True)

        self.games_scrollbar.config(command=self.games_canvas.yview)
        self.games_canvas.config(yscrollcommand=self.games_scrollbar.set)

        self.games_frame = tk.Frame(self.games_canvas, bg=self.BG)
        self.games_canvas_window = self.games_canvas.create_window(
            (0, 0),
            window=self.games_frame,
            anchor="nw",
        )

        self.scrollbar_visible = False

        self.games_frame.bind(
            "<Configure>",
            self._on_games_frame_configure,
        )
        self.games_canvas.bind(
            "<Configure>",
            self._on_games_canvas_configure,
        )

        # Windows / macOS 鼠标滚轮。
        self._wheel_bindings.append((
            "<MouseWheel>",
            self.bind_all("<MouseWheel>", self._on_mousewheel, add="+"),
        ))
        # Linux 鼠标滚轮。
        self._wheel_bindings.append((
            "<Button-4>",
            self.bind_all("<Button-4>", self._on_mousewheel_linux, add="+"),
        ))
        self._wheel_bindings.append((
            "<Button-5>",
            self.bind_all("<Button-5>", self._on_mousewheel_linux, add="+"),
        ))

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

        self.running_label = tk.Label(
            bottom,
            text="",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.PANEL,
            fg=self.GOLD,
        )
        self.running_label.pack(side="right", padx=20)

    def _on_games_frame_configure(self, event=None) -> None:
        """更新当前分类的实际滚动范围。"""
        try:
            if self._closing:
                return
            bbox = self.games_canvas.bbox("all")
            self.games_canvas.configure(
                scrollregion=(0, 0, 0, 0) if bbox is None else bbox
            )
            self._schedule_scrollbar_update()
        except tk.TclError:
            return

    def _on_games_canvas_configure(self, event) -> None:
        """Canvas 改变大小时，让内部列表宽度与可视区域保持一致。"""
        try:
            if self._closing:
                return
            self.games_canvas.itemconfigure(
                self.games_canvas_window,
                width=max(event.width, 1),
            )
            self._schedule_scrollbar_update()
        except tk.TclError:
            return

    def _schedule_scrollbar_update(self) -> None:
        """合并重复的 idle 更新，并避免页面销毁后继续访问子控件。"""
        try:
            if self._closing or not self.winfo_exists():
                return
            if self._scrollbar_job is not None:
                self.after_cancel(self._scrollbar_job)
            self._scrollbar_job = self.after_idle(
                self._update_scrollbar_visibility
            )
        except tk.TclError:
            self._scrollbar_job = None

    def _on_page_destroy(self, event) -> None:
        if event.widget is not self:
            return
        self._closing = True
        if self._scrollbar_job is not None:
            try:
                self.after_cancel(self._scrollbar_job)
            except tk.TclError:
                pass
            self._scrollbar_job = None
        for sequence, func_id in self._wheel_bindings:
            if not func_id:
                continue
            try:
                self._root()._unbind(("bind", "all", sequence), func_id)
            except (tk.TclError, AttributeError):
                pass
        self._wheel_bindings.clear()

    def _update_scrollbar_visibility(self) -> None:
        """
        只根据当前分类的实际内容决定是否显示滚动条。

        当前分类内容没有超过 Canvas 高度时隐藏滚动条；
        超过时显示，滚动终点正好是当前分类最后一行卡片的底部。
        """
        self._scrollbar_job = None
        try:
            if self._closing or not self.winfo_exists():
                return
            if not (self.games_canvas.winfo_exists()
                    and self.games_frame.winfo_exists()
                    and self.games_scrollbar.winfo_exists()):
                return

            self.games_canvas.update_idletasks()
            if self._closing or not self.games_frame.winfo_exists():
                return

            content_height = self.games_frame.winfo_reqheight()
            canvas_height = self.games_canvas.winfo_height()
            needs_scrollbar = canvas_height > 1 and content_height > canvas_height

            if needs_scrollbar and not self.scrollbar_visible:
                self.games_scrollbar.pack(side="right", fill="y")
                self.scrollbar_visible = True
            elif not needs_scrollbar and self.scrollbar_visible:
                self.games_scrollbar.pack_forget()
                self.scrollbar_visible = False
                self.games_canvas.yview_moveto(0)

            bbox = self.games_canvas.bbox("all")
            self.games_canvas.configure(
                scrollregion=(0, 0, 0, 0) if bbox is None
                else (0, 0, bbox[2], content_height)
            )
        except (tk.TclError, AttributeError):
            return

    def _event_is_inside_games_area(self, event) -> bool:
        """判断滚轮事件是否来自游戏列表、卡片、图片或文字。"""
        try:
            if not self.winfo_exists():
                return False

            widget = getattr(event, "widget", None)

            while widget is not None:
                if (
                    widget is self.games_canvas
                    or widget is self.games_frame
                    or widget is self.games_container
                ):
                    return True

                widget = getattr(widget, "master", None)

            return False

        except (tk.TclError, AttributeError):
            # 页面已经被销毁时，旧的 bind_all 回调会安全结束。
            return False

    def _on_mousewheel(self, event) -> Optional[str]:
        """Windows / macOS：图片、文字和卡片内部都可以滚动。"""
        try:
            if not self.winfo_exists():
                return None
            if not self.scrollbar_visible:
                return None
            if not self._event_is_inside_games_area(event):
                return None

            delta = int(-event.delta / 120)
            if delta == 0:
                delta = -1 if event.delta > 0 else 1

            self.games_canvas.yview_scroll(delta * 4, "units")
            return "break"

        except tk.TclError:
            return None

    def _on_mousewheel_linux(self, event) -> Optional[str]:
        """Linux：图片、文字和卡片内部都可以滚动。"""
        try:
            if not self.winfo_exists():
                return None
            if not self.scrollbar_visible:
                return None
            if not self._event_is_inside_games_area(event):
                return None

            direction = -1 if event.num == 4 else 1
            self.games_canvas.yview_scroll(direction * 4, "units")
            return "break"

        except tk.TclError:
            return None

    def _refresh_balance_label(self) -> None:
        self.balance_var.set(self._tr(f"余额  ${self.balance:,.2f}"))

    def set_balance(self, balance: float) -> None:
        self.balance = float(balance)
        self._refresh_balance_label()

    def _get_game_image_path(self, module_name: Optional[str]) -> Optional[str]:
        """
        根据模块名称自动寻找游戏图片。

        例如：
            Casino_Games.Three_Card_Poker
        会对应：
            当前文件目录/Picture/Three_Card_Poker.png
        """
        if not module_name:
            return None

        image_name = module_name.rsplit(".", 1)[-1] + ".png"
        image_path = os.path.join(THIS_DIR, "Picture", image_name)

        if os.path.isfile(image_path):
            return image_path
        return None

    def _load_game_image(
        self,
        module_name: Optional[str],
        maintenance: bool = False,
        max_width: int = 250,
        max_height: int = 150,
    ) -> Optional[tk.PhotoImage]:
        """
        加载并缩放游戏 PNG。

        优先使用 Pillow 进行高质量缩放；如果电脑没有安装 Pillow，
        则自动退回 Tkinter PhotoImage，并使用 subsample 缩小。
        """
        image_path = self._get_game_image_path(module_name)
        if image_path is None:
            return None

        cache_key = (
            f"{image_path}|{max_width}x{max_height}|"
            f"maintenance={maintenance}"
        )
        if cache_key in self.game_images:
            return self.game_images[cache_key]

        try:
            if Image is not None and ImageTk is not None:
                image = Image.open(image_path).convert("RGBA")
                image.thumbnail((max_width, max_height), Image.LANCZOS)

                if maintenance:
                    # 维护中的游戏：转成灰阶，并加入半透明暗色蒙版。
                    image = ImageOps.grayscale(image).convert("RGBA")
                    dark_overlay = Image.new(
                        "RGBA",
                        image.size,
                        (0, 0, 0, 75),
                    )
                    image = Image.alpha_composite(image, dark_overlay)

                    draw = ImageDraw.Draw(image)
                    text = "维护"

                    # 优先寻找 Windows 中文字体；找不到时退回 Pillow 默认字体。
                    font = None
                    font_candidates = [
                        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyhbd.ttc"),
                        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyh.ttc"),
                        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "simhei.ttf"),
                    ]
                    for font_path in font_candidates:
                        try:
                            if os.path.isfile(font_path):
                                font = ImageFont.truetype(font_path, 38)
                                break
                        except (OSError, ValueError):
                            continue

                    if font is None:
                        try:
                            font = ImageFont.truetype("msyh.ttc", 38)
                        except (OSError, ValueError):
                            font = ImageFont.load_default()

                    try:
                        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                    except AttributeError:
                        text_width, text_height = draw.textsize(text, font=font)

                    text_x = (image.width - text_width) / 2
                    text_y = (image.height - text_height) / 2

                    # 白色粗体文字配黑色描边，确保在不同图片上都清晰可见。
                    draw.text(
                        (text_x, text_y),
                        text,
                        font=font,
                        fill=(245, 245, 245, 255),
                        stroke_width=3,
                        stroke_fill=(20, 20, 20, 255),
                    )

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

            self.game_images[cache_key] = photo
            return photo

        except (OSError, tk.TclError, ValueError):
            return None

    @staticmethod
    def _bind_to_all_children(
        widget: tk.Misc,
        sequence: str,
        callback: Callable,
    ) -> None:
        """把鼠标事件绑定到卡片及其所有子控件。"""
        widget.bind(sequence, callback)
        for child in widget.winfo_children():
            SlotMachinesPage._bind_to_all_children(child, sequence, callback)

    def _set_card_background(self, card: tk.Frame, colour: str) -> None:
        """同步修改卡片及其子控件的背景颜色。"""
        def recolour(widget: tk.Misc) -> None:
            try:
                widget.config(bg=colour)
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                recolour(child)

        recolour(card)

    def _set_cursor_for_widget_tree(
        self,
        widget: tk.Misc,
        cursor: str,
    ) -> None:
        """递归修改控件及其所有子控件的鼠标图标。"""
        try:
            widget.config(cursor=cursor)
        except tk.TclError:
            try:
                widget.config(cursor="arrow")
            except tk.TclError:
                pass

        for child in widget.winfo_children():
            self._set_cursor_for_widget_tree(child, cursor)

    def show_category(self, category: str) -> None:
        if self.process is not None:
            return

        self.current_category = category
        self.category_title.config(text=self._tr(category))

        for name, button in self.category_buttons.items():
            selected = name == category
            button.config(
                bg=self.PANEL_2 if selected else self.PANEL,
                fg=self.GOLD if selected else self.TEXT,
            )

        # 切换分类时先回到顶部，并清除上一个分类的网格配置。
        self.games_canvas.yview_moveto(0)

        for widget in self.games_frame.winfo_children():
            widget.destroy()

        for column in range(self.games_frame.grid_size()[0]):
            self.games_frame.grid_columnconfigure(column, weight=0, minsize=0)

        for row in range(self.games_frame.grid_size()[1]):
            self.games_frame.grid_rowconfigure(row, weight=0, minsize=0)

        self.game_cards.clear()

        games = GAME_SECTIONS[category]
        column_count = 3

        for column in range(column_count):
            self.games_frame.grid_columnconfigure(
                column,
                weight=1,
                uniform="games",
                minsize=185,
            )

        row_count = (len(games) + column_count - 1) // column_count
        for row in range(row_count):
            # 行高固定，不使用 weight=1。
            # 否则项目较少时卡片会被强制拉高，造成错误的滚动范围。
            self.games_frame.grid_rowconfigure(
                row,
                weight=0,
                minsize=240,
            )

        for index, (display_name, module_name, maintenance) in enumerate(games):
            row, column = divmod(index, column_count)

            normal_bg = self.MAINTENANCE if maintenance else self.PANEL_2
            hover_bg = normal_bg if maintenance else self.HOVER
            text_colour = self.TEXT
            # 维护游戏显示禁止光标；正常游戏显示普通箭头。
            cursor = "no" if maintenance else "arrow"

            card = tk.Frame(
                self.games_frame,
                bg=normal_bg,
                bd=0,
                highlightthickness=1,
                highlightbackground=(
                    self.MAINTENANCE_BORDER if maintenance else self.CARD_BORDER
                ),
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
            card.grid_propagate(False)

            image = self._load_game_image(
                module_name,
                maintenance=maintenance,
            )

            favorite_bar = None
            if not maintenance:
                favorite_bar = tk.Frame(card, bg=normal_bg, height=30)
                favorite_bar.pack(fill="x", padx=8, pady=(5, 0))
                favorite_bar.pack_propagate(False)

            image_area = tk.Frame(
                card,
                bg=normal_bg,
                height=150,
                cursor=cursor,
            )
            image_area.pack(fill="x", expand=True, padx=8, pady=(0, 0))
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
                fallback_text = "PNG"
                if maintenance:
                    fallback_text = "维护"

                image_label = tk.Label(
                    image_area,
                    text=self._tr(fallback_text),
                    font=("Microsoft YaHei UI", 15, "bold"),
                    bg=normal_bg,
                    fg=self.TEXT,
                    bd=0,
                    cursor=cursor,
                )
                image_label.pack(expand=True)

            name_label = tk.Label(
                card,
                text=self._tr(display_name),
                font=("Microsoft YaHei UI", 11, "bold"),
                bg=normal_bg,
                fg=text_colour,
                bd=0,
                cursor=cursor,
                wraplength=190,
            )
            name_label.pack(fill="x", padx=8, pady=(0, 8))

            card_info = {
                "card": card,
                "maintenance": maintenance,
                "normal_bg": normal_bg,
                "hover_bg": hover_bg,
                "display_name": display_name,
                "module_name": module_name,
            }
            self.game_cards.append(card_info)

            if maintenance:
                # 维护中的游戏不绑定点击、移入或移出事件。
                # 卡片及其子控件已经使用 cursor="no"，点击不会有任何反应。
                pass
            else:
                def on_click(
                    event,
                    game_name=display_name,
                    game_module=module_name,
                ):
                    self.launch_game(game_name, game_module, False)

                def on_enter(
                    event,
                    current_card=card,
                    colour=hover_bg,
                ):
                    self._set_card_background(current_card, colour)
                    current_card.config(highlightbackground=self.GOLD)

                def on_leave(
                    event,
                    current_card=card,
                    colour=normal_bg,
                ):
                    self._set_card_background(current_card, colour)
                    current_card.config(highlightbackground=self.CARD_BORDER)

                self._bind_to_all_children(card, "<Button-1>", on_click)
                self._bind_to_all_children(card, "<Enter>", on_enter)
                self._bind_to_all_children(card, "<Leave>", on_leave)

                favorite_active = is_favorite(self.username, module_name)
                heart = tk.Button(
                    favorite_bar, text="♥" if favorite_active else "♡",
                    font=("Segoe UI Symbol", 15, "bold"),
                    bg=normal_bg, fg=self.RED if favorite_active else self.TEXT,
                    activebackground=hover_bg, activeforeground=self.RED,
                    relief="flat", bd=0, padx=5, pady=2, cursor="hand2",
                )
                heart.pack(side="right")

                def toggle_heart(button=heart, game_name=display_name,
                                 game_module=module_name):
                    active, message = toggle_favorite(
                        self.username, game_name, game_module
                    )
                    button.configure(text="♥" if active else "♡",
                                     fg=self.RED if active else self.TEXT)
                    self.status_var.set(self._tr(message))

                heart.configure(command=toggle_heart)

        # 所有卡片创建完成后，只按当前分类重新计算滚动条。
        self._schedule_scrollbar_update()

    def _replace_root_page(self, page: tk.Widget) -> None:
        """使用 index.py 的 replace_page() 在同一个 Tk 窗口内切换页面。"""
        replace_page = getattr(self.master, "replace_page", None)
        if not callable(replace_page):
            raise RuntimeError(
                "父窗口没有 replace_page(page) 方法，无法切换页面。"
            )
        replace_page(page)

    def launch_embedded_game(
        self,
        display_name: str,
        module_name: str,
    ) -> None:
        """在 index.py 的同一个根窗口内打开老虎机游戏。"""
        try:
            module = importlib.import_module(module_name)
            game_main = getattr(module, "main", None)
            if not callable(game_main):
                raise AttributeError(f"{module_name} 没有可调用的 main()")

            master = self.master
            username = self.username
            parent_back = self.on_back
            balance_callback = self.on_balance_change

            def return_to_slot_machines(final_balance: float) -> None:
                new_balance = float(final_balance)
                update_balance(username, new_balance)

                if callable(balance_callback):
                    balance_callback(new_balance)

                new_page = SlotMachinesPage(
                    master=master,
                    username=username,
                    balance=new_balance,
                    on_back=parent_back,
                    on_balance_change=balance_callback,
                )
                replace_page = getattr(master, "replace_page", None)
                if not callable(replace_page):
                    raise RuntimeError("父窗口没有 replace_page(page) 方法。")
                replace_page(new_page)

            game_page = game_main(
                parent=master,
                balance=self.balance,
                user=username,
                on_back=return_to_slot_machines,
                on_balance_change=balance_callback,
            )

            if not isinstance(game_page, tk.Widget):
                raise TypeError(
                    f"{module_name}.main() 必须返回一个 Tkinter Widget/Frame。"
                )

            self._replace_root_page(game_page)

        except Exception as exc:
            messagebox.showerror(
                "启动失败",
                f"无法打开《{display_name}》：\n\n"
                f"{type(exc).__name__}: {exc}",
                parent=self,
            )

    def launch_game(
        self,
        display_name: str,
        module_name: Optional[str],
        maintenance: bool = False,
    ) -> None:
        if maintenance:
            messagebox.showinfo(
                "维护通知",
                f"《{display_name}》目前正在维护。",
                parent=self,
            )
            return

        if not module_name:
            messagebox.showerror(
                "启动失败",
                f"《{display_name}》没有设置对应的程序模块。",
                parent=self,
            )
            return
        if module_name in LEGACY_PROCESS_MODULES:
            self._launch_legacy_process_game(display_name, module_name)
            return

        # 当前老虎机游戏均在 index.py 唯一 Tk 根窗口内打开。
        self.launch_embedded_game(display_name, module_name)

    def _launch_legacy_process_game(
        self,
        display_name: str,
        module_name: str,
    ) -> None:
        """按旧版逻辑在独立 Python 子进程中运行尚未嵌入兼容的游戏。"""
        if self.process is not None:
            return

        import tempfile

        handle, result_file = tempfile.mkstemp(
            prefix="slot_machine_result_",
            suffix=".json",
        )
        os.close(handle)
        try:
            os.remove(result_file)
        except OSError:
            pass

        command = [
            sys.executable,
            os.path.abspath(__file__),
            "--child",
            module_name,
            result_file,
            str(self.balance),
            self.username,
        ]

        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            self.process = subprocess.Popen(
                command,
                cwd=PROJECT_DIR,
                creationflags=creationflags,
            )
        except OSError as exc:
            messagebox.showerror("启动失败", str(exc), parent=self)
            self.process = None
            try:
                os.remove(result_file)
            except OSError:
                pass
            return

        self.result_file = result_file
        self.running_game_name = display_name
        self.status_var.set(self._tr(f"已启动：{display_name}"))
        self.running_label.config(text=self._tr("游戏运行中…"))
        self._set_controls_enabled(False)

        # 与旧版一致：独立游戏运行时老虎机中心先最小化。
        self.winfo_toplevel().iconify()
        self.after(300, self._poll_game_process)

    def _poll_game_process(self) -> None:
        if self.process is None:
            return

        if self.process.poll() is None:
            self.after(300, self._poll_game_process)
            return

        self.winfo_toplevel().deiconify()
        self.winfo_toplevel().lift()

        result = None
        if self.result_file and os.path.exists(self.result_file):
            try:
                with open(self.result_file, "r", encoding="utf-8") as file:
                    result = json.load(file)
            except (OSError, json.JSONDecodeError):
                result = None

        if self.result_file:
            try:
                os.remove(self.result_file)
            except OSError:
                pass

        old_name = self.running_game_name
        self.process = None
        self.result_file = None
        self.running_game_name = ""
        self.running_label.config(text="")
        self._set_controls_enabled(True)

        if result and result.get("ok"):
            try:
                self.balance = float(result["balance"])
            except (TypeError, ValueError, KeyError):
                self.balance = read_balance(self.username, self.balance)
            update_balance(self.username, self.balance)
            self._refresh_balance_label()
            if self.on_balance_change:
                self.on_balance_change(self.balance)
            self.status_var.set(self._tr(f"{old_name} 已结束，余额已更新"))
        else:
            # 即使游戏异常退出，也重新读取存档，避免丢失已写入的余额。
            self.balance = read_balance(self.username, self.balance)
            self._refresh_balance_label()
            if self.on_balance_change:
                self.on_balance_change(self.balance)

            error = ""
            if isinstance(result, dict):
                error = str(result.get("error", ""))
            self.status_var.set(self._tr(f"{old_name} 已关闭"))
            if error:
                messagebox.showerror(
                    "游戏运行出错",
                    f"{old_name} 未正常结束：\n\n{error}",
                    parent=self,
                )

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"

        for button in self.category_buttons.values():
            button.config(state=state)

        for card_info in self.game_cards:
            card = card_info["card"]
            maintenance = card_info["maintenance"]

            if maintenance:
                continue

            cursor = "hand2" if enabled else "arrow"
            try:
                card.config(cursor=cursor)
            except tk.TclError:
                continue

            for child in card.winfo_children():
                try:
                    child.config(cursor=cursor)
                except tk.TclError:
                    pass
                for grandchild in child.winfo_children():
                    try:
                        grandchild.config(cursor=cursor)
                    except tk.TclError:
                        pass

    def back_to_main(self) -> None:
        if self.process is not None:
            messagebox.showwarning(
                "游戏运行中",
                "请先关闭当前运行中的游戏。",
                parent=self,
            )
            return
        self.on_back(self.balance)

    # index.py 会把右上角 X 绑定到当前页面的 on_close。
    on_close = back_to_main


def main(
    parent: tk.Misc,
    balance: float,
    user: str,
    on_back: Callable[[float], None],
    on_balance_change: Optional[Callable[[float], None]] = None,
    on_preferences: Optional[Callable[[], None]] = None,
    translator: Optional[Callable[[str], str]] = None,
) -> SlotMachinesPage:
    """
    供 index.py 使用；不会创建新的 Tk 根窗口或 mainloop。
    """
    return SlotMachinesPage(
        parent,
        username=user,
        balance=balance,
        on_back=on_back,
        on_balance_change=on_balance_change,
        on_preferences=on_preferences,
        translator=translator,
    )


if __name__ == "__main__":
    if len(sys.argv) >= 6 and sys.argv[1] == "--child":
        raise SystemExit(
            child_run(
                module_name=sys.argv[2],
                result_file=sys.argv[3],
                balance_text=sys.argv[4],
                username=sys.argv[5],
            )
        )

    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(
        "提示",
        "slot_machines.py 应由项目根目录的 index.py 启动。",
        parent=root,
    )
    root.destroy()

import importlib
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk
except ImportError:
    Image = None
    ImageTk = None
from typing import Callable, Optional


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(THIS_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, "saving_data.json")

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


EMBEDDED_GAME_MODULES = {
    "Casino_Games.Mississippi_Stud_Poker",
    "Casino_Games.Criss_Cross_Poker",
    "Casino_Games.Three_Card_Poker",
    "Casino_Games.Ultimate_Omaha_Holdem",
    "Casino_Games.Ultimate_Texas_Holdem",
    "Casino_Games.Ultimate_Three_Card_Poker",
    "Casino_Games.Video_Poker",
    "Casino_Games.Wild_Five_Card_Poker",
    "Casino_Games.Caribbean_Stud_Poker",
    "Casino_Games.Casino_Holdem",
    "Casino_Games.Casino_War",
    "Casino_Games.DJ_Wild",
    "Casino_Games.Four_Card_Poker",
    "Casino_Games.Heads_Up_Holdem",
    "Casino_Games.I_Love_Flush",
    "Casino_Games.In_Or_Out",
    "Casino_Games.Let_It_Ride",
    "Casino_Games.Lunar_Poker",
    "Casino_Games.Auto_Texas_Holdem",
    "Casino_Games.Auto_Stud_Poker",
    "Casino_Games.Craps",
    "Casino_Games.Sicbo",
}

GAME_SECTIONS = {
    "扑克": [
        ("三张牌扑克", "Casino_Games.Three_Card_Poker", False),
        ("视频扑克", "Casino_Games.Video_Poker", False),
        ("加勒比梭哈扑克", "Casino_Games.Caribbean_Stud_Poker", False),
        ("月亮梭哈扑克", "Casino_Games.Lunar_Poker", False),
        ("四张牌扑克", "Casino_Games.Four_Card_Poker", False),
        ("赌场扑克", "Casino_Games.Casino_Holdem", False),
        ("DJ Wild梭哈扑克", "Casino_Games.DJ_Wild", False),
        ("密西西比梭哈扑克", "Casino_Games.Mississippi_Stud_Poker", False),
        ("纵横交叉扑克", "Casino_Games.Criss_Cross_Poker", False),
        ("任逍遥扑克", "Casino_Games.Let_It_Ride", False),
        ("单挑扑克", "Casino_Games.Heads_Up_Holdem", False),
        ("终极德州扑克", "Casino_Games.Ultimate_Texas_Holdem", False),
        ("终极奥马哈扑克", "Casino_Games.Ultimate_Omaha_Holdem", False),
        ("内外注", "Casino_Games.In_Or_Out", False),
        ("牌九扑克", "Casino_Games.Pai_Gow_Poker", False),
        ("王牌五张扑克", "Casino_Games.Wild_Five_Card_Poker", False),
        ("终极三张牌扑克", "Casino_Games.Ultimate_Three_Card_Poker", False),
        ("赌场战争", "Casino_Games.Casino_War", False),
        ("我爱同花", "Casino_Games.I_Love_Flush", False),
    ],
    "百家乐": [
        ("百家乐", "Casino_Games.Baccarat", False),
        ("龙虎斗", "Casino_Games.Dragon_Tiger", False),
        ("龙虎凤", "Casino_Games.Dragon_Tiger_Phoenix", False),
    ],
    "21点": [
        ("简单21点", "Casino_Games.Blackjack_Easy", False),
        ("经典21点", "Casino_Games.Blackjack_Classic", False),
        ("西班牙式21点", "Casino_Games.Blackjack_Spanish", False),
        ("豪赢21点", "Casino_Games.Blackjack_Multiply", False),
        ("免牌加倍21点", "Casino_Games.Blackjack_Double_Up", False),
        ("双向21点", "Casino_Games.Blackjack_Premiere", False),
        ("无限加倍21点", "Casino_Games.Blackjack_Double", False),
    ],
    "骰子": [
        ("花旗骰", "Casino_Games.Craps", False),
        ("克朗代克（维护）", "Casino_Games.Klondike_Dice", True),
        ("骰宝", "Casino_Games.Sicbo", False),
        ("骰子百家乐", "Casino_Games.BacBo", False),
    ],
    "二人对决": [
        ("德州扑克双人对决", "Casino_Games.Auto_Texas_Holdem", False),
        ("梭哈扑克双人对决", "Casino_Games.Auto_Stud_Poker", False),
    ],
    "轮盘赌": [
        ("美式轮盘", "Casino_Games.Roulette_American", False),
        ("欧式轮盘", "Casino_Games.Roulette_Europe", False),
        ("幸运之轮", "Casino_Games.Big_Six_Wheel", False),
    ],
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
            # 某些游戏直接写 saving_data.json，不返回余额。
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


class CasinoGamesPage(tk.Frame):
    """嵌入 index.py 唯一根窗口的赌场选择页面。"""

    BG = "#081a16"
    PANEL = "#102923"
    PANEL_2 = "#17362e"
    GOLD = "#e7be63"
    TEXT = "#f5f1e8"
    MUTED = "#afc3ba"
    RED = "#b94d4d"

    def __init__(
        self,
        master: tk.Misc,
        username: str,
        balance: float,
        on_back: Callable[[float], None],
        on_balance_change: Optional[Callable[[float], None]] = None,
    ):
        super().__init__(master, bg=self.BG)
        self.username = username
        self.balance = float(balance)
        self.on_back = on_back
        self.on_balance_change = on_balance_change

        self.current_category = "扑克"
        self.process: Optional[subprocess.Popen] = None
        self.result_file: Optional[str] = None
        self.running_game_name = ""

        self.balance_var = tk.StringVar()
        self.status_var = tk.StringVar(value="请选择游戏")
        self.category_buttons = {}
        self.game_cards = []
        self.game_images = {}

        self._build_ui()
        self.show_category(self.current_category)

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg=self.PANEL, height=82)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Button(
            top,
            text="← 返回主目录",
            command=self.back_to_main,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.PANEL_2,
            fg=self.TEXT,
            activebackground=self.GOLD,
            activeforeground="#182018",
            relief="flat",
            padx=18,
            pady=9,
            cursor="hand2",
        ).pack(side="left", padx=22, pady=18)

        tk.Label(
            top,
            text="赌场游戏中心",
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

        body = tk.Frame(self, bg=self.BG)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=self.PANEL, width=205)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="游戏分类",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg=self.PANEL,
            fg=self.GOLD,
        ).pack(anchor="w", padx=22, pady=(25, 15))

        for category in GAME_SECTIONS:
            button = tk.Button(
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
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        # Linux 鼠标滚轮。
        self.bind_all("<Button-4>", self._on_mousewheel_linux, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel_linux, add="+")

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
        bbox = self.games_canvas.bbox("all")
        if bbox is None:
            self.games_canvas.configure(scrollregion=(0, 0, 0, 0))
        else:
            self.games_canvas.configure(scrollregion=bbox)

        self.after_idle(self._update_scrollbar_visibility)

    def _on_games_canvas_configure(self, event) -> None:
        """Canvas 改变大小时，让内部列表宽度与可视区域保持一致。"""
        self.games_canvas.itemconfigure(
            self.games_canvas_window,
            width=max(event.width, 1),
        )
        self.after_idle(self._update_scrollbar_visibility)

    def _update_scrollbar_visibility(self) -> None:
        """
        只根据当前分类的实际内容决定是否显示滚动条。

        当前分类内容没有超过 Canvas 高度时隐藏滚动条；
        超过时显示，滚动终点正好是当前分类最后一行卡片的底部。
        """
        if not self.games_canvas.winfo_exists():
            return

        self.games_canvas.update_idletasks()

        content_height = self.games_frame.winfo_reqheight()
        canvas_height = self.games_canvas.winfo_height()

        needs_scrollbar = (
            canvas_height > 1
            and content_height > canvas_height
        )

        if needs_scrollbar and not self.scrollbar_visible:
            self.games_scrollbar.pack(side="right", fill="y")
            self.scrollbar_visible = True

        elif not needs_scrollbar and self.scrollbar_visible:
            self.games_scrollbar.pack_forget()
            self.scrollbar_visible = False
            self.games_canvas.yview_moveto(0)

        bbox = self.games_canvas.bbox("all")
        if bbox is None:
            self.games_canvas.configure(scrollregion=(0, 0, 0, 0))
        else:
            self.games_canvas.configure(
                scrollregion=(0, 0, bbox[2], content_height)
            )

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
        self.balance_var.set(f"余额：${self.balance:,.2f}")

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
            CasinoGamesPage._bind_to_all_children(child, sequence, callback)

    def _set_card_background(self, card: tk.Frame, colour: str) -> None:
        """同步修改卡片及其子控件的背景颜色。"""
        try:
            card.config(bg=colour)
        except tk.TclError:
            return

        for child in card.winfo_children():
            try:
                child.config(bg=colour)
            except tk.TclError:
                pass

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
        self.category_title.config(text=category)

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

            normal_bg = "#263f38" if maintenance else self.PANEL_2
            hover_bg = normal_bg if maintenance else "#245246"
            text_colour = "#81938c" if maintenance else self.TEXT
            # 维护游戏显示禁止光标；正常游戏显示普通箭头。
            cursor = "no" if maintenance else "arrow"

            card = tk.Frame(
                self.games_frame,
                bg=normal_bg,
                bd=0,
                highlightthickness=1,
                highlightbackground="#345048" if maintenance else "#2e5a4d",
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
                fallback_text = "PNG"
                if maintenance:
                    fallback_text = "维护"

                image_label = tk.Label(
                    image_area,
                    text=fallback_text,
                    font=("Microsoft YaHei UI", 15, "bold"),
                    bg=normal_bg,
                    fg="#60756d" if maintenance else "#6f9487",
                    bd=0,
                    cursor=cursor,
                )
                image_label.pack(expand=True)

            name_label = tk.Label(
                card,
                text=display_name,
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
                    current_card.config(highlightbackground="#2e5a4d")

                self._bind_to_all_children(card, "<Button-1>", on_click)
                self._bind_to_all_children(card, "<Enter>", on_enter)
                self._bind_to_all_children(card, "<Leave>", on_leave)

        # 所有卡片创建完成后，只按当前分类重新计算滚动条。
        self.after_idle(self._update_scrollbar_visibility)

    def _replace_root_page(self, page: tk.Widget) -> None:
        """使用 index.py 的 replace_page() 在同一个 Tk 窗口内切换页面。"""
        replace_page = getattr(self.master, "replace_page", None)
        if not callable(replace_page):
            raise RuntimeError(
                "父窗口没有 replace_page(page) 方法，无法进行嵌入式页面切换。"
            )
        replace_page(page)

    def launch_embedded_game(
        self,
        display_name: str,
        module_name: str,
    ) -> None:
        """在 index.py 的同一个根窗口内打开已转换为 Frame 的游戏。"""
        try:
            module = importlib.import_module(module_name)
            game_main = getattr(module, "main", None)
            if not callable(game_main):
                raise AttributeError(f"{module_name} 没有可调用的 main()")

            master = self.master
            username = self.username
            parent_back = self.on_back
            balance_callback = self.on_balance_change

            def return_to_casino(final_balance: float) -> None:
                new_balance = float(final_balance)
                update_balance(username, new_balance)

                if callable(balance_callback):
                    balance_callback(new_balance)

                new_page = CasinoGamesPage(
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
                on_back=return_to_casino,
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
                f"无法在当前窗口打开《{display_name}》：\n\n"
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

        # 已转换为 tk.Frame 的游戏直接在 index.py 当前窗口中打开。
        if module_name in EMBEDDED_GAME_MODULES:
            self.launch_embedded_game(display_name, module_name)
            return

        # 其他尚未转换的旧游戏继续使用原来的独立子进程方式。
        if self.process is not None:
            return

        import tempfile

        handle, result_file = tempfile.mkstemp(prefix="casino_result_", suffix=".json")
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
                # 不额外弹出黑色命令行窗口。
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            self.process = subprocess.Popen(
                command,
                cwd=PROJECT_DIR,
                creationflags=creationflags,
            )
        except OSError as exc:
            messagebox.showerror("启动失败", str(exc), parent=self)
            self.process = None
            return

        self.result_file = result_file
        self.running_game_name = display_name
        self.status_var.set(f"已启动：{display_name}")
        self.running_label.config(text="游戏运行中…")
        self._set_controls_enabled(False)

        # 主窗口保留在同一进程，但暂时最小化，子游戏完全独立。
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
            self.status_var.set(f"{old_name} 已结束，余额已更新")
        else:
            # 即使游戏异常退出，也重新读取存档，避免丢失已写入的余额。
            self.balance = read_balance(self.username, self.balance)
            self._refresh_balance_label()
            if self.on_balance_change:
                self.on_balance_change(self.balance)

            error = ""
            if isinstance(result, dict):
                error = str(result.get("error", ""))
            self.status_var.set(f"{old_name} 已关闭")
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


def main(
    parent: tk.Misc,
    balance: float,
    user: str,
    on_back: Callable[[float], None],
    on_balance_change: Optional[Callable[[float], None]] = None,
) -> CasinoGamesPage:
    """
    供 index.py 使用。不会创建 Tk 或 mainloop。
    """
    return CasinoGamesPage(
        parent,
        username=user,
        balance=balance,
        on_back=on_back,
        on_balance_change=on_balance_change,
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
        "casino_games.py 应由项目根目录的 index.py 启动。",
        parent=root,
    )
    root.destroy()
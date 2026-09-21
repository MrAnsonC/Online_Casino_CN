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
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from typing import Callable, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, "A_Tools/Account/saving_data.json")


def greeting_for(username: str) -> str:
    hour = datetime.now().hour
    period = "凌晨好" if hour < 6 else "早上好" if hour < 12 else "中午好" if hour < 18 else "晚上好"
    return f"{period}，{username}！"


def _ui_colour(master: tk.Misc, colour: str) -> str:
    resolver = getattr(master.winfo_toplevel(), "theme_colour", None)
    return resolver(colour) if callable(resolver) else colour


LOTTO_GAMES = [
    {
        "name": "验钞机",
        "subtitle": "1 元 / 特易中奖",
        "prize": "大奖 1,000",
        "module": "Lotto.Banknote_Detection_gui",
    },
    {
        "name": "高尔夫球",
        "subtitle": "每局 1 元",
        "prize": "大奖 10,000",
        "module": "Lotto.golfs_gui",
    },
    {
        "name": "过三关",
        "subtitle": "每局 1 元",
        "prize": "大奖 10,000",
        "module": "Lotto.pass_3_level_gui",
    },
    {
        "name": "叠叠乐",
        "subtitle": "每局 5 元",
        "prize": "大奖 50,000",
        "module": "Lotto.stacked",
    },
    {
        "name": "100X 现金大挑战",
        "subtitle": "每局 5 元",
        "prize": "大奖 50,000",
        "module": "Lotto.num_gui",
    },
]


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


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            save_user_data(users)
            return


def is_favorite(username: str, module_name: str) -> bool:
    if username == "TEMP_ACCOUNT":
        return False
    for user in load_user_data():
        if user.get("user_name") == username:
            return any(item.get("module") == module_name
                       for item in user.get("favorites", []) if isinstance(item, dict))
    return False


def toggle_favorite(username: str, display_name: str, module_name: str) -> tuple[bool, str]:
    if username == "TEMP_ACCOUNT":
        return False, "体验账号不会储存收藏。"
    users = load_user_data()
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
        save_user_data(users)
        return active, message
    return False, "找不到玩家资料，无法储存收藏。"


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


class LottoPage(tk.Frame):
    """嵌入 index.py 唯一 Tk 根窗口的刮刮乐目录。"""

    BG = "#F7F3EA"
    PANEL = "#E6D9F2"
    CARD = "#DDF2E5"
    CARD_HOVER = "#F6D0D8"
    GOLD = "#111111"
    TEXT = "#111111"
    MUTED = "#111111"

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
        for name in ("BG", "PANEL", "CARD", "CARD_HOVER", "GOLD", "TEXT", "MUTED"):
            setattr(self, name, _ui_colour(master, getattr(type(self), name)))
        self.SURFACE = _ui_colour(master, "#FFFFFF")
        super().__init__(master, bg=self.BG)
        self._uploaded_scope = True
        self.username = username
        self.balance = float(balance)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.on_preferences = on_preferences
        self.translator = translator
        self.game_cards = []

        self.balance_var = tk.StringVar()
        self.status_var = tk.StringVar(value=self._tr("请选择一张刮刮卡"))
        self._build_ui()
        self._refresh_balance_label()
        self._preferences_ready = True

    def _tr(self, text: str) -> str:
        if callable(self.translator):
            return self.translator(text)
        translator = getattr(self.winfo_toplevel(), "translate_ui", None)
        return translator(text) if callable(translator) else text

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=self.PANEL, height=82)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_area = tk.Frame(header, bg=self.PANEL)
        title_area.pack(side="left", padx=(22, 10))
        title_text = self._tr("刮刮乐中心")
        title_size = 19 if len(title_text) > 16 else 23
        tk.Label(
            title_area,
            text=title_text,
            font=("Microsoft YaHei UI", title_size, "bold"),
            wraplength=250,
            justify="left",
            bg=self.PANEL,
            fg=self.GOLD,
        ).pack(anchor="w")

        tk.Button(
            header,
            text=self._tr("← 返回主目录"),
            command=self.back_to_main,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=self.CARD,
            fg=self.TEXT,
            activebackground=self.CARD_HOVER,
            activeforeground=self.TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=10,
            wraplength=155,
            justify="center",
        ).pack(side="left", padx=(0, 22), pady=18)

        tk.Label(header, text=self._tr(greeting_for(self.username)),
                 font=("Microsoft YaHei UI", 11, "bold"),
                 wraplength=220, justify="center",
                 bg=self.PANEL, fg=self.TEXT).place(
                     relx=0.62, rely=0.5, anchor="center"
                 )

        info = tk.Frame(header, bg=self.SURFACE, padx=18, pady=9,
                        highlightbackground="#CBBBDD", highlightthickness=1)
        info.pack(side="right", padx=25, pady=14)
        tk.Label(info, textvariable=self.balance_var,
                 font=("Microsoft YaHei UI", 14, "bold"),
                 bg=self.SURFACE, fg=self.TEXT).pack()
        add_paper_art_ribbon(self, self.BG)

        status = tk.Frame(self, bg=self.BG)
        status.pack(fill="x", padx=35, pady=(18, 6))
        tk.Label(
            status,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 10),
            bg=self.BG,
            fg=self.MUTED,
        ).pack(side="left")

        grid = tk.Frame(self, bg=self.BG)
        grid.pack(expand=True, pady=(0, 30))

        for index, game in enumerate(LOTTO_GAMES):
            row, column = divmod(index, 3)
            card = self._make_game_card(grid, game)
            card.grid(row=row, column=column, padx=13, pady=13)
            self.game_cards.append(card)

    def _make_game_card(self, master: tk.Misc, game: dict) -> tk.Frame:
        card = tk.Frame(master, bg=self.CARD, width=290, height=190, cursor="hand2")
        card.grid_propagate(False)
        card.pack_propagate(False)

        favorite_bar = tk.Frame(card, bg=self.CARD, height=30)
        favorite_bar.pack(fill="x", padx=10, pady=(6, 0))
        favorite_bar.pack_propagate(False)

        tk.Label(
            card,
            text=self._tr(game["name"]),
            font=("Microsoft YaHei UI", 16, "bold"),
            bg=self.CARD,
            fg=self.GOLD,
            cursor="hand2",
            wraplength=250,
            justify="center",
        ).pack(pady=(4, 8))
        tk.Label(
            card,
            text=self._tr(game["subtitle"]),
            font=("Microsoft YaHei UI", 10),
            bg=self.CARD,
            fg=self.MUTED,
            cursor="hand2",
            wraplength=250,
            justify="center",
        ).pack()
        tk.Label(
            card,
            text=self._tr(game["prize"]),
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.CARD,
            fg=self.TEXT,
            cursor="hand2",
            wraplength=250,
            justify="center",
        ).pack(pady=(10, 0))

        def set_bg(widget: tk.Misc, colour: str) -> None:
            try:
                widget.configure(bg=colour)
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                set_bg(child, colour)

        def enter(_event=None):
            set_bg(card, self.CARD_HOVER)

        def leave(_event=None):
            set_bg(card, self.CARD)

        def click(_event=None):
            self.launch_game(game["name"], game["module"])

        for widget in (card, *card.winfo_children()):
            widget.bind("<Enter>", enter)
            widget.bind("<Leave>", leave)
            widget.bind("<Button-1>", click)

        favorite_active = is_favorite(self.username, game["module"])
        heart = tk.Button(
            favorite_bar, text="♥" if favorite_active else "♡",
            font=("Segoe UI Symbol", 15, "bold"),
            bg=self.CARD, fg="#D43D55" if favorite_active else self.TEXT,
            activebackground=self.CARD_HOVER, activeforeground="#D43D55",
            relief="flat", bd=0, padx=5, pady=2, cursor="hand2",
        )
        heart.pack(side="right")

        def toggle_heart():
            active, message = toggle_favorite(
                self.username, game["name"], game["module"]
            )
            heart.configure(text="♥" if active else "♡",
                            fg="#D43D55" if active else self.TEXT)
            self.status_var.set(self._tr(message))

        heart.configure(command=toggle_heart)
        return card

    def _refresh_balance_label(self) -> None:
        self.balance_var.set(self._tr(f"余额  ${self.balance:,.2f}"))

    def _replace_root_page(self, page: tk.Widget) -> None:
        """调用 index.py 的 replace_page()，在唯一 Tk 根窗口中切换页面。"""
        replace_page = getattr(self.master, "replace_page", None)
        if not callable(replace_page):
            raise RuntimeError(
                "父窗口没有 replace_page(page) 方法，无法切换页面。"
            )
        replace_page(page)

    def launch_game(self, display_name: str, module_name: str) -> None:
        try:
            module = importlib.import_module(module_name)
            game_main = getattr(module, "main", None)
            if not callable(game_main):
                raise AttributeError(f"{module_name} 没有可调用的 main()")

            master = self.master
            username = self.username
            parent_back = self.on_back
            balance_callback = self.on_balance_change

            def return_to_lotto(final_balance: float) -> None:
                new_balance = float(final_balance)
                update_balance_in_json(username, new_balance)

                if callable(balance_callback):
                    balance_callback(new_balance)

                new_page = LottoPage(
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
                on_back=return_to_lotto,
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

    def back_to_main(self) -> None:
        self.on_back(self.balance)

    on_close = back_to_main


def main(
    parent: tk.Misc,
    balance: float,
    user: str,
    on_back: Callable[[float], None],
    on_balance_change: Optional[Callable[[float], None]] = None,
    on_preferences: Optional[Callable[[], None]] = None,
    translator: Optional[Callable[[str], str]] = None,
) -> LottoPage:
    """供 index.py 使用；不会创建新的 Tk 根窗口或 mainloop。"""
    return LottoPage(
        parent,
        username=user,
        balance=balance,
        on_back=on_back,
        on_balance_change=on_balance_change,
        on_preferences=on_preferences,
        translator=translator,
    )


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(
        "提示",
        "lotto.py 应由项目根目录的 index.py 启动。",
        parent=root,
    )
    root.destroy()

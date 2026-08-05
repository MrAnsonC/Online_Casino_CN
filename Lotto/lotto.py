import importlib
import json
import os
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, "saving_data.json")


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


class LottoPage(tk.Frame):
    """嵌入 index.py 唯一 Tk 根窗口的刮刮乐目录。"""

    BG = "#071713"
    PANEL = "#102923"
    CARD = "#17362e"
    CARD_HOVER = "#245246"
    GOLD = "#e7be63"
    TEXT = "#f5f1e8"
    MUTED = "#afc3ba"

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
        self.game_cards = []

        self.balance_var = tk.StringVar()
        self.status_var = tk.StringVar(value="请选择一张刮刮卡")
        self._build_ui()
        self._refresh_balance_label()

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=self.PANEL, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Button(
            header,
            text="← 返回主目录",
            command=self.back_to_main,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=self.CARD,
            fg=self.TEXT,
            activebackground=self.GOLD,
            activeforeground="#182018",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=10,
        ).pack(side="left", padx=25, pady=20)

        title_area = tk.Frame(header, bg=self.PANEL)
        title_area.pack(side="left", padx=12)
        tk.Label(
            title_area,
            text="刮刮乐中心",
            font=("Microsoft YaHei UI", 23, "bold"),
            bg=self.PANEL,
            fg=self.GOLD,
        ).pack(anchor="w")
        tk.Label(
            title_area,
            text="点击卡片后将在当前窗口打开游戏，返回时余额会自动同步",
            font=("Microsoft YaHei UI", 9),
            bg=self.PANEL,
            fg=self.MUTED,
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            header,
            textvariable=self.balance_var,
            font=("Microsoft YaHei UI", 15, "bold"),
            bg=self.PANEL,
            fg=self.TEXT,
        ).pack(side="right", padx=30)

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

        tk.Label(
            card,
            text=game["name"],
            font=("Microsoft YaHei UI", 16, "bold"),
            bg=self.CARD,
            fg=self.GOLD,
            cursor="hand2",
        ).pack(pady=(28, 8))
        tk.Label(
            card,
            text=game["subtitle"],
            font=("Microsoft YaHei UI", 10),
            bg=self.CARD,
            fg=self.MUTED,
            cursor="hand2",
        ).pack()
        tk.Label(
            card,
            text=game["prize"],
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.CARD,
            fg=self.TEXT,
            cursor="hand2",
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
        return card

    def _refresh_balance_label(self) -> None:
        self.balance_var.set(f"当前余额  ${self.balance:,.2f}")

    def _replace_root_page(self, page: tk.Widget) -> None:
        """调用 index.py 的 replace_page()，在唯一 Tk 根窗口中切换页面。"""
        replace_page = getattr(self.master, "replace_page", None)
        if not callable(replace_page):
            raise RuntimeError(
                "父窗口没有 replace_page(page) 方法，无法进行嵌入式页面切换。"
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
                f"无法在当前窗口打开《{display_name}》：\n\n"
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
) -> LottoPage:
    """供 index.py 使用；不会创建新的 Tk 根窗口或 mainloop。"""
    return LottoPage(
        parent,
        username=user,
        balance=balance,
        on_back=on_back,
        on_balance_change=on_balance_change,
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
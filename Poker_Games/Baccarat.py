import tkinter as tk
from tkinter import messagebox
import random
import threading
import time

# Tiger Baccarat GUI with betting timer, automatic deal, and traditional draw rules
typing = None
class TigerBaccaratGUI:
    def __init__(self, master):
        self.master = master
        master.title("虎百家乐")
        master.resizable(False, False)

        # 游戏数据
        self.balance = 500_000.12
        self.last_win = 0.00
        self.current_chip = 0
        self.bets = {pos: 0 for pos in [
            "小老虎", "和虎", "大老虎", "虎对子", "老虎",
            "闲", "和", "庄"
        ]}
        self.betting_open = False

        # 储存按钮引用
        self.buttons = {}

        # 布局容器
        self.left_frame = tk.Frame(master, padx=10, pady=10)
        self.left_frame.grid(row=0, column=0)
        self.right_frame = tk.Frame(master, padx=10, pady=10)
        self.right_frame.grid(row=0, column=1, sticky="n")

        # 构建界面
        self._build_bet_grid()
        self._build_info_panel()
        self._build_chip_panel()

        # 启动下注阶段
        self.start_betting()

    def _build_bet_grid(self):
        top = tk.Frame(self.left_frame)
        top.pack(pady=5)
        for name in ["小老虎", "和虎", "大老虎"]:
            btn = tk.Button(top, text=name, width=12, height=4,
                            command=lambda n=name: self.place_bet(n))
            btn.pack(side="left", padx=5)
            self.buttons[name] = btn

        mid = tk.Frame(self.left_frame)
        mid.pack(pady=5)
        tk.Label(mid, width=6).pack(side="left")
        for name in ["虎对子", "老虎"]:
            btn = tk.Button(mid, text=name, width=12, height=4,
                            command=lambda n=name: self.place_bet(n))
            btn.pack(side="left", padx=5)
            self.buttons[name] = btn
        tk.Label(mid, width=6).pack(side="left")

        bot = tk.Frame(self.left_frame)
        bot.pack(pady=5)
        for name in ["闲", "和", "庄"]:
            btn = tk.Button(bot, text=name, width=12, height=4,
                            command=lambda n=name: self.place_bet(n))
            btn.pack(side="left", padx=5)
            self.buttons[name] = btn

    def _build_info_panel(self):
        panel = tk.Frame(self.right_frame)
        panel.pack(pady=5)
        self.lbl_balance = tk.Label(panel, text=f"当前余额: {self.balance:,.2f}", font=("Arial", 12))
        self.lbl_balance.pack(pady=2)
        self.lbl_total = tk.Label(panel, text="当前下注: 0.00", font=("Arial", 12))
        self.lbl_total.pack(pady=2)
        self.lbl_timer = tk.Label(panel, text="下注倒计时: -- 秒", font=("Arial", 12))
        self.lbl_timer.pack(pady=2)
        self.lbl_last = tk.Label(panel, text=f"上局胜利: {self.last_win:,.2f}", font=("Arial", 12))
        self.lbl_last.pack(pady=2)

    def _build_chip_panel(self):
        panel = tk.Frame(self.right_frame)
        panel.pack(pady=20)
        tk.Label(panel, text="选择下注筹码：", font=("Arial", 12)).pack(pady=5)
        for val in [5, 10, 15, 20, 25]:
            btn = tk.Button(panel, text=str(val), width=8,
                            command=lambda v=val: self.select_chip(v))
            btn.pack(pady=3)

    def select_chip(self, value):
        if not self.betting_open:
            messagebox.showwarning("暂停下注", "当前不在下注阶段！")
            return
        self.current_chip = value
        messagebox.showinfo("筹码", f"已选择下注筹码：{value}")

    def place_bet(self, position):
        if not self.betting_open:
            messagebox.showwarning("暂停下注", "当前不在下注阶段！")
            return
        if self.current_chip <= 0:
            messagebox.showwarning("注意", "请先选择筹码！")
            return
        side_bets = {"小老虎","和虎","大老虎","虎对子","老虎"}
        if position in side_bets and all(self.bets[x] == 0 for x in ["闲","和","庄"]):
            messagebox.showwarning("禁止", "请先至少下注‘闲’、‘和’或‘庄’！")
            return
        self.bets[position] += self.current_chip
        self.balance -= self.current_chip
        self._update_buttons()
        self._update_info()

    def _update_buttons(self):
        for name, btn in self.buttons.items():
            amt = self.bets.get(name, 0)
            btn.config(text=f"{name}\n{amt if amt>0 else ''}")

    def _update_info(self):
        total = sum(self.bets.values())
        self.lbl_balance.config(text=f"当前余额: {self.balance:,.2f}")
        self.lbl_total.config(text=f"当前下注: {total:,.2f}")

    def start_betting(self):
        self.betting_open = True
        self.timer = 22
        def countdown():
            while self.timer > 0:
                self.lbl_timer.config(text=f"下注倒计时: {self.timer} 秒")
                time.sleep(1)
                self.timer -= 1
            self.betting_open = False
            self.lbl_timer.config(text="下注结束，发牌中...")
            self.deal_and_settle()
        threading.Thread(target=countdown, daemon=True).start()

    def deal_and_settle(self):
        # 发牌逻辑同前
        player = [random.randint(0,9), random.randint(0,9)]
        banker = [random.randint(0,9), random.randint(0,9)]
        p_score = sum(player) % 10
        b_score = sum(banker) % 10
        player_third = None
        if p_score <= 5:
            player_third = random.randint(0,9)
            player.append(player_third)
            p_score = sum(player) % 10
        if b_score <= 2:
            banker.append(random.randint(0,9))
        elif b_score == 3 and player_third != 8:
            banker.append(random.randint(0,9))
        elif b_score == 4 and player_third in range(2,8):
            banker.append(random.randint(0,9))
        elif b_score == 5 and player_third in range(4,8):
            banker.append(random.randint(0,9))
        elif b_score == 6 and player_third in [6,7]:
            banker.append(random.randint(0,9))
        b_score = sum(banker) % 10
        if p_score > b_score:
            result = "闲"
        elif b_score > p_score:
            result = "庄"
        else:
            result = "和"
        text = (
            f"闲家手牌：{player} 点数={p_score}\n"
            f"庄家手牌：{banker} 点数={b_score}\n"
            f"本局结果：{result}"
        )
        messagebox.showinfo("发牌结果", text)
        # 结算
        if result == "和":
            self.last_win = self.bets["和"] * 8
        else:
            self.last_win = self.bets[result] * 2
        self.balance += self.last_win
        self.lbl_last.config(text=f"上局胜利: {self.last_win:,.2f}")
        # 重置并重新开始下注
        self.reset_for_next()
        self.start_betting()

    def reset_for_next(self):
        self.current_chip = 0
        self.bets = {k: 0 for k in self.bets}
        self._update_buttons()

if __name__ == "__main__":
    root = tk.Tk()
    app = TigerBaccaratGUI(root)
    root.mainloop()
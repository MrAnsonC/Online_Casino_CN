import random
import tkinter as tk
from tkinter import messagebox


class ClassicTopDollarSlotMachine:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Top Dollar Slot Machine")
        self.root.resizable(False, False)
        self.root.configure(bg="#101010")

        # Window sizing
        self.root.geometry("920x680")
        self.root.minsize(920, 680)

        # ---- Game state ----
        self.starting_credits = 1000
        self.credits = self.starting_credits

        self.bet = 1
        self.min_bet = 1
        self.max_bet = 3  # classic feel: small bet range
        self.max_bet_required = 3

        self.spinning = False
        self.in_bonus = False
        self.bonus_locked = False
        self.bonus_round = 0
        self.bonus_offer = 0
        self.bonus_offers = []

        # ---- Classic symbol set ----
        self.symbols = ["7", "BAR", "BAR", "2BAR", "3BAR", "DD", "DD", "TOP"]

        # Reel strips: intentionally weighted and slightly different per reel
        self.reel_strips = [
            ["BAR", "7", "2BAR", "BAR", "DD", "BAR", "3BAR", "BAR", "TOP", "7", "BAR", "DD", "BAR", "2BAR"],
            ["7", "BAR", "2BAR", "BAR", "DD", "BAR", "TOP", "3BAR", "BAR", "DD", "7", "BAR", "2BAR", "BAR"],
            ["BAR", "2BAR", "BAR", "7", "DD", "BAR", "3BAR", "BAR", "TOP", "BAR", "7", "DD", "BAR", "2BAR"],
        ]

        # Paytable: net wins per unit bet
        self.paytable = {
            ("7", "7", "7"): 20,
            ("3BAR", "3BAR", "3BAR"): 15,
            ("2BAR", "2BAR", "2BAR"): 10,
            ("BAR", "BAR", "BAR"): 5,
            ("DD", "DD", "DD"): 25,
        }

        # Bonus offers are percentages / multipliers of the current bet.
        # The original feel is progressive offers with the last one mandatory.
        self.bonus_multiplier_table = [18, 28, 45, 80]

        self._build_ui()
        self._refresh_all()

    # ---------------- UI ----------------
    def _build_ui(self):
        header = tk.Frame(self.root, bg="#101010")
        header.pack(fill="x", pady=(16, 6))

        tk.Label(
            header,
            text="TOP DOLLAR",
            font=("Arial", 24, "bold"),
            fg="#f2c94c",
            bg="#101010"
        ).pack()

        tk.Label(
            header,
            text="Classic 3-Reel / Center Payline / Bonus Offer Game",
            font=("Arial", 10),
            fg="#d8d8d8",
            bg="#101010"
        ).pack(pady=(4, 0))

        body = tk.Frame(self.root, bg="#101010")
        body.pack(fill="both", expand=True, padx=16, pady=8)

        left = tk.Frame(body, bg="#171717", bd=2, relief="ridge")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right = tk.Frame(body, bg="#171717", bd=2, relief="ridge", width=280)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        # Reels panel
        reel_outer = tk.Frame(left, bg="#171717")
        reel_outer.pack(pady=(22, 10))

        self.reel_frames = []
        self.reel_labels = []

        for i in range(3):
            frame = tk.Frame(reel_outer, bg="#2a2a2a", bd=4, relief="sunken")
            frame.pack(side="left", padx=8)
            self.reel_frames.append(frame)

            label = tk.Label(
                frame,
                text="7",
                width=7,
                height=3,
                font=("Courier New", 24, "bold"),
                fg="#ffffff",
                bg="#2a2a2a"
            )
            label.pack(padx=10, pady=10)
            self.reel_labels.append(label)

        self.payline_bar = tk.Frame(left, bg="#f2c94c", height=4)
        self.payline_bar.pack(fill="x", padx=85, pady=(0, 8))

        self.message_label = tk.Label(
            left,
            text="Press SPIN to play.",
            font=("Arial", 13, "bold"),
            fg="#ffffff",
            bg="#171717",
            wraplength=600,
            justify="center"
        )
        self.message_label.pack(pady=(6, 8))

        control = tk.Frame(left, bg="#171717")
        control.pack(pady=8)

        bet_row = tk.Frame(control, bg="#171717")
        bet_row.pack(pady=(0, 8))

        tk.Label(
            bet_row,
            text="Bet:",
            font=("Arial", 12, "bold"),
            fg="#e8e8e8",
            bg="#171717"
        ).pack(side="left", padx=(0, 8))

        self.bet_var = tk.IntVar(value=self.bet)
        self.bet_spin = tk.Spinbox(
            bet_row,
            from_=self.min_bet,
            to=self.max_bet,
            width=6,
            font=("Arial", 12),
            textvariable=self.bet_var,
            justify="center"
        )
        self.bet_spin.pack(side="left")

        btn_row = tk.Frame(control, bg="#171717")
        btn_row.pack(pady=10)

        self.spin_btn = tk.Button(
            btn_row,
            text="SPIN",
            width=12,
            font=("Arial", 13, "bold"),
            command=self.spin
        )
        self.spin_btn.pack(side="left", padx=6)

        self.max_btn = tk.Button(
            btn_row,
            text="MAX BET",
            width=12,
            font=("Arial", 11, "bold"),
            command=self.max_bet
        )
        self.max_btn.pack(side="left", padx=6)

        self.clear_btn = tk.Button(
            btn_row,
            text="CLEAR",
            width=12,
            font=("Arial", 11, "bold"),
            command=self.clear_game
        )
        self.clear_btn.pack(side="left", padx=6)

        self.new_btn = tk.Button(
            btn_row,
            text="NEW GAME",
            width=12,
            font=("Arial", 11, "bold"),
            command=self.new_game
        )
        self.new_btn.pack(side="left", padx=6)

        # Right info panel
        tk.Label(
            right,
            text="GAME INFO",
            font=("Arial", 16, "bold"),
            fg="#f2c94c",
            bg="#171717"
        ).pack(pady=(16, 10))

        self.credit_label = tk.Label(
            right,
            text="Credits: 0",
            font=("Arial", 13, "bold"),
            fg="#ffffff",
            bg="#171717",
            anchor="w"
        )
        self.credit_label.pack(fill="x", padx=16, pady=6)

        self.bet_label = tk.Label(
            right,
            text="Bet: 0",
            font=("Arial", 13, "bold"),
            fg="#ffffff",
            bg="#171717",
            anchor="w"
        )
        self.bet_label.pack(fill="x", padx=16, pady=6)

        self.status_label = tk.Label(
            right,
            text="Status: Idle",
            font=("Arial", 11),
            fg="#dcdcdc",
            bg="#171717",
            wraplength=250,
            justify="left",
            anchor="nw"
        )
        self.status_label.pack(fill="x", padx=16, pady=(10, 8))

        pay_frame = tk.LabelFrame(
            right,
            text="Base Paytable",
            font=("Arial", 10, "bold"),
            fg="#f2c94c",
            bg="#171717",
            bd=2,
            relief="groove"
        )
        pay_frame.pack(fill="both", padx=16, pady=10)

        pay_text = (
            "777 = 20x\n"
            "DDD = 25x\n"
            "3BAR 3BAR 3BAR = 15x\n"
            "2BAR 2BAR 2BAR = 10x\n"
            "BAR BAR BAR = 5x"
        )
        tk.Label(
            pay_frame,
            text=pay_text,
            font=("Consolas", 10),
            fg="#ffffff",
            bg="#171717",
            justify="left",
            anchor="w"
        ).pack(fill="both", padx=10, pady=10)

        bonus_frame = tk.LabelFrame(
            right,
            text="Top Dollar Bonus",
            font=("Arial", 10, "bold"),
            fg="#f2c94c",
            bg="#171717",
            bd=2,
            relief="groove"
        )
        bonus_frame.pack(fill="both", padx=16, pady=10)

        self.bonus_label = tk.Label(
            bonus_frame,
            text=(
                "Land TOP on the middle reel\n"
                "with MAX BET to trigger bonus.\n\n"
                "Progressive offers appear.\n"
                "Take Offer or Try Again.\n"
                "Last offer must be taken."
            ),
            font=("Arial", 10),
            fg="#ffffff",
            bg="#171717",
            justify="left",
            wraplength=245
        )
        self.bonus_label.pack(fill="both", padx=10, pady=10)

        self.offer_label = tk.Label(
            right,
            text="",
            font=("Arial", 11, "bold"),
            fg="#ffffff",
            bg="#171717",
            justify="left",
            wraplength=245
        )
        self.offer_label.pack(fill="x", padx=16, pady=(0, 8))

        bonus_btn_row = tk.Frame(right, bg="#171717")
        bonus_btn_row.pack(fill="x", padx=16, pady=(0, 12))

        self.take_btn = tk.Button(
            bonus_btn_row,
            text="Take Offer",
            font=("Arial", 11, "bold"),
            state="disabled",
            command=self.take_offer
        )
        self.take_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.try_btn = tk.Button(
            bonus_btn_row,
            text="Try Again",
            font=("Arial", 11, "bold"),
            state="disabled",
            command=self.try_again
        )
        self.try_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self._show_idle_reels()

    # ---------------- Game flow ----------------
    def _refresh_all(self):
        self.credit_label.config(text=f"Credits: {self.credits:,}")
        self.bet_label.config(text=f"Bet: {self.bet}")
        self.bet_var.set(self.bet)
        self._refresh_bonus_ui()

    def _refresh_bonus_ui(self):
        if self.in_bonus:
            self.take_btn.config(state="normal")
            self.try_btn.config(state="normal" if not self.bonus_locked else "disabled")
            self.status_label.config(
                text=(
                    f"Status: BONUS ROUND\n"
                    f"Offer: {self.bonus_round + 1} / 4\n"
                    f"Current offer: ${self.bonus_offer:,}"
                )
            )
            self.offer_label.config(text=f"Offer Value: ${self.bonus_offer:,}")
        else:
            self.take_btn.config(state="disabled")
            self.try_btn.config(state="disabled")
            self.status_label.config(text="Status: Idle")
            self.offer_label.config(text="")

    def _show_idle_reels(self):
        idle = ["BAR", "7", "BAR"]
        for idx, sym in enumerate(idle):
            self.reel_labels[idx].config(text=sym)

    def max_bet(self):
        self.bet = self.max_bet
        self.bet_var.set(self.bet)
        self.message_label.config(text=f"Max bet set to {self.bet}.")
        self._refresh_all()

    def clear_game(self):
        self.credits = self.starting_credits
        self.bet = 1
        self.in_bonus = False
        self.bonus_locked = False
        self.bonus_round = 0
        self.bonus_offer = 0
        self.spinning = False
        self._show_idle_reels()
        self.message_label.config(text="Game cleared.")
        self._refresh_all()

    def new_game(self):
        self.clear_game()
        self.message_label.config(text="New game started.")

    def spin(self):
        if self.spinning or self.in_bonus:
            return

        try:
            self.bet = int(self.bet_var.get())
        except Exception:
            self.bet = 1

        self.bet = max(self.min_bet, min(self.max_bet, self.bet))
        self.bet_var.set(self.bet)

        if self.bet > self.credits:
            messagebox.showwarning("Not enough credits", "Insufficient credits for this bet.")
            return

        self.credits -= self.bet
        self.spinning = True
        self.spin_btn.config(state="disabled")
        self.max_btn.config(state="disabled")
        self.clear_btn.config(state="disabled")
        self.new_btn.config(state="disabled")
        self.bet_spin.config(state="disabled")

        self.message_label.config(text="Spinning...")
        self._refresh_all()

        # Pre-determine the final result, then animate toward it.
        final_result = self._generate_result()
        self.final_result = final_result

        # Separate spin lengths for the three reels to mimic mechanical stop order.
        self.spin_ticks = [0, 0, 0]
        self.stop_after = [18, 26, 34]
        self.reel_animation_indices = [random.randrange(len(strip)) for strip in self.reel_strips]

        self._animate_reels()

    def _generate_result(self):
        # 1 in 35 chance to hit a bonus-capable arrangement when max betting.
        if self.bet == self.max_bet_required and random.random() < 0.028:
            left = random.choice(["BAR", "7", "2BAR", "3BAR", "DD"])
            middle = "TOP"
            right = random.choice(["BAR", "7", "2BAR", "3BAR", "DD"])
            return [left, middle, right]

        # Normal reel stop result from strips
        return [
            random.choice(self.reel_strips[0]),
            random.choice(self.reel_strips[1]),
            random.choice(self.reel_strips[2]),
        ]

    def _animate_reels(self):
        if not self.spinning:
            return

        all_stopped = True
        for i in range(3):
            if self.spin_ticks[i] < self.stop_after[i]:
                all_stopped = False
                self.spin_ticks[i] += 1
                self.reel_animation_indices[i] = (self.reel_animation_indices[i] + 1) % len(self.reel_strips[i])
                self.reel_labels[i].config(text=self.reel_strips[i][self.reel_animation_indices[i]])

                # Slightly vary animation speed per reel.
                if self.stop_after[i] - self.spin_ticks[i] > 6:
                    pass

        if all_stopped:
            self._finish_spin()
            return

        # Faster animation at start, slower at end.
        delay = 55
        max_ticks_left = max(self.stop_after[i] - self.spin_ticks[i] for i in range(3))
        if max_ticks_left <= 8:
            delay = 95
        elif max_ticks_left <= 15:
            delay = 75

        self.root.after(delay, self._animate_reels)

    def _finish_spin(self):
        self.spinning = False
        for i in range(3):
            self.reel_labels[i].config(text=self.final_result[i])

        left, middle, right = self.final_result

        # Bonus trigger: max bet + Top Dollar on the center reel.
        if self.bet == self.max_bet_required and middle == "TOP":
            self.message_label.config(text="TOP DOLLAR! Bonus round triggered.")
            self._start_bonus_round()
            self._restore_buttons()
            self._refresh_all()
            return

        win_units = self._evaluate_payline(self.final_result)
        win_amount = win_units * self.bet

        if win_amount > 0:
            self.credits += win_amount
            self.message_label.config(text=f"You won ${win_amount:,} on {left}-{middle}-{right}.")
        else:
            self.message_label.config(text=f"No win. Result: {left}-{middle}-{right}.")

        self._restore_buttons()
        self._refresh_all()

    def _evaluate_payline(self, result):
        combo = tuple(result)
        if combo in self.paytable:
            return self.paytable[combo]
        return 0

    def _restore_buttons(self):
        self.spin_btn.config(state="normal")
        self.max_btn.config(state="normal")
        self.clear_btn.config(state="normal")
        self.new_btn.config(state="normal")
        self.bet_spin.config(state="normal")

    # ---------------- Bonus round ----------------
    def _start_bonus_round(self):
        self.in_bonus = True
        self.bonus_locked = False
        self.bonus_round = 0
        self.bonus_offer = self._make_bonus_offer(0)
        self._refresh_bonus_ui()

    def _make_bonus_offer(self, round_index: int) -> int:
        base = self.bet * self.bonus_multiplier_table[round_index]
        # Keep offers lively without making them too random.
        swing = random.randint(-2, 4) * self.bet
        return max(self.bet, base + swing)

    def take_offer(self):
        if not self.in_bonus:
            return
        self.credits += self.bonus_offer
        self.message_label.config(text=f"Bonus taken: ${self.bonus_offer:,}.")
        self._end_bonus_round()
        self._refresh_all()

    def try_again(self):
        if not self.in_bonus or self.bonus_locked:
            return

        if self.bonus_round >= 3:
            self.take_offer()
            return

        self.bonus_round += 1
        self.bonus_offer = self._make_bonus_offer(self.bonus_round)

        # Final round is mandatory in the original-style flow.
        if self.bonus_round >= 3:
            self.bonus_locked = True

        self.message_label.config(
            text=f"Bonus offer #{self.bonus_round + 1}: ${self.bonus_offer:,}."
        )
        self._refresh_bonus_ui()

    def _end_bonus_round(self):
        self.in_bonus = False
        self.bonus_locked = False
        self.bonus_round = 0
        self.bonus_offer = 0
        self.offer_label.config(text="")
        self._refresh_bonus_ui()


if __name__ == "__main__":
    root = tk.Tk()
    app = ClassicTopDollarSlotMachine(root)
    root.mainloop()

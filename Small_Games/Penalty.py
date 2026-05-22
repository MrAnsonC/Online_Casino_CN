import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import random
import math

# ---------------------------- 数据持久化 ----------------------------
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")

def save_user_data(users):
    with open(get_data_file_path(), "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    with open(get_data_file_path(), "r", encoding="utf-8") as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    try:
        users = load_user_data()
    except FileNotFoundError:
        return
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{new_balance:.2f}"
            break
    save_user_data(users)

# ---------------------------- 绘图辅助 ----------------------------
def lerp(a, b, t):
    return a + (b - a) * t

def ease_in_out_cubic(t):
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2

def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def point_in_circle(px, py, cx, cy, r):
    return (px - cx) ** 2 + (py - cy) ** 2 <= r ** 2

# ---------------------------- 球门绘制 ----------------------------
def draw_soccer_net(canvas, left=60, right=460, top=50, bottom=300):
    """绘制3D足球门网"""
    canvas.delete("soccer_net")
    flt = (60, 75, 40); frt = (196, 75, 40); flb = (60, 176, 40); frb = (196, 176, 40)
    blt = (40, 55, 0); brt = (216, 55, 0); blb = (40, 156, 0); brb = (216, 156, 0)

    def orig_tp(p):
        return (p[0], -p[1] + 200)

    orig_x_min, orig_x_max = 40, 216
    orig_y_min, orig_y_max = 24, 145

    def map_point(p):
        ox, oy = orig_tp(p)
        nx = left + (ox - orig_x_min) / (orig_x_max - orig_x_min) * (right - left)
        ny = top + (oy - orig_y_min) / (orig_y_max - orig_y_min) * (bottom - top)
        return (nx, ny)

    def draw_line(p1, p2, **kw):
        x1, y1 = map_point(p1)
        x2, y2 = map_point(p2)
        canvas.create_line(x1, y1, x2, y2, tags="soccer_net", **kw)

    edges = [
        (flt, frt), (flt, flb), (frt, frb), (flb, frb),
        (flt, blt), (frt, brt), (flb, blb), (frb, brb),
        (blb, brb), (blt, blb), (brt, brb)
    ]
    for e in edges:
        draw_line(e[0], e[1], fill="white", width=3)

    def grid(p1, p2, p3, p4, cols, rows):
        for i in range(1, cols):
            t = i / cols
            a = (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t, p1[2] + (p2[2] - p1[2]) * t)
            b = (p4[0] + (p3[0] - p4[0]) * t, p4[1] + (p3[1] - p4[1]) * t, p4[2] + (p3[2] - p4[2]) * t)
            draw_line(a, b, fill="#c8ffd0", width=1)
        for i in range(1, rows):
            t = i / rows
            a = (p1[0] + (p4[0] - p1[0]) * t, p1[1] + (p4[1] - p1[1]) * t, p1[2] + (p4[2] - p1[2]) * t)
            b = (p2[0] + (p3[0] - p2[0]) * t, p2[1] + (p3[1] - p2[1]) * t, p2[2] + (p3[2] - p2[2]) * t)
            draw_line(a, b, fill="#c8ffd0", width=1)

    grid(flt, frt, frb, flb, 18, 10)
    grid(flt, blt, blb, flb, 6, 10)
    grid(brt, frt, frb, brb, 6, 10)
    grid(flb, frb, brb, blb, 18, 6)
    canvas.tag_lower("soccer_net")

# ---------------------------- 主游戏类 ----------------------------
class PenaltyGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("点球大战")
        self.root.geometry("1000x750+50+10")
        self.root.resizable(0, 0)
        self.root.configure(bg="#16213e")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.pending_bet = 0.0
        self.last_win = 0.0
        self.animation_running = False

        # 龙门有效区域 (基于draw_soccer_net的范围)
        self.net_left = 60
        self.net_right = 460
        self.net_top = 50
        self.net_bottom = 300

        self.create_widgets()
        self.update_display()

        self.draw_goalkeeper()
        self.goalkeeper_reset_pose()

    # ---------------------------- UI 构建 ----------------------------
    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg="#16213e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        left_frame = tk.Frame(main_frame, bg="#2e7d32", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        tk.Label(left_frame, text="点球大战", font=("Arial", 20, "bold"),
                 bg="#2e7d32", fg="#ffffff").pack(pady=10)

        self.goal_canvas = tk.Canvas(left_frame, width=500, height=500,
                                     bg="#2e7d32", bd=0, highlightthickness=0)
        self.goal_canvas.pack(pady=10, padx=10)
        draw_soccer_net(self.goal_canvas, left=60, right=460, top=50, bottom=300)

        self.goal_canvas.create_line(0, 300, 540, 300, fill="white", width=2, tags="ground_line")

        # 绑定点击事件（射门）
        self.goal_canvas.bind("<Button-1>", self.on_goal_canvas_click)

        self.draw_football()

        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        balance_frame = tk.Frame(right_frame, bg="#16213e")
        balance_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(balance_frame, text="余额:", font=("Arial", 14),
                 bg="#16213e", fg="#ffffff").pack(side=tk.LEFT)
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        tk.Label(balance_frame, textvariable=self.balance_var, font=("Arial", 14, "bold"),
                 bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=5)

        chips_frame = tk.Frame(right_frame, bg="#16213e")
        chips_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        chips = [
            ("$5", "#ff0000", "white"),
            ("$25", "#00ff00", "black"),
            ("$100", "#000000", "white"),
            ("$500", "#FF7DDA", "black"),
            ("$1K", "#ffffff", "black"),
        ]
        self.chip_buttons = []
        for text, bg, fg in chips:
            btn = self.create_circle_button(
                chips_frame, text=text, bg_color=bg, fg_color=fg,
                command=lambda t=text: self.add_chip(t[1:])
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)

        bet_frame = tk.Frame(right_frame, bg="#16213e")
        bet_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12),
                 bg="#16213e", fg="#ffffff").pack(anchor=tk.W)
        self.bet_var = tk.StringVar(value="$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"),
                 bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=5)

        win_frame = tk.Frame(right_frame, bg="#16213e")
        win_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12),
                 bg="#16213e", fg="#ffffff").pack(anchor=tk.W)
        self.last_win_var = tk.StringVar(value="$0.00")
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"),
                 bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=5)

        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        self.play_button = tk.Button(button_frame, text="开始点球", font=("Arial", 12, "bold"),
                                     bg="#27ae60", fg="white", width=12, command=self.play_game)
        self.play_button.pack(pady=5)
        self.reset_bet_button = tk.Button(button_frame, text="重设下注金额", font=("Arial", 12),
                                          bg="#3498db", fg="white", width=12, command=self.reset_bet)
        self.reset_bet_button.pack(pady=5)

        rules_frame = tk.Frame(right_frame, bg="#16213e")
        rules_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(rules_frame, text="游戏规则:", font=("Arial", 12, "bold"),
                 bg="#16213e", fg="#ffffff").pack(anchor=tk.W, pady=(0, 5))
        for rule in [
            "1. 选择下注金额",
            "2. 点击'开始点球'",
            "3. 点击龙门内任意位置射门",
            "4. 守门员会随机移动并做出扑救动作",
            "5. 球碰到守门员任何部位 = 不进",
            "6. 球飞入球门 = 进球赢",
        ]:
            tk.Label(rules_frame, text=rule, font=("Arial", 10),
                     bg="#16213e", fg="#c8e6c9", justify=tk.LEFT).pack(anchor=tk.W, pady=2)

    def create_circle_button(self, parent, text, bg_color, fg_color, command=None, radius=30):
        canvas = tk.Canvas(parent, width=radius * 2, height=radius * 2,
                           highlightthickness=0, bg="#16213e")
        canvas.create_oval(0, 0, radius * 2, radius * 2, fill=bg_color, outline="#16213e", width=2)
        canvas.create_text(radius, radius, text=text, fill=fg_color, font=("Arial", 12, "bold"))
        canvas.bind("<Button-1>", lambda e: command() if command else None)
        return canvas

    def draw_football(self):
        left, right = 60, 460
        bottom = 350
        self.ball_start_pos = ((left + right) / 2, bottom + 100)
        cx, cy = self.ball_start_pos
        r = 40
        self.goal_canvas.delete("football")
        self.goal_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="white", outline="black", width=2, tags="football")
        self.goal_canvas.create_line(cx - r, cy, cx + r, cy, fill="black", width=2, tags="football")
        self.goal_canvas.create_line(cx, cy - r, cx, cy + r, fill="black", width=2, tags="football")
        self.goal_canvas.create_line(cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7,
                                     fill="black", width=2, tags="football")
        self.goal_canvas.create_line(cx - r * 0.7, cy + r * 0.7, cx + r * 0.7, cy - r * 0.7,
                                     fill="black", width=2, tags="football")

    # ---------------------------- 守门员绘制 ----------------------------
    def draw_goalkeeper(self):
        self.gk_items = {}

        self.gk_items["shadow"] = self.goal_canvas.create_oval(
            0, 0, 0, 0, fill="#0a0a0a", outline="", stipple="gray50", tags="goalkeeper"
        )
        self.gk_items["body"] = self.goal_canvas.create_oval(
            0, 0, 0, 0, fill="#1e88e5", outline="white", width=2, tags="goalkeeper"
        )
        self.gk_items["shorts"] = self.goal_canvas.create_oval(
            0, 0, 0, 0, fill="#0d47a1", outline="white", width=1, tags="goalkeeper"
        )
        self.gk_items["head"] = self.goal_canvas.create_oval(
            0, 0, 0, 0, fill="#ffcc80", outline="#5d4037", width=2, tags="goalkeeper"
        )
        self.gk_items["hair"] = self.goal_canvas.create_arc(
            0, 0, 0, 0, start=0, extent=180, style=tk.PIESLICE,
            fill="#3e2723", outline="#3e2723", tags="goalkeeper"
        )
        self.gk_items["left_eye"] = self.goal_canvas.create_oval(0, 0, 0, 0, fill="black", outline="", tags="goalkeeper")
        self.gk_items["right_eye"] = self.goal_canvas.create_oval(0, 0, 0, 0, fill="black", outline="", tags="goalkeeper")
        self.gk_items["mouth"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#6d4c41", width=2, tags="goalkeeper")

        self.gk_items["left_upper_arm"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1976d2", width=9, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["left_lower_arm"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1976d2", width=8, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["right_upper_arm"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1976d2", width=9, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["right_lower_arm"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1976d2", width=8, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["left_glove"] = self.goal_canvas.create_oval(0, 0, 0, 0, fill="#ffd966", outline="#7f6000", width=2, tags="goalkeeper")
        self.gk_items["right_glove"] = self.goal_canvas.create_oval(0, 0, 0, 0, fill="#ffd966", outline="#7f6000", width=2, tags="goalkeeper")

        self.gk_items["left_upper_leg"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1565c0", width=10, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["left_lower_leg"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1565c0", width=9, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["right_upper_leg"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1565c0", width=10, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["right_lower_leg"] = self.goal_canvas.create_line(0, 0, 0, 0, fill="#1565c0", width=9, capstyle=tk.ROUND, tags="goalkeeper")
        self.gk_items["left_shoe"] = self.goal_canvas.create_oval(0, 0, 0, 0, fill="#263238", outline="white", width=1, tags="goalkeeper")
        self.gk_items["right_shoe"] = self.goal_canvas.create_oval(0, 0, 0, 0, fill="#263238", outline="white", width=1, tags="goalkeeper")

    def goalkeeper_reset_pose(self):
        self.gk_center_x = 260
        self.gk_center_y = 290
        self.gk_pose = self.make_pose(
            self.gk_center_x, self.gk_center_y,
            lean=0.0, crouch=0.15, arm_open=0.25, reach_x=0.0, reach_y=0.0, leg_spread=0.18, dive=0.0
        )
        self.update_goalkeeper_pose(self.gk_pose)
        self._enforce_floor()

    def make_pose(self, cx, cy, lean=0.0, crouch=0.0, arm_open=0.0,
                  reach_x=0.0, reach_y=0.0, leg_spread=0.0, dive=0.0,
                  twist=0.0, stretch=0.0):
        return {
            "cx": cx,
            "cy": cy,
            "lean": lean,
            "crouch": crouch,
            "arm_open": arm_open,
            "reach_x": reach_x,
            "reach_y": reach_y,
            "leg_spread": leg_spread,
            "dive": dive,
            "twist": twist,
            "stretch": stretch,
        }

    def _joint(self, start, angle_deg, length):
        rad = math.radians(angle_deg)
        return (start[0] + math.cos(rad) * length, start[1] + math.sin(rad) * length)

    def _draw_limb(self, upper_item, lower_item, shoe_item, start, upper_angle, upper_len, lower_angle, lower_len, shoe_r=7):
        knee = self._joint(start, upper_angle, upper_len)
        foot = self._joint(knee, lower_angle, lower_len)
        self.goal_canvas.coords(upper_item, start[0], start[1], knee[0], knee[1])
        self.goal_canvas.coords(lower_item, knee[0], knee[1], foot[0], foot[1])
        self.goal_canvas.coords(shoe_item, foot[0] - shoe_r, foot[1] - shoe_r, foot[0] + shoe_r, foot[1] + shoe_r)
        return knee, foot

    def update_goalkeeper_pose(self, pose):
        """更自然、丝滑、分层明确的守门员姿态。"""
        cx = pose["cx"]
        cy = pose["cy"]
        lean = pose["lean"]
        crouch = pose["crouch"]
        arm_open = pose["arm_open"]
        reach_x = pose["reach_x"]
        reach_y = pose["reach_y"]
        leg_spread = pose["leg_spread"]
        dive = pose["dive"]
        twist = pose.get("twist", 0.0)
        stretch = pose.get("stretch", 0.0)

        shoulder_x = cx + lean * 18 + reach_x * 6
        shoulder_y = cy - 44 + crouch * 10 - dive * 10 + reach_y * 6
        hip_x = cx - lean * 10 + reach_x * 3
        hip_y = cy + 6 + crouch * 14 + dive * 8 + reach_y * 2

        shadow_w = 96 + stretch * 18 - dive * 18
        shadow_h = 18 - dive * 8 + stretch * 2
        self.goal_canvas.coords(
            self.gk_items["shadow"],
            cx - shadow_w / 2, cy + 60,
            cx + shadow_w / 2, cy + 60 + shadow_h
        )

        body_w = 52 + abs(lean) * 8 + stretch * 4
        body_h = 62 + dive * 12 + stretch * 10
        self.goal_canvas.coords(
            self.gk_items["body"],
            shoulder_x - body_w / 2, shoulder_y - 4,
            shoulder_x + body_w / 2, shoulder_y + body_h
        )
        self.goal_canvas.coords(
            self.gk_items["shorts"],
            hip_x - 26, hip_y,
            hip_x + 26, hip_y + 32 + crouch * 4
        )

        head_x = cx + lean * 14 + reach_x * 4 - dive * 4
        head_y = cy - 70 + crouch * 6 - dive * 8 + reach_y * 3
        self.goal_canvas.coords(
            self.gk_items["head"],
            head_x - 20, head_y - 20,
            head_x + 20, head_y + 20
        )
        self.goal_canvas.coords(
            self.gk_items["hair"],
            head_x - 20, head_y - 22,
            head_x + 20, head_y + 4
        )
        self.goal_canvas.coords(
            self.gk_items["left_eye"],
            head_x - 9, head_y - 5,
            head_x - 4, head_y - 1
        )
        self.goal_canvas.coords(
            self.gk_items["right_eye"],
            head_x + 4, head_y - 5,
            head_x + 9, head_y - 1
        )
        self.goal_canvas.coords(
            self.gk_items["mouth"],
            head_x - 7, head_y + 11,
            head_x + 7, head_y + 11
        )

        ls = (shoulder_x - 24, shoulder_y + 2)
        rs = (shoulder_x + 24, shoulder_y + 2)
        lh = (hip_x - 18, hip_y + 2)
        rh = (hip_x + 18, hip_y + 2)

        # reach_y < 0 时，手臂向上抬；高位封堵会非常明显
        left_upper_angle = 205 - arm_open * 72 - reach_x * 40 + reach_y * 80 - twist * 14 - dive * 12
        left_lower_angle = 168 - arm_open * 30 - reach_x * 28 + reach_y * 45 - twist * 8 - dive * 8
        right_upper_angle = 335 + arm_open * 72 + reach_x * 40 - reach_y * 80 + twist * 14 + dive * 12
        right_lower_angle = 12 + arm_open * 30 + reach_x * 28 - reach_y * 45 + twist * 8 + dive * 8

        if reach_x < -0.25:
            left_upper_angle -= 28
            left_lower_angle -= 30
            right_upper_angle += 10
            right_lower_angle += 8
        elif reach_x > 0.25:
            right_upper_angle += 28
            right_lower_angle += 30
            left_upper_angle -= 10
            left_lower_angle -= 8

        upper_arm_len = 36 + arm_open * 12 + stretch * 2
        lower_arm_len = 32 + arm_open * 10 + stretch * 2

        self._draw_limb(
            self.gk_items["left_upper_arm"], self.gk_items["left_lower_arm"], self.gk_items["left_glove"],
            ls, left_upper_angle, upper_arm_len, left_lower_angle, lower_arm_len, shoe_r=11
        )
        self._draw_limb(
            self.gk_items["right_upper_arm"], self.gk_items["right_lower_arm"], self.gk_items["right_glove"],
            rs, right_upper_angle, upper_arm_len, right_lower_angle, lower_arm_len, shoe_r=11
        )

        left_upper_leg_angle = 106 + leg_spread * 38 + lean * 16 + dive * 54
        left_lower_leg_angle = 100 + leg_spread * 22 + lean * 12 + dive * 30
        right_upper_leg_angle = 74 - leg_spread * 38 + lean * 16 - dive * 54
        right_lower_leg_angle = 80 - leg_spread * 22 + lean * 12 - dive * 30

        if abs(reach_x) > 0.25:
            move_dir = -1 if reach_x < 0 else 1
            hip_shift = move_dir * 10
            lh = (lh[0] + hip_shift, lh[1])
            rh = (rh[0] + hip_shift, rh[1])

        leg_upper_len = 42
        leg_lower_len = 38
        self._draw_limb(
            self.gk_items["left_upper_leg"], self.gk_items["left_lower_leg"], self.gk_items["left_shoe"],
            lh, left_upper_leg_angle, leg_upper_len, left_lower_leg_angle, leg_lower_len, shoe_r=10
        )
        self._draw_limb(
            self.gk_items["right_upper_leg"], self.gk_items["right_lower_leg"], self.gk_items["right_shoe"],
            rh, right_upper_leg_angle, leg_upper_len, right_lower_leg_angle, leg_lower_len, shoe_r=10
        )

        self._enforce_floor()

    def _play_gk_sequence(self, sequence, on_complete=None, delay=28):
        """
        通用关键帧播放器。
        sequence 格式:
            [
                (pose1, frames1, easing1),
                (pose2, frames2, easing2),
                ...
            ]
        """
        if not sequence:
            if on_complete:
                on_complete()
            return

        start_pose = dict(self.gk_pose)
        poses = [start_pose] + [item[0] for item in sequence]
        frames_list = [max(1, int(item[1])) for item in sequence]
        easings = [item[2] if len(item) > 2 and item[2] else ease_in_out_cubic for item in sequence]

        seg = 0
        frame = 0

        def step():
            nonlocal seg, frame

            if seg >= len(frames_list):
                if on_complete:
                    on_complete()
                return

            total = frames_list[seg]
            t = clamp(frame / total, 0.0, 1.0)
            t = easings[seg](t)

            a = poses[seg]
            b = poses[seg + 1]

            pose = self.make_pose(
                lerp(a["cx"], b["cx"], t),
                lerp(a["cy"], b["cy"], t),
                lean=lerp(a["lean"], b["lean"], t),
                crouch=lerp(a["crouch"], b["crouch"], t),
                arm_open=lerp(a["arm_open"], b["arm_open"], t),
                reach_x=lerp(a["reach_x"], b["reach_x"], t),
                reach_y=lerp(a["reach_y"], b["reach_y"], t),
                leg_spread=lerp(a["leg_spread"], b["leg_spread"], t),
                dive=lerp(a["dive"], b["dive"], t),
                twist=lerp(a.get("twist", 0.0), b.get("twist", 0.0), t),
                stretch=lerp(a.get("stretch", 0.0), b.get("stretch", 0.0), t),
            )

            self.gk_pose = pose
            self.update_goalkeeper_pose(pose)

            frame += 1
            if frame > total:
                seg += 1
                frame = 0

            self.root.after(delay, step)

        step()

    def _enforce_floor(self):
        """将守门员整体向上移动，使脚底不高于地面线300"""
        floor_y = 300
        max_y = -1e9
        for item in self.gk_items.values():
            bbox = self.goal_canvas.bbox(item)
            if bbox:
                max_y = max(max_y, bbox[3])
        if max_y > floor_y:
            dy = max_y - floor_y
            for item in self.gk_items.values():
                self.goal_canvas.move(item, 0, -dy)
            self.gk_pose["cy"] -= dy

    def _get_glove_positions(self):
        """返回左右手中心点 + 半径"""
        result = []

        for key in ["left_glove", "right_glove"]:
            bbox = self.goal_canvas.bbox(self.gk_items[key])
            if bbox:
                x = (bbox[0] + bbox[2]) / 2
                y = (bbox[1] + bbox[3]) / 2
                r = (bbox[2] - bbox[0]) / 2
                result.append((x, y, r))

        return result

    def check_ball_collision(self, ball_x, ball_y, ball_r):
        """
        返回:
        - None: 未碰撞
        - "catch": 被手接住
        - "block": 被身体挡住
        """

        # 1️⃣ 手套检测（优先级最高）
        for gx, gy, gr in self._get_glove_positions():
            dist_sq = (ball_x - gx) ** 2 + (ball_y - gy) ** 2
            if dist_sq <= (ball_r + gr * 0.9) ** 2:
                return "catch", (gx, gy)

        # 2️⃣ 身体检测
        body_bbox = self.goal_canvas.bbox(self.gk_items["body"])
        if body_bbox:
            if (body_bbox[0] <= ball_x <= body_bbox[2] and
                    body_bbox[1] <= ball_y <= body_bbox[3]):
                return "block", (ball_x, ball_y)

        return None, None

    # ---------------------------- 守门员动作动画（随机版） ----------------------------
    def animate_goalkeeper_random_action(self, action_type, target_gk_x, on_complete):
        """
        守门员移动到随机目标X位置并做出指定动作。
        action_type: "save_high_block", "catch_middle", "kick_foot", "dive_save", "split_save"
        target_gk_x: 守门员最终的中心X坐标（160~360之间）
        """
        start = dict(self.gk_pose)
        sx = start["cx"]
        sy = start["cy"]

        # 目标Y坐标略微根据动作变化，但基本保持原高度附近
        target_gk_y = sy
        if action_type in ("kick_foot", "split_save"):
            target_gk_y = sy + 8
        elif action_type == "dive_save":
            target_gk_y = sy + 12
        elif action_type == "save_high_block":
            target_gk_y = sy - 4

        # 判断移动方向
        side = 1 if target_gk_x > sx else -1
        move_x = target_gk_x - sx

        def P(cx, cy, lean=0.0, crouch=0.0, arm_open=0.0, reach_x=0.0, reach_y=0.0,
              leg_spread=0.0, dive=0.0, twist=0.0, stretch=0.0):
            return self.make_pose(
                cx, cy,
                lean=lean, crouch=crouch, arm_open=arm_open,
                reach_x=reach_x, reach_y=reach_y,
                leg_spread=leg_spread, dive=dive,
                twist=twist, stretch=stretch
            )

        if action_type == "save_high_block":
            seq = [
                (P(sx + move_x * 0.2, sy - 1,
                   lean=side * 0.12, crouch=0.22, arm_open=0.52,
                   reach_x=side * 0.10, reach_y=-0.20,
                   leg_spread=0.20, dive=0.00, twist=side * 0.04, stretch=0.03), 4, ease_in_out_cubic),
                (P(target_gk_x, target_gk_y - 2,
                   lean=side * 0.26, crouch=0.36, arm_open=1.46,
                   reach_x=side * 0.32, reach_y=-1.10,
                   leg_spread=0.30, dive=0.08, twist=side * 0.08, stretch=0.18), 5, ease_out_back),
                (P(target_gk_x + side * 2, target_gk_y - 1,
                   lean=side * 0.18, crouch=0.32, arm_open=1.52,
                   reach_x=side * 0.38, reach_y=-1.18,
                   leg_spread=0.28, dive=0.05, twist=side * 0.06, stretch=0.16), 4, ease_in_out_cubic),
                (P(target_gk_x, target_gk_y,
                   lean=side * 0.08, crouch=0.22, arm_open=0.58,
                   reach_x=side * 0.08, reach_y=-0.18,
                   leg_spread=0.20, dive=0.00, twist=side * 0.03, stretch=0.02), 4, ease_in_out_cubic),
            ]

        elif action_type == "catch_middle":
            seq = [
                (P(sx + move_x * 0.2, sy - 1,
                   lean=side * 0.12, crouch=0.24, arm_open=0.48,
                   reach_x=side * 0.12, reach_y=-0.10,
                   leg_spread=0.22, dive=0.00, twist=side * 0.04, stretch=0.03), 4, ease_in_out_cubic),
                (P(target_gk_x, target_gk_y,
                   lean=side * 0.32, crouch=0.34, arm_open=1.20,
                   reach_x=side * 1.00, reach_y=-0.40,
                   leg_spread=0.34, dive=0.04, twist=side * 0.10, stretch=0.08), 5, ease_out_back),
                (P(target_gk_x + side * 2, target_gk_y,
                   lean=side * 0.28, crouch=0.30, arm_open=1.28,
                   reach_x=side * 1.10, reach_y=-0.42,
                   leg_spread=0.30, dive=0.03, twist=side * 0.08, stretch=0.06), 4, ease_in_out_cubic),
                (P(target_gk_x, target_gk_y,
                   lean=side * 0.10, crouch=0.22, arm_open=0.52,
                   reach_x=side * 0.10, reach_y=-0.08,
                   leg_spread=0.20, dive=0.00, twist=side * 0.03, stretch=0.02), 4, ease_in_out_cubic),
            ]

        elif action_type == "kick_foot":
            seq = [
                (P(sx + move_x * 0.2, sy + 2,
                   lean=side * 0.08, crouch=0.40, arm_open=0.40,
                   reach_x=side * 0.06, reach_y=0.02,
                   leg_spread=0.50, dive=0.00, twist=side * 0.03, stretch=0.03), 4, ease_in_out_cubic),
                (P(target_gk_x, target_gk_y + 4,
                   lean=side * 0.30, crouch=0.92, arm_open=0.60,
                   reach_x=side * 0.42, reach_y=0.10,
                   leg_spread=1.06, dive=0.00, twist=side * 0.08, stretch=0.12), 6, ease_out_back),
                (P(target_gk_x + side * 2, target_gk_y + 6,
                   lean=side * 0.24, crouch=0.96, arm_open=0.58,
                   reach_x=side * 0.34, reach_y=0.12,
                   leg_spread=1.14, dive=0.00, twist=side * 0.06, stretch=0.10), 4, ease_in_out_cubic),
            ]

        elif action_type == "dive_save":
            seq = [
                (P(sx + move_x * 0.15, sy,
                   lean=side * 0.12, crouch=0.32, arm_open=0.42,
                   reach_x=side * 0.10, reach_y=0.00,
                   leg_spread=0.24, dive=0.05, twist=side * 0.05, stretch=0.02), 3, ease_in_out_cubic),
                (P(target_gk_x + side * 18, target_gk_y + 6,
                   lean=side * 0.72, crouch=0.50, arm_open=1.18,
                   reach_x=side * 1.02, reach_y=0.12,
                   leg_spread=0.72, dive=0.46, twist=side * 0.18, stretch=0.14), 5, ease_out_back),
                (P(target_gk_x + side * 42, target_gk_y + 12,
                   lean=side * 0.96, crouch=0.60, arm_open=1.42,
                   reach_x=side * 1.28, reach_y=0.22,
                   leg_spread=0.92, dive=0.82, twist=side * 0.24, stretch=0.20), 5, ease_out_back),
                (P(target_gk_x + side * 30, target_gk_y + 8,
                   lean=side * 0.62, crouch=0.52, arm_open=1.20,
                   reach_x=side * 1.08, reach_y=0.14,
                   leg_spread=0.76, dive=0.52, twist=side * 0.16, stretch=0.12), 3, ease_in_out_cubic),
            ]

        elif action_type == "split_save":  # 一字马扑救
            seq = [
                (P(sx + move_x * 0.2, sy + 2,
                   lean=side * 0.10, crouch=0.50, arm_open=0.60,
                   reach_x=side * 0.15, reach_y=0.05,
                   leg_spread=0.70, dive=0.10, twist=side * 0.05, stretch=0.05), 4, ease_in_out_cubic),
                (P(target_gk_x, target_gk_y + 8,
                   lean=side * 0.35, crouch=1.10, arm_open=1.30,
                   reach_x=side * 0.60, reach_y=0.20,
                   leg_spread=1.50, dive=0.20, twist=side * 0.12, stretch=0.20), 6, ease_out_back),
                (P(target_gk_x + side * 3, target_gk_y + 10,
                   lean=side * 0.30, crouch=1.05, arm_open=1.25,
                   reach_x=side * 0.55, reach_y=0.18,
                   leg_spread=1.45, dive=0.15, twist=side * 0.10, stretch=0.18), 4, ease_in_out_cubic),
                (P(target_gk_x, target_gk_y + 6,
                   lean=side * 0.20, crouch=0.90, arm_open=1.10,
                   reach_x=side * 0.40, reach_y=0.10,
                   leg_spread=1.30, dive=0.10, twist=side * 0.08, stretch=0.12), 4, ease_in_out_cubic),
            ]

        else:
            # 默认简单移动
            seq = [
                (P(target_gk_x, target_gk_y,
                   lean=0.0, crouch=0.15, arm_open=0.25,
                   reach_x=0.0, reach_y=0.0,
                   leg_spread=0.18, dive=0.0, twist=0.0, stretch=0.0), 10, ease_in_out_cubic)
            ]

        self._play_gk_sequence(seq, on_complete=on_complete)

    # ---------------------------- 足球动画 ----------------------------
    def animate_ball(self, start, control, end, start_r, end_r, frames=20,
                    callback=None, on_frame=None):
        """
        新版本：
        - 每一帧调用 on_frame(x, y, r, t)
        - 可用于实时碰撞检测
        """

        self.goal_canvas.delete("shot_ball")
        self.ball_animation_stop = False

        def update(i=0):
            if self.ball_animation_stop:
                return

            if i > frames:
                if callback:
                    callback((end[0], end[1]))
                return

            t = i / frames
            inv = 1 - t

            x = inv * inv * start[0] + 2 * inv * t * control[0] + t * t * end[0]
            y = inv * inv * start[1] + 2 * inv * t * control[1] + t * t * end[1]
            r = start_r + (end_r - start_r) * t

            # 👉 实时回调（关键）
            if on_frame:
                should_stop = on_frame(x, y, r, t)
                if should_stop:
                    self.ball_animation_stop = True
                    return

            self.goal_canvas.delete("shot_ball")
            self.goal_canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill="white", outline="black", width=2, tags="shot_ball"
            )

            self.root.after(40, update, i + 1)

        update()

    def show_ball_in_hand(self, hand_pos):
        """在守门员手部显示被抓住的球"""
        self.goal_canvas.delete("shot_ball")
        self.goal_canvas.delete("blocked_ball")
        r = 20
        x, y = hand_pos
        self.goal_canvas.create_oval(x - r, y - r, x + r, y + r, fill="white", outline="black", width=2, tags="caught_ball")
        self.goal_canvas.create_line(x - r, y, x + r, y, fill="black", width=1, tags="caught_ball")
        self.goal_canvas.create_line(x, y - r, x, y + r, fill="black", width=1, tags="caught_ball")

    def show_ball_blocked(self, ball_pos):
        """显示被封堵住的球"""
        self.goal_canvas.delete("shot_ball")
        self.goal_canvas.delete("caught_ball")
        self.goal_canvas.delete("blocked_ball")
        r = 16
        x, y = ball_pos
        self.goal_canvas.create_oval(x - r, y - r, x + r, y + r, fill="white", outline="black", width=2, tags="blocked_ball")
        self.goal_canvas.create_line(x - r, y, x + r, y, fill="black", width=1, tags="blocked_ball")
        self.goal_canvas.create_line(x, y - r, x, y + r, fill="black", width=1, tags="blocked_ball")

    # ---------------------------- 点球核心流程（修正版） ----------------------------
    def on_goal_canvas_click(self, event):
        """玩家点击龙门内任意位置射门"""
        if self.animation_running:
            return
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return

        # 检查点击位置是否在龙门有效区域内
        if not (self.net_left <= event.x <= self.net_right and self.net_top <= event.y <= self.net_bottom):
            messagebox.showwarning("无效区域", "请点击龙门网区域射门！")
            return

        # 开始点球流程
        self.animation_running = True
        self.set_buttons_state(False)

        target_pos = (event.x, event.y)  # 射门目标点

        # 扣注
        shot_bet = self.current_bet
        self.pending_bet = shot_bet
        self.balance -= shot_bet
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
        self.update_display()
        update_balance_in_json(self.username, self.balance)

        # 随机决定守门员目标X位置（范围180~340，避免出界）
        gk_target_x = random.randint(180, 340)
        # 随机选择动作类型
        action_types = ["save_high_block", "catch_middle", "kick_foot", "dive_save", "split_save"]
        action = random.choice(action_types)

        # 状态管理
        state = {
            "ball_done": False,
            "gk_done": False,
            "collision": False,
            "collision_pos": None,
            "scored": False  # 默认未进球，等碰撞检测后决定
        }

        def try_finish():
            if state["ball_done"] and state["gk_done"]:
                # 结算：如果发生了碰撞则输，否则进球赢
                if state["collision"]:
                    self.settle_shot(False, None, collision_pos=state.get("collision_pos"))
                else:
                    self.settle_shot(True, None)

        def after_gk():
            state["gk_done"] = True
            try_finish()

        def after_ball(pos=None):
            state["ball_done"] = True
            # 如果球到达终点且没有碰撞，则进球
            if not state["collision"]:
                # 显示球在网内效果（可选）
                self.goal_canvas.delete("shot_ball")
                self.goal_canvas.create_oval(
                    pos[0] - 15, pos[1] - 15, pos[0] + 15, pos[1] + 15,
                    fill="white", outline="black", width=2, tags="goal_ball"
                )
            try_finish()

        def on_ball_frame(x, y, r, t):
            # 实时碰撞检测
            result, col_pos = self.check_ball_collision(x, y, r)
            if result:
                state["collision"] = True
                state["collision_pos"] = col_pos
                state["ball_done"] = True
                # 显示碰撞效果
                if result == "catch":
                    self.show_ball_in_hand(col_pos)
                else:
                    self.show_ball_blocked(col_pos)
                try_finish()
                return True  # 停止动画
            return False

        # 准备球轨迹 - 修正为更接近直线的轨迹
        start_pos = self.ball_start_pos
        # 控制点取中点并加上轻微弧度（保证球基本沿直线飞向目标，但略有弧线增加真实感）
        ctrl_x = (start_pos[0] + target_pos[0]) / 2 + random.randint(-15, 15)
        # 弧线高度：让球稍微向上拱起，但不会偏离目标方向
        arc_height = max(20, min(80, (start_pos[1] - target_pos[1]) * 0.3))
        ctrl_y = (start_pos[1] + target_pos[1]) / 2 - random.randint(int(arc_height*0.5), int(arc_height))

        # 可选：绘制一条临时轨迹线（帮助玩家看到预期路径）
        self.goal_canvas.delete("trajectory")
        points = []
        for i in range(0, 11):
            t = i / 10
            inv = 1 - t
            x = inv * inv * start_pos[0] + 2 * inv * t * ctrl_x + t * t * target_pos[0]
            y = inv * inv * start_pos[1] + 2 * inv * t * ctrl_y + t * t * target_pos[1]
            points.extend([x, y])
        if len(points) >= 4:
            self.goal_canvas.create_line(points, fill="#ffff88", width=2, dash=(4, 4), tags="trajectory")
        # 0.5秒后擦除轨迹
        self.root.after(500, lambda: self.goal_canvas.delete("trajectory"))

        # 开始守门员动画和足球动画
        self.animate_goalkeeper_random_action(action, gk_target_x, on_complete=after_gk)
        self.animate_ball(
            start_pos,
            (ctrl_x, ctrl_y),
            target_pos,
            40,
            25,
            frames=20,
            callback=after_ball,
            on_frame=on_ball_frame
        )

    def settle_shot(self, scored, action_type=None, collision_pos=None):
        pending = self.pending_bet

        if scored:
            payout = pending * 2
            self.balance += payout
            self.last_win = payout
            messagebox.showinfo("进球啦！", f"球进了！您获得 ${payout:.2f}")
        else:
            self.last_win = 0
            messagebox.showinfo("没进", f"守门员扑出了点球！本次已扣除 ${pending:.2f}")

        self.update_display()
        update_balance_in_json(self.username, self.balance)

        self.pending_bet = 0.0
        self.goalkeeper_reset_pose()
        self.animation_running = False
        self.set_buttons_state(True)
        # 清理所有临时球体
        self.goal_canvas.delete("shot_ball")
        self.goal_canvas.delete("caught_ball")
        self.goal_canvas.delete("blocked_ball")
        self.goal_canvas.delete("goal_ball")
        self.goal_canvas.delete("trajectory")

    def set_buttons_state(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        for btn in self.chip_buttons:
            btn.config(state=state)
        self.play_button.config(state=state)
        self.reset_bet_button.config(state=state)

    def add_chip(self, amount):
        if self.animation_running:
            return
        try:
            amount_val = 1000.0 if amount == "1K" else float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
            else:
                messagebox.showwarning("余额不足", "下注金额不能超过余额")
        except Exception:
            pass

    def reset_bet(self):
        if self.animation_running:
            return
        self.current_bet = 0.0
        self.bet_var.set("$0.00")

    def play_game(self):
        if self.animation_running:
            return
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        messagebox.showinfo("点球大战", "请点击龙门网内任意位置射门！")

    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")

    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

# ---------------------------- 外部调用 ----------------------------
def main(initial_balance, username):
    root = tk.Tk()
    game = PenaltyGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = PenaltyGame(root, 1000.0, "test_user")
    root.mainloop()
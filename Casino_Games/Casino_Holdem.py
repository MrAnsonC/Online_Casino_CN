import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
import math
import secrets
import subprocess, sys
import time

# =========================================================
# 仿轮盘 UI 颜色与常量
# =========================================================
ROOT_BG = "#1B3D31"
CYAN = "#007502"
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家同花顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}

# Ante下注支付表 (修改后的赔率)
ANTE_PAYOUT = {
    9: 100,   # 皇家同花顺 100:1
    8: 49,    # 同花顺 49:1
    7: 17,    # 四条 17:1
    6: 3,     # 葫芦 3:1
    5: 2,     # 同花 2:1
    # 其他牌型都是1:1
}

# AA下注支付表 (修改后的赔率)
AA_PAYOUT = {
    9: 100,   # 皇家同花顺 100:1
    8: 50,    # 同花顺 50:1
    7: 40,    # 四条 40:1
    6: 30,    # 葫芦 30:1
    5: 20,    # 同花 20:1
    4: 10,    # 顺子 10:1
    3: 8,     # 三条 8:1
    2: 7,     # 两对 7:1
    # 对子Aces需要特殊处理
}

def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def user_data_path() -> str:
    return os.path.join(project_root(), "saving_data.json")

def che_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Casino_Holdem.json")

def get_data_file_path():
    return user_data_path()

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:,.2f}"
            break
    save_user_data(users)

# =========================================================
# Jackpot 文件加载与保存（保持不变）
# =========================================================

def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default_progressive = 271288.59
    if not os.path.exists(path):
        return True, default_progressive
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'Progressive_2.50':
                    return False, float(item.get('jackpot', default_progressive))
    except Exception:
        return True, default_progressive
    return True, default_progressive

def save_progressive(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    found = False
    for item in data:
        if item.get('Games') == 'Progressive_2.50':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": "Progressive_2.50", "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# =========================================================
# 扑克牌类与牌堆（完全保留）
# =========================================================

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            result = subprocess.run(
                [sys.executable, shuffle_script, "false", "1"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            if "deck" not in shuffle_data or "cut_position" not in shuffle_data:
                raise ValueError("Invalid shuffle data format")
            self.full_deck = [
                Card(d["suit"], d["rank"])
                for d in shuffle_data["deck"]
            ]
            self.cut_position = shuffle_data["cut_position"]
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
                KeyError) as e:
            print(f"Error calling shuffle.py: {e}. Using fallback shuffle.")
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
    
    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# =========================================================
# 手牌评估（完全保留）
# =========================================================

def evaluate_hand(cards):
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    suits = [c.suit for c in cards]
    unique_vals = sorted(set(values), reverse=True)
    if 14 in unique_vals:
        unique_vals.append(1)
    straight_vals = []
    seq = []
    for v in unique_vals:
        if not seq or seq[-1] - 1 == v:
            seq.append(v)
        else:
            seq = [v]
        if len(seq) >= 5:
            straight_vals = seq[:5]
            break
    flush_suit = next((s for s in SUITS if suits.count(s) >= 5), None)
    flush_cards = [c for c in cards if c.suit == flush_suit] if flush_suit else []
    if flush_cards and straight_vals:
        flush_vals = sorted({c.value for c in flush_cards}, reverse=True)
        if 14 in flush_vals:
            flush_vals.append(1)
        seq2 = []
        for v in flush_vals:
            if not seq2 or seq2[-1] - 1 == v:
                seq2.append(v)
            else:
                seq2 = [v]
            if len(seq2) >= 5:
                return (9, seq2[:5]) if seq2[0] == 14 else (8, seq2[:5])
    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, [quad, kicker])
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (6, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (5, top5)
    if straight_vals:
        return (4, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (2, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, [pair] + kickers)
    return (0, values[:5])

def find_best_5(cards):
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 5):
        ev = evaluate_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand

# =========================================================
# 游戏类（CHEGame）—— 完全保留原逻辑
# =========================================================

class CHEGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.dealer_hole = []
        self.ante = 0
        self.aa = 0
        self.call_bet = 0
        self.participate_jackpot = False
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False, False],
            "dealer": [False, False],
            "community": [False, False, False, False, False]
        }
        self.jackpot_initial, self.progressive_amount = load_jackpot()
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
    
    def dealer_qualifies(self, dealer_eval):
        """检查庄家是否合格（至少有一对4或更好）"""
        if dealer_eval[0] > 1:
            return True
        elif dealer_eval[0] == 1:
            pair_value = dealer_eval[1][0]
            if pair_value >= 4:
                return True
        else:
            return False
        
    def deal_initial(self):
        self.community_cards = self.deck.deal(5)
        self.player_hole = self.deck.deal(2)
        self.dealer_hole = self.deck.deal(2)
        
    def evaluate_hands(self):
        player_cards = self.player_hole + self.community_cards
        dealer_cards = self.dealer_hole + self.community_cards
        player_eval, player_best = find_best_5(player_cards)
        dealer_eval, dealer_best = find_best_5(dealer_cards)
        return player_eval, player_best, dealer_eval, dealer_best
    
    def evaluate_current_hand(self, cards, community_revealed_count):
        if community_revealed_count == 0:
            return None
        revealed_community = self.community_cards[:community_revealed_count]
        all_cards = cards + revealed_community
        if len(all_cards) < 2:
            return None
        best_eval, _ = find_best_5(all_cards)
        return best_eval

# =========================================================
# 历史记录保存（Casino_Holdem.json）
# =========================================================

def save_che_history(deck, player_cards, dealer_cards, community_cards, result_info=None):
    log_path = che_log_path()
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "push": 0,
            "fold": 0,
            "game": 0
        },
        "history": []
    }
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    if "history_record" in loaded:
                        for key in data["history_record"]:
                            if key not in loaded["history_record"]:
                                loaded["history_record"][key] = 0
                        data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    data["history"] = loaded
                    stats = {"player_win": 0, "dealer_win": 0, "fold": 0, "push": 0, "game": len(loaded)}
                    for rec in loaded:
                        if "result" in rec and "winner" in rec["result"]:
                            winner = rec["result"]["winner"]
                            if winner == "player":
                                stats["player_win"] += 1
                            elif winner == "dealer":
                                stats["dealer_win"] += 1
                            elif winner == "fold":
                                stats["fold"] += 1
                            elif winner == "push":
                                stats["push"] += 1
                    data["history_record"] = stats
        except Exception as e:
            print(f"读取历史文件出错: {e}，将使用全新记录")
    
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1
    
    stats = data["history_record"]
    stats["game"] += 1
    
    winner = None
    if result_info:
        if result_info.get("fold", False):
            winner = "fold"
            stats["fold"] += 1
        elif "winner" in result_info:
            winner = result_info["winner"]
            if winner == "player":
                stats["player_win"] += 1
            elif winner == "dealer":
                stats["dealer_win"] += 1
            elif winner == "push":
                stats["push"] += 1
    
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "player_cards": [str(c) for c in player_cards],
        "dealer_cards": [str(c) for c in dealer_cards],
        "community_cards": [str(c) for c in community_cards],
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner
    elif "winner" not in record["result"]:
        pass
    
    data["history"].append(record)
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]
    
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 主GUI类（CHEGUI）—— 基于UTH UI改造
# =========================================================

class CHEGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)
        
        self.username = username
        self.balance = initial_balance
        self.game = CHEGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {
            "ante": 0,
            "aa": 0,
            "call": 0,
            "jackpot": 0
        }
        self.bet_widgets = {}
        self.last_jackpot_selection = False
        
        # 存储上一次游戏的下注信息（用于重复下注）
        self.last_game_bet = None
        
        self._load_assets()
        self._create_widgets()

    # ---------- 规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("游戏规则")
        win.geometry("800x650")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        rules_text = """
        赌场扑克 游戏规则

        1. 游戏开始前下注:
           - 底注: 基础下注
           - AA+: 可选副注
           - 累进大奖: 可选参与($2.5)

        2. 游戏流程:
           a. 翻牌前:
               - 发玩家2张牌，庄家2张牌，公共牌3张（翻牌）
               - 查看手牌后选择:
                 * 弃牌: 输掉底注（AA+和累进大奖仍可能赢）
                 * 加注: 下注底注的2倍

           b. 翻牌圈:
               - 如果加注，发出最后2张公共牌（转牌和河牌）
               - 摊牌比较手牌

        3. 庄家资格:
           - 庄家必须至少有一对4或更好的牌才能参与比较
           - 如果庄家不合格，玩家赢得底注，加注退还

        4. 结算规则:
           - 底注:
             * 庄家不合格: 无条件获胜，按玩家牌型赔率支付
             * 玩家赢: 按玩家牌型赔率支付
             * 平局: 退还
             * 玩家输: 输掉

           - 加注:
             * 玩家赢: 支付1:1
             * 庄家不合格: 退还
             * 平局: 退还
             * 其他情况: 输掉

           - AA+边注:
             * 根据玩家最终手牌支付（见赔率表）
        """
        rules_label = tk.Label(
            content_frame, 
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        rules_label.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(
            content_frame, 
            text="赔率表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        odds_frame = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame.pack(fill=tk.X, padx=20, pady=5)
        headers = ["牌型", "底注赔率", "AA+赔率", "累进大奖"]
        odds_data = [
            ("皇家同花顺", "100:1", "100:1", "100%"),
            ("同花顺", "49:1", "50:1", "10%"),
            ("四条", "17:1", "40:1", "$1,250"),
            ("葫芦", "3:1", "30:1", "$375"),
            ("同花", "2:1", "20:1", "$250"),
            ("顺子", "1:1", "10:1", "-"),
            ("三条", "1:1", "8:1", "-"),
            ("两对", "1:1", "7:1", "-"),
            ("对子A", "1:1", "7:1", "-"),
            ("其他牌型", "1:1", "-", "-"),
        ]
        for col, h in enumerate(headers):
            tk.Label(
                odds_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row_data in enumerate(odds_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    odds_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(headers)):
            odds_frame.columnconfigure(c, weight=1)
        for r in range(len(odds_data) + 1):
            odds_frame.rowconfigure(r, weight=1)
        notes = """
        注: 
        * 玩家的牌和头3张公共牌组成牌型才获胜
        * 对子A指一对A
        """
        notes_label = tk.Label(
            content_frame, 
            text=notes,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        notes_label.pack(fill=tk.X, padx=10, pady=5)
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def on_close(self):
        timer = getattr(self, "auto_reset_timer", None)
        if timer:
            try:
                self.after_cancel(timer)
            except tk.TclError:
                pass
        try:
            update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))
        if callable(self.on_back):
            self.on_back(float(self.balance))


    # ---------- 加载扑克牌图片（轮流使用 Poker1/Poker2） ----------
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }
        self.original_images = {}
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        for suit in SUITS:
            for rank in RANKS:
                suit_name = suit_mapping.get(suit, suit)
                filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    text = "Error"
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    text_width, text_height = draw.textsize(text, font=font)
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

    # ---------- 筹码相关 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        if bet_type == "ante":
            current = float(self.ante_var.get())
            max_bet = 10000
            if current >= max_bet:
                messagebox.showwarning("下注限制", "底注已满，不能再下注！")
                return
            if current + chip_value > max_bet:
                allowed_amount = max_bet - current
                if allowed_amount > 0:
                    chip_value = allowed_amount
                    messagebox.showwarning("下注限制", f"底注已达上限，自动调整为 {int(allowed_amount)}")
                else:
                    messagebox.showwarning("下注限制", "底注已满，不能再下注！")
                    return
            self.ante_var.set(str(int(current + chip_value)))
        elif bet_type == "aa":
            current = float(self.aa_var.get())
            max_bet = 2500
            if current >= max_bet:
                messagebox.showwarning("下注限制", "AA+已满，不能再下注！")
                return
            if current + chip_value > max_bet:
                allowed_amount = max_bet - current
                if allowed_amount > 0:
                    chip_value = allowed_amount
                    messagebox.showwarning("下注限制", f"AA+已达上限，自动调整为 {int(allowed_amount)}")
                else:
                    messagebox.showwarning("下注限制", "AA+已满，不能再下注！")
                    return
            self.aa_var.set(str(int(current + chip_value)))

    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "aa":
            self.aa_var.set("0")
        elif bet_type == "call":
            self.call_var.set("0")
        if bet_type in self.bet_widgets:
            widget = self.bet_widgets[bet_type]
            original_bg = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg=original_bg))

    # ---------- 创建主界面 ----------
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌区域
        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        table_canvas.create_rectangle(0, 0, 725, 720, fill=ROOT_BG, outline=GOLD, width=5)

        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=190, y=5, width=300, height=210)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 中间提示
        self.ante_info_label0 = tk.Label(
            table_canvas, 
            text="庄家需要对子4或以上才合格", 
            font=('Arial', 22), 
            bg=ROOT_BG, 
            fg='#FFD700'
        )
        self.ante_info_label0.update_idletasks()
        label_width = self.ante_info_label0.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width) // 2
        self.ante_info_label0.place(x=center_x + 355, y=215, anchor='n')

        # 公共牌区域
        community_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=50, y=250, width=600, height=210)
        community_label = tk.Label(community_frame, text="公共牌", font=('Arial', 18), bg='#2a4a3c', fg='white')
        community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 底部提示
        self.ante_info_label = tk.Label(
            table_canvas, 
            text="庄家不合格时 加注退还 底注按玩家牌型赔付", 
            font=('Arial', 22), 
            bg=ROOT_BG, 
            fg='#FFD700'
        )
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width) // 2
        self.ante_info_label.place(x=center_x + 355, y=460, anchor='n')

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=190, y=500, width=300, height=210)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # ---------- 右侧控制面板 ----------
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        # 信息卡片
        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        header_info = tk.Frame(info_card, bg=HEADER_BG)
        header_info.pack(fill=tk.X)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)

        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial', 16, 'bold'), bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)

        self.stage_label = tk.Label(body_info, text="翻牌前", font=('Arial', 16, 'bold'), bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # 累进大奖卡片
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text="累进大奖", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_amount_var,
                                            font=('Arial', 20, 'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

        # 限红信息卡片
        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        header_limit_bar = tk.Frame(limit_card, bg=HEADER_BG)
        header_limit_bar.pack(fill=tk.X)
        tk.Label(header_limit_bar, text="下注上限", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_limit = tk.Frame(limit_card, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)

        table_frame = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        table_frame.pack(fill=tk.X, padx=0, pady=0)

        titles = ["底注最低", "底注最高", "边注最高"]
        for col, title in enumerate(titles):
            lbl = tk.Label(
                table_frame,
                text=title,
                font=('Arial', 11, 'bold'),
                bg=PANEL_BG,
                fg='#2A1B08',
                borderwidth=1,
                relief=tk.SOLID,
                padx=5,
                pady=5
            )
            lbl.grid(row=0, column=col, sticky="nsew", padx=0, pady=0)

        values = ["$10", "$10,000", "$2,500"]
        for col, val in enumerate(values):
            lbl = tk.Label(
                table_frame,
                text=val,
                font=('Arial', 12, 'bold'),
                bg=PANEL_BG,
                fg="#A88100",
                borderwidth=1,
                relief=tk.SOLID,
                padx=5,
                pady=5
            )
            lbl.grid(row=1, column=col, sticky="nsew", padx=0, pady=0)

        for col in range(3):
            table_frame.columnconfigure(col, weight=1)

        # 合并筹码 + 下注区卡片
        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)

        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text="筹码与下注", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)

        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)

        body_combined.columnconfigure(0, weight=1)
        body_combined.columnconfigure(1, weight=2)
        body_combined.columnconfigure(2, weight=1)

        # 筹码行
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=3, pady=(0, 8), sticky='ew')
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)

        chip_configs = [
            ('$10', '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black'),
            ("$2.5K", '#ff0000', 'white'),
        ]
        self.chip_buttons = []
        self.chip_texts = {}
        for i, (text, bg_color, fg_color) in enumerate(chip_configs):
            cell = tk.Frame(chip_row, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2, 2, 49, 49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5, 25.5, text=text, fill=fg_color, font=('Arial', 12, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$10")

        # 累进大奖复选框
        self.progressive_var = tk.IntVar()
        self.progressive_cb = tk.Checkbutton(
            body_combined, text="累进大奖 ($2.50)", variable=self.progressive_var,
            font=('Arial', 12, "bold"), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.progressive_cb.grid(row=1, column=0, columnspan=3, sticky='w', padx=35, pady=(4, 2))

        # 底注和AA+（同一行）
        row_ante = tk.Frame(body_combined, bg=PANEL_BG)
        row_ante.grid(row=2, column=0, columnspan=3, sticky='ew', pady=2)
        tk.Label(row_ante, text="       底注:", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row_ante, textvariable=self.ante_var, font=('Arial', 12),
                                    bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row_ante, text="    AA+:", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(10,0))
        self.aa_var = tk.StringVar(value="0")
        self.aa_display = tk.Label(row_ante, textvariable=self.aa_var, font=('Arial', 12),
                                 bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.aa_display.pack(side=tk.LEFT, padx=5)
        self.aa_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("aa"))
        self.aa_display.bind("<Button-3>", lambda e: self.reset_single_bet("aa", e))
        self.bet_widgets["aa"] = self.aa_display

        # 加注（Call）显示只读
        row_call = tk.Frame(body_combined, bg=PANEL_BG)
        row_call.grid(row=3, column=0, columnspan=3, sticky='ew', pady=2)
        tk.Label(row_call, text="       加注:", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.call_var = tk.StringVar(value="0")
        self.call_display = tk.Label(row_call, textvariable=self.call_var, font=('Arial', 12),
                                   bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.call_display.pack(side=tk.LEFT, padx=5)
        self.call_display.bind("<Button-3>", lambda e: self.reset_single_bet("call", e))
        self.bet_widgets["call"] = self.call_display

        # 操作卡片
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action_card.pack(fill=tk.X, pady=3)
        header_action = tk.Frame(action_card, bg=HEADER_BG)
        header_action.pack(fill=tk.X)
        tk.Label(header_action, text="操作", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)

        self.status_label = tk.Label(
            body_action, text="设置下注金额并开始游戏", font=('Arial', 12, 'bold'),
            bg=PANEL_BG, fg='#2A1B08', height=1
        )
        self.status_label.pack(fill=tk.X, pady=4)

        btn_frame = tk.Frame(body_action, bg=PANEL_BG)
        btn_frame.pack(fill=tk.X, pady=5)
        inner_btn_frame = tk.Frame(btn_frame, bg=PANEL_BG)
        inner_btn_frame.pack(anchor='center')

        self.reset_bets_button = tk.Button(
            inner_btn_frame, text="重设金额", command=self.reset_bets,
            font=('Arial', 12, 'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)

        self.repeat_bet_button = tk.Button(
            inner_btn_frame, text="重复上局下注", command=self.repeat_last_bet,
            font=('Arial', 12, 'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=12,
            state=tk.DISABLED
        )
        self.repeat_bet_button.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(
            inner_btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.action_frame = body_action

        # 底部信息卡片
        info_bottom_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_bottom_card.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(info_bottom_card, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)

        self.current_bet_label = tk.Label(
            body_bottom, text="本局下注: $0.00", font=('Arial', 12), bg=PANEL_BG, fg='black'
        )
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(
            row_last, text="上局获胜: $0.00", font=('Arial', 12), bg=PANEL_BG, fg='black'
        )
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(
            row_last, text="ℹ️", command=self.show_game_instructions,
            bg='#4B8BBE', fg='white', font=('Arial', 12), width=2, relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

        self.action_frame = body_action

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='#2f00ff', width=3, tags="highlight")
                break

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    def update_hand_labels(self):
        community_revealed_count = sum(self.game.cards_revealed["community"])
        player_eval = self.game.evaluate_current_hand(self.game.player_hole, community_revealed_count)
        player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
        self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
        if self.game.stage == "showdown" or self.game.folded or any(self.game.cards_revealed["dealer"]):
            dealer_eval = self.game.evaluate_current_hand(self.game.dealer_hole, community_revealed_count)
            dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]] if dealer_eval else ""
            self.dealer_label.config(text=f"庄家 - {dealer_hand_name}" if dealer_hand_name else "庄家")
        else:
            self.dealer_label.config(text="庄家")

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            if widget.winfo_exists() and isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)

    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            if widget.winfo_exists():
                try:
                    widget.config(state=tk.NORMAL)
                except:
                    pass

    # ---------- 游戏流程 ----------
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.aa = int(self.aa_var.get())
            self.participate_jackpot = bool(self.progressive_var.get())
            self.last_jackpot_selection = bool(self.progressive_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return

        if self.ante < 5:
            messagebox.showerror("错误", "底注至少需要10块")
            return

        total_bet = self.ante + self.aa
        if self.participate_jackpot:
            total_bet += 2.5

        if total_bet > self.balance:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return

        self.last_game_bet = {
            'ante': self.ante,
            'aa': self.aa,
            'progressive': self.participate_jackpot
        }
        self.repeat_bet_button.config(state=tk.NORMAL)

        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:,.2f}")

        ante_aa_bet = self.ante + self.aa
        rake = ante_aa_bet * 0.01
        self.game.progressive_amount += rake
        if self.participate_jackpot:
            self.game.progressive_amount += 2.21
        save_progressive(self.game.progressive_amount)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")

        self.game.reset_game()
        self.game.deal_initial()
        self.game.ante = self.ante
        self.game.aa = self.aa
        self.game.participate_jackpot = self.participate_jackpot

        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()

        self.animation_queue = []
        self.animation_in_progress = False
        self.active_card_labels = []
        self.card_positions = {}

        for i in range(5):
            card_id = f"community_{i}"
            self.card_positions[card_id] = {"current": (50, 50), "target": (i * 110, 0)}
            self.animation_queue.append(card_id)
        for i in range(2):
            card_id = f"player_{i}"
            self.card_positions[card_id] = {"current": (50, 50), "target": (i * 150, 0)}
            self.animation_queue.append(card_id)
        for i in range(2):
            card_id = f"dealer_{i}"
            self.card_positions[card_id] = {"current": (50, 50), "target": (i * 150, 0)}
            self.animation_queue.append(card_id)

        self.animate_deal()
        self.stage_label.config(text="翻牌前")

        self.ante_display.unbind("<Button-1>")
        self.aa_display.unbind("<Button-1>")
        self.progressive_cb.config(state=tk.DISABLED)
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")
        self.reset_bets_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)

        for widget in self.action_frame.winfo_children():
            if widget not in [self.reset_bets_button, self.start_button, self.status_label, self.repeat_bet_button]:
                widget.destroy()

        self.status_label.config(text="发牌中，请稍后。")

        buttons_container = tk.Frame(self.action_frame, bg=PANEL_BG)
        buttons_container.pack(pady=5)
        self.fold_button = tk.Button(
            buttons_container, text="弃牌", command=self.fold_action,
            state=tk.DISABLED, font=('Arial', 12, 'bold'), bg='#F44336', fg='white',
            width=10, relief=tk.RAISED, bd=2
        )
        self.fold_button.pack(side=tk.LEFT, padx=5)
        self.call_button = tk.Button(
            buttons_container, text="下注2倍", command=self.call_action,
            state=tk.DISABLED, font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white',
            width=10, relief=tk.RAISED, bd=2
        )
        self.call_button.pack(side=tk.LEFT, padx=5)

    # ---------- 动画（原始速度） ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        if card_id.startswith("community"):
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx] if idx < len(self.game.community_cards) else None
        elif card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hole[idx] if idx < len(self.game.player_hole) else None
        elif card_id.startswith("dealer"):
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hole[idx] if idx < len(self.game.dealer_hole) else None
        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(x=self.card_positions[card_id]["current"][0],
                         y=self.card_positions[card_id]["current"][1] + 20)
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        self.active_card_labels.append(card_label)
        self.animate_card_move(card_label)

    def animate_card_move(self, card_label):
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
        try:
            current_x, current_y = card_label.winfo_x(), card_label.winfo_y()
            target_x, target_y = card_label.target_pos
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx**2 + dy**2)
            if distance < 5:
                card_label.place(x=target_x, y=target_y)
                card_label.is_moving = False
                if card_label.target_pos == (50, 50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                self.after(20, self.animate_deal)
                return
            step_x = dx * 0.2
            step_y = dy * 0.2
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return

    def reveal_player_cards(self):
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()
        self.after(500, self.reveal_flop)

    def reveal_flop(self):
        self.flop_revealed = 0
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up and i < 3:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True
                self.flop_revealed += 1
        self.update_hand_labels()
        self.after(1000, self.enable_preflop_buttons)

    def enable_preflop_buttons(self):
        if hasattr(self, 'fold_button') and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.NORMAL)
        if hasattr(self, 'call_button') and self.call_button.winfo_exists():
            if self.balance >= self.game.ante * 2:
                self.call_button.config(state=tk.NORMAL)
            else:
                self.call_button.config(state=tk.DISABLED)
        self.status_label.config(text="做出决策: 弃牌或下注2倍")

    def reveal_turn_river(self):
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up and i >= 3:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True

    def reveal_dealer_cards(self):
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["dealer"][i] = True
        self.after(700, self.update_hand_labels)

    def flip_card_animation(self, card_label, callback=None):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 12
        orig_w, orig_h = 100, 140

        # 结束条件：恢复正面全尺寸图片
        if step > steps:
            card_label.is_face_up = True
            self.animation_in_progress = False
            tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
            card_label.place(x=tx, y=ty, width=orig_w, height=orig_h)
            card_label.config(image=front_img)
            return

        # 计算当前帧的宽度比例（前半段背面缩窄，后半段正面展开）
        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))        # 1 → 0
            use_back = True
        else:
            ratio = (step - half) / float(half)     # 0 → 1
            use_back = False

        w = max(1, int(orig_w * ratio))            # 当前宽度（至少1px）

        # 从缓存的原始图像生成缩放后的 PhotoImage
        # 注意：front_img 是完整正面图，但我们需要根据 use_back 选择图像源
        if use_back:
            # 使用背面图像（从 original_images 中获取“back”）
            img_key = "back"
            if img_key in self.original_images:
                pil_img = self.original_images[img_key].resize((w, orig_h), Image.LANCZOS)
            else:
                # 若没有背面原始图，则用当前 back_image 的原始尺寸? 这里直接使用 self.back_image 的原始图像？但 self.back_image 已经是 PhotoImage，无法缩放。
                # 保险做法：使用已加载的背面 PIL 原图（若存在）
                pil_img = self.original_images.get("back", Image.new('RGB', (orig_w, orig_h), 'green'))
                pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)
        else:
            # 正面：从 original_images 中获取对应牌的原图（卡牌原图未缩放）
            # 根据 card_label.card 获取 key
            card = card_label.card
            key = (card.suit, card.rank)
            pil_img = self.original_images.get(key)
            if pil_img is None:
                # 容错：用 front_img 的原始图像？但 front_img 是 PhotoImage，无法获取原图。
                # 这里我们假设 original_images 中一定有该牌，因为 _load_assets 已加载。
                # 若没有，则生成一个占位图
                pil_img = Image.new('RGB', (orig_w, orig_h), 'gray')
            pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)

        # 转换为 PhotoImage 并保存引用防止被垃圾回收
        scaled_img = ImageTk.PhotoImage(pil_img)
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_label] = scaled_img   # 用 card_label 作为 key

        # 更新 Label 显示
        tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
        offset = (orig_w - w) // 2      # 水平居中
        card_label.config(image=scaled_img)
        card_label.place(x=tx + offset, y=ty, width=w, height=orig_h)

        # 继续下一帧
        self.after(30, lambda: self.animate_flip(card_label, front_img, step + 1))

    # ---------- 动作 ----------
    def call_action(self):
        call_amount = self.game.ante * 2
        if self.balance < call_amount:
            messagebox.showerror("错误", "余额不足以支付加注")
            return
        self.balance -= call_amount
        self.update_balance()
        self.game.call_bet = call_amount
        self.call_var.set(str(int(call_amount)))
        self.status_label.config(text=f"加注: ${call_amount}")

        call_rake = call_amount * 0.01
        self.game.progressive_amount += call_rake
        save_progressive(self.game.progressive_amount)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")

        self.fold_button.config(state=tk.DISABLED)
        self.call_button.config(state=tk.DISABLED)

        total_bet = self.ante + self.aa + call_amount
        if self.participate_jackpot:
            total_bet += 2.5
        self.current_bet_label.config(text=f"本局下注: ${total_bet:,.2f}")

        self.after(1000, self.reveal_turn_river)
        self.game.stage = "showdown"
        self.after(2000, self.show_showdown)

    def fold_action(self):
        self.game.folded = True
        self.status_label.config(text="您已弃牌。游戏结束。")

        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True
        self.reveal_dealer_cards()
        self.update_hand_labels()

        self.after(1000, self.settle_side_bets_after_fold)

    def settle_side_bets_after_fold(self):
        aa_winnings = 0
        if self.game.aa > 0:
            aa_cards = self.game.player_hole + self.game.community_cards[:3]
            aa_eval, _ = find_best_5(aa_cards)
            aa_winnings = self.calculate_aa_winnings(aa_eval)
            self.win_details['aa'] = aa_winnings
            self.aa_var.set(str(int(aa_winnings)))
            if aa_winnings > 0:
                self.aa_display.config(bg='gold')
            elif aa_winnings == self.game.aa:
                self.aa_display.config(bg='light blue')
            else:
                self.aa_display.config(bg='white')

        jackpot_winnings = 0
        if self.game.participate_jackpot:
            progressive_cards = self.game.player_hole + self.game.community_cards[:3]
            pg_eval, _ = find_best_5(progressive_cards)
            # ========== 修改后的 jackpot_rules ==========
            jackpot_rules = {
                9: {"amount": lambda: self.game.progressive_amount, "message": "皇家同花顺! 赢得累进大奖 ${amount:,.2f}!"},
                8: {"amount": lambda: self.game.progressive_amount * 0.1, "message": "同花顺! 赢得累进大奖 ${amount:,.2f}!"},
                7: {"amount": 1250, "message": "四条! 赢得累进大奖 $1,250!"},
                6: {"amount": 375, "message": "葫芦! 赢得累进大奖 $375!"},
                5: {"amount": 250, "message": "同花! 赢得累进大奖 $250!"}
            }
            # ============================================
            if pg_eval[0] in jackpot_rules:
                rule = jackpot_rules[pg_eval[0]]
                if callable(rule["amount"]):
                    amount = rule["amount"]()
                else:
                    amount = rule["amount"]
                jackpot_winnings = amount
                self.game.progressive_amount -= amount
                if self.game.progressive_amount < 271288.59:
                    self.game.progressive_amount = 271288.59
                save_progressive(self.game.progressive_amount)
                self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
                messagebox.showinfo("恭喜您获得累进大奖！", rule["message"].format(amount=amount))
                self.progressive_display.config(bg='gold')

        total_winnings = aa_winnings + jackpot_winnings
        self.last_win = total_winnings
        self.balance += total_winnings
        self.update_balance()
        self.last_win_label.config(text=f"上局获胜: ${total_winnings:,.2f}")

        self.ante_var.set("0")
        self.call_var.set("0")
        self.bet_widgets["ante"].config(bg='white')
        self.bet_widgets["call"].config(bg='white')

        self._save_history(result_info={"fold": True, "total_winnings": total_winnings})

        for widget in self.action_frame.winfo_children():
            if widget not in [self.reset_bets_button, self.start_button, self.status_label, self.repeat_bet_button]:
                widget.destroy()
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", command=self.reset_game,
            font=('Arial', 12, 'bold'), bg='#2196F3', fg='white',
            width=10, relief=tk.RAISED, bd=2
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def calculate_aa_winnings(self, aa_eval):
        if self.game.aa <= 0:
            return 0
        aa_hand_rank = aa_eval[0]
        aa_hand_cards = aa_eval[1]
        is_pair_aces = (aa_hand_rank == 1 and len(aa_hand_cards) > 0 and aa_hand_cards[0] == 14)
        if is_pair_aces:
            return self.game.aa * (1 + 7)
        elif aa_hand_rank in AA_PAYOUT:
            odds = AA_PAYOUT[aa_hand_rank]
            return self.game.aa * (1 + odds)
        else:
            return 0

    def show_showdown(self):
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True
        self.after(500, self.final_reveal)

    def final_reveal(self):
        self.reveal_dealer_cards()
        self.after(2200, self.update_hand_labels)

        player_eval, player_best, dealer_eval, dealer_best = self.game.evaluate_hands()
        winnings = self.calculate_winnings(player_eval, dealer_eval)
        self.last_win = winnings
        self.balance += winnings
        self.update_balance()

        self.ante_var.set(str(int(self.win_details['ante'])))
        self.aa_var.set(str(int(self.win_details['aa'])))
        self.call_var.set(str(int(self.win_details['call'])))

        for bet_type, widget in self.bet_widgets.items():
            if self.win_details[bet_type] == 0:
                if bet_type == "ante":
                    self.ante_var.set("0")
                elif bet_type == "aa":
                    self.aa_var.set("0")
                elif bet_type == "call":
                    self.call_var.set("0")
                widget.config(bg='white')
            else:
                principal = 0
                if bet_type == "ante":
                    principal = self.game.ante
                elif bet_type == "aa":
                    principal = self.game.aa
                elif bet_type == "call":
                    principal = self.game.call_bet
                if self.win_details[bet_type] == principal:
                    widget.config(bg='light blue')
                else:
                    widget.config(bg='gold')

        self.status_label.config(text="游戏结束。")
        self.last_win_label.config(text=f"上局获胜: ${winnings:,.2f}")

        if player_eval > dealer_eval:
            winner = "player"
        elif dealer_eval > player_eval:
            winner = "dealer"
        else:
            winner = "push"
        self._save_history(result_info={"winner": winner, "winnings": winnings})

        for widget in self.action_frame.winfo_children():
            if widget not in [self.reset_bets_button, self.start_button, self.status_label, self.repeat_bet_button]:
                widget.destroy()
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", command=self.reset_game,
            font=('Arial', 12, 'bold'), bg='#2196F3', fg='white',
            width=10, relief=tk.RAISED, bd=2
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def calculate_winnings(self, player_eval, dealer_eval):
        self.win_details = {
            "ante": 0,
            "aa": 0,
            "call": 0,
            "jackpot": 0
        }
        total_winnings = 0

        dealer_qualified = self.game.dealer_qualifies(dealer_eval)

        # Ante
        if not dealer_qualified:
            player_hand_rank = player_eval[0]
            if player_hand_rank in ANTE_PAYOUT:
                odds = ANTE_PAYOUT[player_hand_rank]
                self.win_details['ante'] = self.game.ante * (1 + odds)
            else:
                self.win_details['ante'] = self.game.ante * 2
        elif player_eval > dealer_eval:
            player_hand_rank = player_eval[0]
            if player_hand_rank in ANTE_PAYOUT:
                odds = ANTE_PAYOUT[player_hand_rank]
                self.win_details['ante'] = self.game.ante * (1 + odds)
            else:
                self.win_details['ante'] = self.game.ante * 2
        elif player_eval == dealer_eval:
            self.win_details['ante'] = self.game.ante
        else:
            self.win_details['ante'] = 0
        total_winnings += self.win_details['ante']

        # Call bet
        if not dealer_qualified:
            self.win_details['call'] = self.game.call_bet
        elif player_eval > dealer_eval:
            self.win_details['call'] = self.game.call_bet * 2
        elif player_eval == dealer_eval:
            self.win_details['call'] = self.game.call_bet
        else:
            self.win_details['call'] = 0
        total_winnings += self.win_details['call']

        # AA+
        if self.game.aa > 0:
            aa_cards = self.game.player_hole + self.game.community_cards[:3]
            aa_eval, _ = find_best_5(aa_cards)
            aa_winnings = self.calculate_aa_winnings(aa_eval)
            self.win_details['aa'] = aa_winnings
            total_winnings += aa_winnings

        # Jackpot
        if self.game.participate_jackpot:
            progressive_cards = self.game.player_hole + self.game.community_cards[:3]
            pg_eval, _ = find_best_5(progressive_cards)
            # ========== 修改后的 jackpot_rules ==========
            jackpot_rules = {
                9: {"amount": lambda: self.game.progressive_amount, "message": "皇家同花顺! 赢得累进大奖 ${amount:,.2f}!"},
                8: {"amount": lambda: self.game.progressive_amount * 0.1, "message": "同花顺! 赢得累进大奖 ${amount:,.2f}!"},
                7: {"amount": 1250, "message": "四条! 赢得累进大奖 $1,250!"},
                6: {"amount": 375, "message": "葫芦! 赢得累进大奖 $375!"},
                5: {"amount": 250, "message": "同花! 赢得累进大奖 $250!"}
            }
            # ============================================
            if pg_eval[0] in jackpot_rules:
                rule = jackpot_rules[pg_eval[0]]
                if callable(rule["amount"]):
                    amount = rule["amount"]()
                else:
                    amount = rule["amount"]
                self.win_details['jackpot'] = amount
                total_winnings += amount
                self.game.progressive_amount -= amount
                if self.game.progressive_amount < 271288.59:
                    self.game.progressive_amount = 271288.59
                save_progressive(self.game.progressive_amount)
                self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
                messagebox.showinfo("恭喜您获得累进大奖！", rule["message"].format(amount=amount))
                self.progressive_display.config(bg='gold')

        total_bet = self.game.ante + self.game.aa + self.game.call_bet
        progressive_increase = total_bet * 0.01
        if self.game.participate_jackpot:
            progressive_increase += 2.21
        self.game.progressive_amount += progressive_increase
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59
        save_progressive(self.game.progressive_amount)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")

        return total_winnings

    # ---------- 历史记录 ----------
    def _save_history(self, result_info=None):
        try:
            deck = self.game.deck
            if deck is None:
                return
            save_che_history(
                deck=deck,
                player_cards=self.game.player_hole,
                dealer_cards=self.game.dealer_hole,
                community_cards=self.game.community_cards,
                result_info=result_info if result_info else {}
            )
        except Exception as e:
            print(f"保存历史记录时出错: {e}")

    # ---------- 辅助 ----------
    def repeat_last_bet(self):
        if self.last_game_bet is None:
            return
        self.ante_var.set(str(self.last_game_bet['ante']))
        self.aa_var.set(str(self.last_game_bet['aa']))
        self.progressive_var.set(1 if self.last_game_bet['progressive'] else 0)
        self.status_label.config(text="已重复上局下注")

    def reset_bets(self):
        self.ante_var.set("0")
        self.aa_var.set("0")
        self.call_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.ante_display.config(bg='#FFCDD2')
        self.aa_display.config(bg='#FFCDD2')
        self.after(500, lambda: [self.ante_display.config(bg='white'), self.aa_display.config(bg='white')])

    def animate_collect_cards(self, auto_reset):
        self.disable_action_buttons()
        self.animate_move_cards_out(auto_reset)

    def animate_move_cards_out(self, auto_reset):
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return
        for card_label in self.active_card_labels:
            card_label.target_pos = (1200, card_label.winfo_y())
        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        all_done = True
        for card_label in self.active_card_labels[:]:
            if not hasattr(card_label, 'target_pos'):
                continue
            current_x = card_label.winfo_x()
            target_x, target_y = card_label.target_pos
            dx = target_x - current_x
            if abs(dx) < 5:
                card_label.place(x=target_x, y=target_y)
                card_label.destroy()
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue
            new_x = current_x + dx * 0.2
            card_label.place(x=new_x)
            all_done = False
        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            self._do_reset(auto_reset)

    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if self.active_card_labels:
            self.disable_action_buttons()
            self.animate_collect_cards(auto_reset)
            return
        self._do_reset(auto_reset)

    def _do_reset(self, auto_reset=False):
        self._load_assets()
        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        self.ante_var.set("0")
        self.aa_var.set("0")
        self.call_var.set("0")
        self.progressive_var.set(1 if self.last_jackpot_selection else 0)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.progressive_display.config(bg=PANEL_BG)

        self.active_card_labels = []
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.aa_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("aa"))
        self.aa_display.bind("<Button-3>", lambda e: self.reset_single_bet("aa", e))
        self.progressive_cb.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

        for widget in self.action_frame.winfo_children():
            if widget != self.status_label:
                widget.destroy()

        btn_frame = tk.Frame(self.action_frame, bg=PANEL_BG)
        btn_frame.pack(fill=tk.X, pady=5)
        inner_btn_frame = tk.Frame(btn_frame, bg=PANEL_BG)
        inner_btn_frame.pack(anchor='center')

        self.reset_bets_button = tk.Button(
            inner_btn_frame, text="重设金额", command=self.reset_bets,
            font=('Arial', 12, 'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)

        self.repeat_bet_button = tk.Button(
            inner_btn_frame, text="重复上局下注", command=self.repeat_last_bet,
            font=('Arial', 12, 'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=12,
            state=tk.NORMAL if self.last_game_bet is not None else tk.DISABLED
        )
        self.repeat_bet_button.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(
            inner_btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")

    def show_card_sequence(self, event):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("730x750")
        win.resizable(0, 0)
        win.configure(bg='#f0f0f0')
        cut_pos = self.game.deck.start_pos
        cut_label = tk.Label(win, text=f"本局切牌位置: {cut_pos + 1}", font=('Arial', 14, 'bold'), bg='#f0f0f0')
        cut_label.pack(pady=10)
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        small_size = (60, 90)
        small_images = {}
        for i, card in enumerate(self.game.deck.full_deck):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig_img = self.original_images[key]
                small_img = orig_img.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                text = f"{card.rank}{card.suit}"
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                draw.text(((small_size[0]-tw)//2, (small_size[1]-th)//2), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)

        for row in range(6):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            cards_in_row = 9 if row < 5 else 7
            for col in range(cards_in_row):
                card_index = row * 9 + col
                if card_index >= 52:
                    break
                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5)
                is_cut_position = card_index == self.game.deck.start_pos
                bg_color = 'light blue' if is_cut_position else '#f0f0f0'
                card = self.game.deck.full_deck[card_index]
                card_label = tk.Label(card_container, image=small_images[card_index], bg=bg_color, borderwidth=1, relief="solid")
                card_label.image = small_images[card_index]
                card_label.pack()
                pos_label = tk.Label(card_container, text=str(card_index+1), bg=bg_color, font=('Arial', 9))
                pos_label.pack()

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return CHEGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("Casino Holdem")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = CHEGUI(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)

    def close_standalone():
        try:
            update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        root.destroy()

    page.on_back = lambda final_balance: close_standalone()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")

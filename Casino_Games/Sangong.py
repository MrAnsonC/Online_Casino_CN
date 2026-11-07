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

"""三公独立版：仅保留三公规则、UI、动画、下注、结算与存档。"""
import copy
import json
import os
import random
import re
import tkinter as tk
from collections import Counter
from datetime import datetime
from tkinter import messagebox
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
except ImportError:
    Image = ImageTk = ImageDraw = ImageFont = None

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../A_Tools/Account/saving_data.json')
def load_user_data():
    try:
        with open(get_data_file_path(),'r',encoding='utf-8') as f:
            data=json.load(f); return data if isinstance(data,list) else []
    except (FileNotFoundError,json.JSONDecodeError,OSError): return []
def save_user_data(users):
    try:
        with open(get_data_file_path(),'w',encoding='utf-8') as f: json.dump(users,f,ensure_ascii=False,indent=4)
    except OSError: pass
def update_balance_in_json(username,new_balance):
    users=load_user_data()
    for user in users:
        if user.get('user_name')==username: user['cash']=f'{new_balance:.2f}'; break
    save_user_data(users)

class SangongBetState:
    def __init__(self): self.bets={}
    def total_at_risk(self): return sum(map(float,self.bets.values()))
    def current_area_bet(self,bet_type,_param=None): return float(self.bets.get(bet_type,0))
    def add_bet(self,bet_type,amount,_param=None):
        self.bets[bet_type]=self.current_area_bet(bet_type)+float(amount)
    def clear_area(self,bet_type,_param=None): return float(self.bets.pop(bet_type,0))
    def clear_all(self): total=self.total_at_risk(); self.bets.clear(); return total

class SangongEngine:
    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A','2','3','4','5','6','7','8','9','10','J','Q','K')
    POWER = {rank: index for index, rank in enumerate(RANKS, 1)}
    TYPE_NAMES = {5: '大三公', 4: '小三公', 3: '混三公', 2: '对子', 1: '普通点数'}

    def __init__(self):
        self.new_shoe()

    def new_shoe(self):
        self.deck = [(suit, rank) for suit in self.SUITS for rank in self.RANKS]
        random.SystemRandom().shuffle(self.deck)

    def remaining_cards(self):
        return len(self.deck)

    def needs_shuffle(self):
        return len(self.deck) < 9

    def deal_round(self):
        if self.needs_shuffle():
            self.new_shoe()
        before = list(self.deck)
        hands = {'Player1': [], 'Banker': [], 'Player2': []}
        for _ in range(3):
            for side in ('Player1', 'Banker', 'Player2'):
                hands[side].append(self.deck.pop())
        return {'hands': hands, 'deck_order': before, 'shoe_remaining': len(self.deck)}

    @staticmethod
    def point_value(rank):
        if rank == 'A': return 1
        if rank in ('10', 'J', 'Q', 'K'): return 0
        return int(rank)

    @classmethod
    def evaluate(cls, hand, side=None):
        ranks = [card[1] for card in hand]
        counts = Counter(ranks)
        powers = sorted((cls.POWER[rank] for rank in ranks), reverse=True)
        point = sum(cls.point_value(rank) for rank in ranks) % 10
        if side == 'Banker' and ranks.count('4') == 3:
            return {'name': '破煞', 'key': (7,), 'point': point}
        if side in ('Player1', 'Player2') and ranks.count('8') == 3:
            return {'name': '发发发', 'key': (6,), 'point': point}
        all_faces = all(rank in ('J', 'Q', 'K') for rank in ranks)
        if all_faces and len(counts) == 1:
            key = (5, powers[0])
        elif all_faces:
            key = (4, powers[0])
        elif any(rank in ('J', 'Q', 'K') for rank in ranks) and point == 0:
            key = (3, powers[0])
        elif any(count >= 2 for count in counts.values()):
            pair = max(cls.POWER[rank] for rank, count in counts.items() if count >= 2)
            kicker = max((cls.POWER[rank] for rank, count in counts.items() if count == 1), default=pair)
            key = (2, pair, kicker)
        else:
            key = (1, point, powers[0])
        return {'name': cls.TYPE_NAMES[key[0]], 'key': key, 'point': point}

    @classmethod
    def compare(cls, player_hand, banker_hand, player_side):
        player = cls.evaluate(player_hand, player_side)
        banker = cls.evaluate(banker_hand, 'Banker')
        if banker['name'] == '破煞': winner = 'Banker'
        elif player['name'] == '发发发': winner = player_side
        elif player['key'] > banker['key']: winner = player_side
        elif player['key'] < banker['key']: winner = 'Banker'
        else: winner = 'Tie'
        return winner, player, banker

    @classmethod
    def pair_plus_odds(cls, hand):
        ranks=[cls.POWER[card[1]] for card in hand]; suits=[card[0] for card in hand]
        counts=Counter(ranks); unique=set(ranks); flush=len(set(suits))==1
        straight=(len(unique)==3 and (max(unique)-min(unique)==2 or unique=={1,12,13}))
        if straight and flush:return 40
        if 3 in counts.values():return 30
        if straight:return 6
        if flush:return 3
        if 2 in counts.values():return 1
        return 0

    @classmethod
    def gong_point_tie(cls, player_hand, banker_hand):
        # 先评估两手牌，获取牌型 key
        player_eval = cls.evaluate(player_hand, 'Player')
        banker_eval = cls.evaluate(banker_hand, 'Banker')
        # 牌型等级必须相同（key[0] 相同）
        if player_eval['key'][0] != banker_eval['key'][0]:
            return False
        # 再比较公牌数和点数
        gong = lambda hand: sum(card[1] in ('J','Q','K') for card in hand)
        point = lambda hand: sum(cls.point_value(card[1]) for card in hand) % 10
        return gong(player_hand) == gong(banker_hand) and point(player_hand) == point(banker_hand)

    @classmethod
    def settle(cls, bets, hands):
        credit = liability = 0.0
        outcomes = []
        bosha = cls.evaluate(hands['Banker'], 'Banker')['name'] == '破煞'
        for side in ('Player1', 'Player2'):
            stake = float(bets.get(side, 0.0))
            winner, player, _ = cls.compare(hands[side], hands['Banker'], side)
            factor = 0.0 if bosha or winner != side else (89.0 if player['name'] == '发发发' else 1.95)
            if stake:
                credit += stake * factor
                outcomes.append({'key': (side, None), 'stake': stake, 'return_factor': factor,
                                 'return_amount': stake * factor,
                                 'status': 'win' if factor > 0 else 'lose'})
        banker_total = float(bets.get('Banker', 0.0))
        if banker_total:
            half = banker_total / 2.0
            for side in ('Player1', 'Player2'):
                # ① 获取庄家评估结果，赋值给 banker
                winner, player, banker = cls.compare(hands[side], hands['Banker'], side)
                
                if bosha:
                    # 破煞通杀，庄家返还 2 倍（净赚 1 倍）
                    factor, extra = 2.0, 0.0
                elif winner in ('Banker', 'Tie'):
                    # 庄家获胜或平局（平局仍算庄赢）
                    if banker['name'] == '普通点数' and banker['point'] <= 4:
                        # 普通点数 0~4 点，盈利减半 → 返还 1.5 倍（净赚 0.5 倍）
                        factor, extra = 1.5, 0.0
                    else:
                        # 其他牌型（对子、三公、高点数等）全额赔付
                        factor, extra = 2.0, 0.0
                elif player['name'] == '发发发':
                    # 玩家 888 触发罚金（88 倍）
                    factor, extra = 0.0, half * 88.0
                else:
                    # 玩家其他牌型获胜，庄家输
                    factor, extra = 0.0, 0.0

                # 累加 credit 和 liability ...
                credit += half * factor
                liability += extra
                outcomes.append({'key': ('Banker', side), 'stake': half,
                                 'return_factor': factor, 'return_amount': half * factor,
                                 'status': 'win' if factor else 'lose'})
        side_specs=(
            ('Player1 PairPlus','Player1','pairplus'),('Player1 Tie','Player1','tie'),
            ('Player1 Sangong','Player1','sangong'),('Player2 PairPlus','Player2','pairplus'),
            ('Player2 Tie','Player2','tie'),('Player2 Sangong','Player2','sangong'),
            ('Banker PairPlus','Banker','pairplus'),('Banker Sangong','Banker','sangong'))
        for bet_type,side,kind in side_specs:
            stake=float(bets.get(bet_type,0.0)); profit=0
            if kind=='pairplus':profit=cls.pair_plus_odds(hands[side])
            elif kind=='tie':profit=24 if cls.gong_point_tie(hands[side],hands['Banker']) else 0
            elif kind=='sangong':profit=70 if all(card[1] in ('J','Q','K') for card in hands[side]) else 0
            factor=float(profit+1 if profit else 0)
            if stake:
                credit+=stake*factor
                outcomes.append({'key':(bet_type,None),'stake':stake,'return_factor':factor,
                                 'return_amount':stake*factor,'status':'win' if factor else 'lose'})
        stake = sum(float(value) for value in bets.values())
        return {'credit': credit, 'liability': liability,
                'net': credit - liability - stake, 'outcomes': outcomes}

class SangongV13(tk.Frame):
    WIDTH=1150; HEIGHT=750; GAME_X0=12; GAME_X1=1138; BOARD_INNER_X1=1128
    BG='#17120f'; PANEL='#211811'; PANEL_LINE='#665240'; FELT='#083f38'; LINE='#c3d5ca'
    PLAYER_ZONE_BASE='#102d47'; BANKER_ZONE_BASE='#4b1e22'
    MIN_BET=100.; MAX_TABLE_BET=2_000_000.; CHIP_MOVE_DURATION_MS=200; CHIP_MOVE_STEPS=10
    CHIP_SPECS=[(100,'#202020','100'),(500,'#d780c0','500'),(1000,'#ab0058','1K'),(5000,'#ba3438','5K'),(10000,'#70439a','10K'),(50000,'#2e7542','50K'),(250000,'#ffffff','250K')]
    M_CHIP_COLOR='#102d47'; BET_COLORS={'Player1':'#345fc4','Banker':'#c94349','Player2':'#345fc4'}
    def __init__(self,parent,balance=10000,user=None,on_back=None,on_balance_change=None,game_mode=None):
        super().__init__(parent,bg=self.BG,width=self.WIDTH,height=self.HEIGHT); self.pack_propagate(False)
        self.root=self; self.username=user; self.on_back=on_back; self.on_balance_change=on_balance_change
        self.balance=float(balance); self.final_balance=float(balance); self.game_mode='sangong'
        self.summary_mode='bet'; self.last_win_amount=0.; self.last_net=0.; self.engine=SangongEngine(); self.bet_state=SangongBetState()
        self.selected_chip=1000.; self.undo_stack=[]; self.last_round_bets=[]; self.bet_spots={}; self.chip_selector_items={}; self.control_buttons={}
        self.accept_bets=True; self.animation_running=False; self.settlement_running=False; self.animation_after_ids=[]
        self.chip_motion_after_ids=set(); self.chip_motion_serial=0; self.pending_bet_visual_amounts={}; self.settlement_after_id=None
        self.pre_deal_bets=None; self.current_result=None; self.settlement_flash_step=0; self._closing=False
        self.seat_order=['Player1','Player2','Banker']; self.history_file=os.path.join(self.get_runtime_json_dir(),'Sangong.json')
        try:
            with open(self.history_file,'r',encoding='utf-8') as f: records=json.load(f).get('history',[])
            saved=records[-1].get('seat_order') if records else None
            if sorted(saved or [])==['Banker','Player1','Player2']: self.seat_order=list(saved)
        except (OSError,json.JSONDecodeError,AttributeError,TypeError): pass
        self.bet_seat_order=list(self.seat_order); self.settlement_visual_bets=None
        self.banker_half_wins={'Player1':False,'Player2':False}; self.banker_return_amounts={}; self.flash_return_amounts={}
        self.winning_spot_keys=set(); self.flash_winning_keys=set(); self.flash_white=False; self.settlement_outcomes=[]
        self.external_card_images={}; self.external_card_images_rotated={}; self.external_card_pil={}
        self.external_back_image=None; self.external_back_pil=None; self.card_asset_dir=None; self.load_original_card_assets()
        top=self.winfo_toplevel()
        # Embedded games preserve the window settings owned by the parent.
        self._enter_window = top
        self._previous_enter_binding = top.bind('<Return>')
        self._enter_binding_id = top.bind('<Return>', self.handle_enter_deal)
        self.bind('<Destroy>', self._restore_enter_binding, add='+')
        self.create_ui(); self.select_chip(self.selected_chip); self.update_display()
    def handle_enter_deal(self,_event=None): self.deal_cards()
    def _current_round_total_cost(self): return self.bet_state.total_at_risk()
    def place_base_bet(self,bet_type,amount=None,record_undo=True):
        if not self.accept_bets or self.animation_running or self.settlement_running or (bet_type,None) not in self.bet_spots:return False
        requested=float(amount if amount is not None else self.selected_chip)
        if requested<100 or abs(requested/100-round(requested/100))>1e-9:return False
        allowed=float(int(max(0,min(requested,self.bet_limit_for(bet_type)-self.bet_state.current_area_bet(bet_type),self.MAX_TABLE_BET-self.bet_state.total_at_risk(),self.balance))//100)*100)
        if allowed<100:return False
        key=(bet_type,None); self.pending_bet_visual_amounts[key]=self.pending_bet_visual_amounts.get(key,0)+allowed
        self.bet_state.add_bet(bet_type,allowed); self.balance-=allowed
        if record_undo:self.undo_stack.append((bet_type,None,allowed))
        self.summary_mode='bet'; self.update_display()
        self._animate_amount_chip(allowed,self._chip_rack_source_position(),tuple(self.bet_spots[key]['chip_pos']),lambda:self._complete_pending_bet_visual(key,allowed))
        self.save_balance(); return True
    def clear_single_bet(self,bet_type,_param=None):
        if not self.accept_bets or self.animation_running or self.settlement_running:return
        refund=self.bet_state.clear_area(bet_type)
        if refund<=0:return
        self.balance+=refund; self.undo_stack=[x for x in self.undo_stack if x[0]!=bet_type]; self.pending_bet_visual_amounts.pop((bet_type,None),None)
        self.update_display(); self.save_balance()
    def clear_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:return
        refund=self.bet_state.clear_all()
        if refund<=0:return
        self.balance+=refund; self.undo_stack.clear(); self.pending_bet_visual_amounts.clear(); self.update_display(); self.save_balance()
    def snapshot_bets(self): return [(k,None,float(v)) for k,v in self.bet_state.bets.items() if v>0]


    def find_original_card_asset_dir(self):
        """Locate the original project A_Tools/Card/Poker1 directory."""
        current = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(current, 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(current), 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(os.path.dirname(current)), 'A_Tools', 'Card', 'Poker1'),
        ]
        for directory in candidates:
            if os.path.isdir(directory) and os.path.exists(os.path.join(directory, 'Background.png')):
                return directory
        return None

    def load_original_card_assets(self):
        """Use the original 100x140 external card artwork when available."""
        if Image is None or ImageTk is None:
            return
        self.external_card_pil = {}
        self.external_back_pil = None
        card_size = (100, 140)
        directory = self.find_original_card_asset_dir()
        resample = getattr(Image, 'Resampling', Image).LANCZOS

        if directory:
            try:
                for suit in SangongEngine.SUITS:
                    for rank in SangongEngine.RANKS:
                        path = os.path.join(directory, f'{suit}{rank}.png')
                        if not os.path.exists(path):
                            continue
                        base = Image.open(path).convert('RGBA').resize(card_size, resample)
                        self.external_card_pil[(suit, rank)] = base
                        self.external_card_images[(suit, rank)] = ImageTk.PhotoImage(base, master=self)
                        self.external_card_images_rotated[(suit, rank)] = ImageTk.PhotoImage(
                            base.rotate(90, expand=True), master=self)
                back_path = os.path.join(directory, 'Background.png')
                if os.path.exists(back_path):
                    back = Image.open(back_path).convert('RGBA').resize(card_size, resample)
                    self.external_back_pil = back
                    self.external_back_image = ImageTk.PhotoImage(back, master=self)
                if self.external_card_images and self.external_back_image is not None:
                    self.card_asset_dir = directory
                    return
            except Exception:
                self.external_card_images.clear()
                self.external_card_images_rotated.clear()
                self.external_card_pil.clear()
                self.external_back_image = None
                self.external_back_pil = None
                self.card_asset_dir = None

        # Temporary fallback only when the original external images do not exist.
        try:
            self.external_back_pil = self._make_fallback_card_pil(None, face_up=False)
            self.external_back_image = ImageTk.PhotoImage(self.external_back_pil, master=self)
            for suit in SangongEngine.SUITS:
                for rank in SangongEngine.RANKS:
                    card = (suit, rank)
                    base = self._make_fallback_card_pil(card, face_up=True)
                    self.external_card_pil[card] = base
                    self.external_card_images[card] = ImageTk.PhotoImage(base, master=self)
                    self.external_card_images_rotated[card] = ImageTk.PhotoImage(
                        base.rotate(90, expand=True), master=self)
        except Exception:
            self.external_card_images.clear()
            self.external_card_images_rotated.clear()
            self.external_card_pil = {}
            self.external_back_image = None
            self.external_back_pil = None

    def _make_fallback_card_pil(self, card, face_up=True):
        image = Image.new('RGBA', (100, 140), '#f4efe4' if face_up else '#253e66')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 97, 137), radius=8,
                               outline='#d7cbb9' if face_up else '#d7c46a', width=3)
        if not face_up:
            draw.rectangle((12, 12, 87, 127), outline='#e4d490', width=2)
            draw.line((16, 16, 83, 123), fill='#e4d490', width=2)
            draw.line((83, 16, 16, 123), fill='#e4d490', width=2)
            return image
        suit, rank = card
        suit_map = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}
        color = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
        try:
            font_big = ImageFont.truetype('DejaVuSans-Bold.ttf', 30)
            font_suit = ImageFont.truetype('DejaVuSans.ttf', 28)
        except Exception:
            font_big = None
            font_suit = None
        draw.text((8, 6), str(rank), fill=color, font=font_big)
        draw.text((9, 42), suit_map.get(suit, suit[:1]), fill=color, font=font_suit)
        draw.text((50, 88), suit_map.get(suit, suit[:1]), fill=color, font=font_suit,
                  anchor='mm')
        return image

    @staticmethod
    def spot_tag(key):
        bet_type, param = key
        safe = 'none' if param is None else re.sub(r'[^0-9A-Za-z]+', '_', str(param))
        safe_type = re.sub(r'[^0-9A-Za-z]+', '_', str(bet_type))
        return f'betspot_{safe_type}_{safe}'

    def register_spot(self, bet_type, x0, y0, x1, y1, chip_pos, label):
        key = (bet_type, None)
        self.bet_spots[key] = {
            'bounds': (x0, y0, x1, y1), 'chip_pos': chip_pos,
            'label': label, 'tag': self.spot_tag(key),
        }

    def draw_bottom_controls(self):
        c = self.canvas
        y0, y1 = 625, 748
        c.create_rectangle(0, y0, 1150, y1, fill=self.BG,
                           outline=self.PANEL_LINE, width=2, tags='controls')
        self.balance_text = c.create_text(10, 665, anchor='w', text='余额: $0.00',
                                          font=('Arial', 18, 'bold'), fill='white',
                                          tags=('dynamic', 'controls'))
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='本局下注: $0.00',
                                            font=('Arial', 18, 'bold'), fill='white',
                                            tags=('dynamic', 'controls'))

        # Compact stacked utility buttons leave the true centre of the 1150px
        # table free for the chip rack.
        self.clear_button = self.create_control_button(
            278, 650, 344, 704, '清除', self.clear_bets, '#7c3b40', font_size=11)

        # Larger chips, with the whole seven-chip rack centred at x=575.
        chip_diameter = 56
        chip_gap = 8
        chip_total_width = len(self.CHIP_SPECS) * chip_diameter + (len(self.CHIP_SPECS) - 1) * chip_gap
        chip_x = (self.WIDTH - chip_total_width) / 2
        chip_y = 646
        for value, color, label in self.CHIP_SPECS:
            tag = f'chip_select_{value}'
            outer = c.create_oval(chip_x, chip_y, chip_x + chip_diameter, chip_y + chip_diameter,
                                  fill='#292522', outline='#6d6259', width=3,
                                  tags=(tag, 'chip_selector', 'controls'))
            inner = c.create_oval(chip_x + 5, chip_y + 5,
                                  chip_x + chip_diameter - 5, chip_y + chip_diameter - 5,
                                  fill=color, outline='#eee3d6', width=2,
                                  tags=(tag, 'chip_selector', 'controls'))
            text_color = self.contrast_text_color(color)
            label_id = c.create_text(chip_x + chip_diameter / 2,
                                     chip_y + chip_diameter / 2, text=label,
                                     font=('Arial', 10, 'bold'), fill=text_color,
                                     tags=(tag, 'chip_selector', 'controls'))
            c.tag_bind(tag, '<Button-1>', lambda _e, v=value: self.select_chip(v))
            self.chip_selector_items[value] = (outer, inner, label_id)
            chip_x += chip_diameter + chip_gap

        self.info_button = self.create_control_button(
            810, 650, 855, 695, '❓', self.show_game_instructions, '#315b72',
            fg='white', font_size=17)
        self.repeat_button = self.create_control_button(
            862, 638, 1000, 708, '重复下注', self.repeat_last_bets, '#5b4938', font_size=11)
        self.deal_button = self.create_control_button(
            1012, 628, 1138, 720, '开始' if False else '开牌', self.deal_cards, '#d5ad4d',
            fg='#111', font_size=14, subtext='ENTER', subtext_font_size=10)
        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()

        # 在 chip selector 循环之后，添加说明文字
        self.rule_text = self.canvas.create_text(
            575, 718,  # 居中，位于 chip selector 下方
            text='*庄家以0-4点获胜，赔半',
            font=('Arial', 11, 'bold'),
            fill='#e0d5b0',
            tags=('controls', 'dynamic')
        )

    @staticmethod
    def shade_color(color, factor):
        color = color.lstrip('#')
        if len(color) != 6:
            return '#555555'
        values = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
        values = [max(0, min(255, int(value * factor))) for value in values]
        return '#' + ''.join(f'{value:02x}' for value in values)

    def create_control_button(self, x0, y0, x1, y1, text, command, fill,
                              fg='white', font_size=11, subtext=None,
                              subtext_font_size=10):
        tag = f'control_button_{len(self.control_buttons)}'
        shadow = self.canvas.create_rectangle(x0 + 5, y0 + 6, x1 + 5, y1 + 6,
                                              fill='#070605', outline='#070605',
                                              width=1, tags=(tag, 'controls'))
        rim = self.canvas.create_rectangle(x0, y0, x1, y1,
                                           fill=self.shade_color(fill, 0.55),
                                           outline='#b7a58d', width=2,
                                           tags=(tag, 'controls'))
        face = self.canvas.create_rectangle(x0 + 4, y0 + 4, x1 - 4, y1 - 4,
                                            fill=fill,
                                            outline=self.shade_color(fill, 1.25),
                                            width=2, tags=(tag, 'controls'))
        highlight = self.canvas.create_line(x0 + 8, y0 + 8, x1 - 8, y0 + 8,
                                            fill=self.shade_color(fill, 1.45), width=2,
                                            tags=(tag, 'controls'))
        center_y = (y0 + y1) / 2 - 1
        text_y = center_y - 12 if subtext else center_y
        text_id = self.canvas.create_text((x0 + x1) / 2, text_y, text=text,
                                          font=('Arial', font_size, 'bold'), fill=fg,
                                          tags=(tag, 'controls'))
        subtext_id = None
        subtext_center_y = None
        if subtext:
            subtext_center_y = center_y + 16
            subtext_id = self.canvas.create_text((x0 + x1) / 2, subtext_center_y,
                                                 text=subtext,
                                                 font=('Arial', subtext_font_size, 'bold'),
                                                 fill=fg, tags=(tag, 'controls'))
        self.control_buttons[tag] = {
            'shadow': shadow, 'rim': rim, 'face': face, 'highlight': highlight,
            'text': text_id, 'subtext': subtext_id, 'command': command,
            'fill': fill, 'fg': fg, 'enabled': True, 'pressed': False,
            'center_y': text_y, 'subtext_center_y': subtext_center_y,
        }

        def enter(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 1.12))

        def leave(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=button['fill'])

        def press(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled']:
                return
            button['pressed'] = True
            self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 0.72))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 0.8))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'] + 2)
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'] + 2)

        def release(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled'] or not button['pressed']:
                return
            button['pressed'] = False
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'])
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
            button['command']()

        self.canvas.tag_bind(tag, '<Enter>', enter)
        self.canvas.tag_bind(tag, '<Leave>', leave)
        self.canvas.tag_bind(tag, '<ButtonPress-1>', press)
        self.canvas.tag_bind(tag, '<ButtonRelease-1>', release)
        return tag

    def set_control_button_state(self, tag, enabled):
        button = self.control_buttons.get(tag)
        if not button:
            return
        button['enabled'] = bool(enabled)
        button['pressed'] = False
        x, _y = self.canvas.coords(button['text'])
        self.canvas.coords(button['text'], x, button['center_y'])
        if button.get('subtext'):
            sx, _sy = self.canvas.coords(button['subtext'])
            self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
        if enabled:
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfigure(button['text'], fill=button['fg'])
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill=button['fg'])
        else:
            self.canvas.itemconfigure(button['face'], fill='#4a4743')
            self.canvas.itemconfigure(button['rim'], fill='#262422')
            self.canvas.itemconfigure(button['highlight'], fill='#66615b')
            self.canvas.itemconfigure(button['text'], fill='#9b9690')
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill='#9b9690')

    def update_control_states(self):
        enabled = self.accept_bets and not self.animation_running and not self.settlement_running
        for attr in ('clear_button', 'repeat_button', 'deal_button'):
            tag = getattr(self, attr, None)
            if tag:
                self.set_control_button_state(tag, enabled)

    def _schedule_chip_motion(self, delay_ms, callback):
        """Schedule one chip-motion frame and keep its after-id cancellable."""
        holder = {}

        def run():
            after_id = holder.get('id')
            if after_id is not None:
                self.chip_motion_after_ids.discard(after_id)
            if self._closing:
                return
            callback()

        after_id = self.after(max(0, int(delay_ms)), run)
        holder['id'] = after_id
        self.chip_motion_after_ids.add(after_id)
        return after_id

    def _chip_rack_source_position(self):
        """Return the centre of the currently selected physical chip in the rack."""
        items = self.chip_selector_items.get(self.selected_chip)
        if items:
            try:
                coords = self.canvas.coords(items[1])
                if len(coords) >= 4:
                    return ((coords[0] + coords[2]) / 2.0,
                            (coords[1] + coords[3]) / 2.0)
            except tk.TclError:
                pass
        # Seven-chip rack is centred in the lower control area.
        return (self.WIDTH / 2.0, 674.0)

    def _chip_rack_return_position(self, index=0, total=1):
        """Spread simultaneous winning returns slightly across the chip-rack centre."""
        total = max(1, int(total))
        index = max(0, min(int(index), total - 1))
        if total <= 1:
            offset = 0.0
        else:
            spacing = min(34.0, 150.0 / max(1, total - 1))
            offset = (index - (total - 1) / 2.0) * spacing
        return (self.WIDTH / 2.0 + offset, 674.0)

    def _animate_amount_chip(self, amount, start_xy, target_xy, on_complete=None,
                             role='wager'):
        """Animate one compact chip from start_xy to target_xy in exactly 0.2 s."""
        if self._closing:
            if callable(on_complete):
                on_complete()
            return

        amount = float(amount)
        if amount <= 0:
            if callable(on_complete):
                on_complete()
            return

        self.chip_motion_serial += 1
        tag = f'chip_motion_{self.chip_motion_serial}'
        x, y = map(float, start_xy)
        tx, ty = map(float, target_xy)
        radius = 19.0
        chip_color = self.bet_chip_color(amount)
        text_color = self.contrast_text_color(chip_color)
        outline = '#ffd84a' if role == 'fee' else '#e2ddd5'

        outer = self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill='#292522', outline='#151311', width=1,
            tags=(tag, 'chip_motion'))
        inner = self.canvas.create_oval(
            x - radius + 3, y - radius + 3, x + radius - 3, y + radius - 3,
            fill=chip_color, outline=outline, width=2 if role == 'fee' else 1,
            tags=(tag, 'chip_motion'))
        text = self.canvas.create_text(
            x, y, text=self._compact_amount(amount),
            font=('Arial', 9, 'bold'), fill=text_color,
            tags=(tag, 'chip_motion'))
        item_ids = (outer, inner, text)
        steps = max(1, int(self.CHIP_MOVE_STEPS))
        frame_ms = max(1, int(round(self.CHIP_MOVE_DURATION_MS / steps)))

        def place_items(cx, cy):
            try:
                self.canvas.coords(outer, cx - radius, cy - radius,
                                   cx + radius, cy + radius)
                self.canvas.coords(inner, cx - radius + 3, cy - radius + 3,
                                   cx + radius - 3, cy + radius - 3)
                self.canvas.coords(text, cx, cy)
                self.canvas.tag_raise(tag)
            except tk.TclError:
                return False
            return True

        def frame(step):
            if self._closing:
                return
            ratio = min(1.0, max(0.0, step / steps))
            # Smoothstep keeps the motion quick but avoids a mechanical stop.
            eased = ratio * ratio * (3.0 - 2.0 * ratio)
            cx = x + (tx - x) * eased
            cy = y + (ty - y) * eased
            if not place_items(cx, cy):
                return
            if step >= steps:
                try:
                    self.canvas.delete(tag)
                except tk.TclError:
                    pass
                if callable(on_complete):
                    on_complete()
                return
            self._schedule_chip_motion(frame_ms, lambda: frame(step + 1))

        place_items(x, y)
        self._schedule_chip_motion(frame_ms, lambda: frame(1))

    def _complete_pending_bet_visual(self, key, amount):
        pending = max(0.0, float(self.pending_bet_visual_amounts.get(key, 0.0))
                      - float(amount))
        if pending > 1e-9:
            self.pending_bet_visual_amounts[key] = pending
        else:
            self.pending_bet_visual_amounts.pop(key, None)
        if not self._closing:
            self.update_bet_chips()
            self.canvas.tag_raise('controls')

    def select_chip(self, amount):
        self.selected_chip = float(amount)
        for value, items in self.chip_selector_items.items():
            outer, _inner, _text = items
            selected = float(value) == float(amount)
            self.canvas.itemconfigure(outer,
                                      outline='#ffda42' if selected else '#6d6259',
                                      width=5 if selected else 3)
        self.canvas.tag_raise('chip_selector')

    @staticmethod
    def format_money(value):
        if abs(value - round(value)) < 0.005:
            return f'${value:,.0f}'
        return f'${value:,.2f}'

    @staticmethod
    def contrast_text_color(color):
        value = color.lstrip('#')
        if len(value) != 6:
            return 'black'
        red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        return 'black' if luminance >= 150 else 'white'

    @staticmethod
    def _compact_amount(amount):
        if amount >= 1_000_000:
            # Winning chips are compacted in M once they reach 1000K.
            # Exact 100K steps have an exact one-decimal M representation;
            # smaller residuals are intentionally truncated and marked with +.
            hundred_k = 100_000.0
            exact_step = abs(amount / hundred_k - round(amount / hundred_k)) < 1e-9
            truncated_tenths = int(amount // hundred_k) / 10.0
            text = (f'{truncated_tenths:.0f}M' if abs(truncated_tenths - round(truncated_tenths)) < 1e-9
                    else f'{truncated_tenths:.1f}M')
            return text if exact_step else text + '+'
        if amount >= 1000:
            value = amount / 1000
            return f'{value:.0f}K' if abs(value - round(value)) < 0.01 else f'{value:.1f}K'
        return str(int(round(amount))) if abs(amount - round(amount)) < 0.01 else f'{amount:.1f}'

    @classmethod
    def bet_chip_color(cls, amount):
        # _compact_amount() switches to M at 1,000,000; mirror that visual state
        # with a dark-navy chip. contrast_text_color() then yields white text.
        if amount >= 1_000_000:
            return cls.M_CHIP_COLOR

        color = cls.CHIP_SPECS[0][1]
        for threshold, chip_color, _label in cls.CHIP_SPECS:
            if amount >= threshold:
                color = chip_color
            else:
                break
        return color

    def _queue_animation(self, delay, callback, *args):
        after_id = self.after(delay, callback, *args)
        self.animation_after_ids.append(after_id)
        return after_id

    def _back_photo(self, rotated=False):
        if not rotated:
            return self.external_back_image
        image = getattr(self, '_rotated_back_image', None)
        if image is None and self.external_back_pil is not None and ImageTk is not None:
            self._rotated_back_image = ImageTk.PhotoImage(
                self.external_back_pil.rotate(90, expand=True), master=self)
            image = self._rotated_back_image
        return image or self.external_back_image

    def _animate_card_entrance_original(self, hand_type, index, rotated=False, on_arrive=None):
        target_x, target_y = self.card_position(hand_type, index)
        base_w = 140 if rotated else 100
        start_x = (self.GAME_X0 + self.GAME_X1) / 2 - base_w / 2
        start_y = -110 if rotated else -150
        back = self._back_photo(rotated=rotated)
        card_id = self.canvas.create_image(start_x, start_y, image=back, anchor='nw',
                                           tags=('animation_card', 'animation'))
        self.card_item_ids.append(card_id)
        info = (hand_type, card_id, index)
        self.initial_card_ids.append(info)

        def move_step(step=0):
            if self._closing:
                return
            ratio = min(1.0, step / 30.0)
            x = start_x + (target_x - start_x) * ratio
            y = start_y + (target_y - start_y) * ratio
            self.canvas.coords(card_id, x, y)
            if step < 30:
                self._queue_animation(10, move_step, step + 1)
            elif callable(on_arrive):
                on_arrive(info)

        move_step(0)
        return info

    def get_runtime_json_dir(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        target = os.path.join(project_root, 'A_Logs', 'Json')
        try:
            os.makedirs(target, exist_ok=True)
            return target
        except OSError:
            target = os.path.join(current_dir, 'A_Logs', 'Json')
            os.makedirs(target, exist_ok=True)
            return target

    def save_balance(self):
        if self.username:
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def _face_photo(self,card,rotated=False):
        card=tuple(card)
        return self.external_card_images_rotated.get(card) if rotated else self.external_card_images.get(card)
    def _create_scaled_flip_image(self,card,width,height,use_back=False,rotated=False):
        if Image is None or ImageTk is None:return self._back_photo(rotated) if use_back else self._face_photo(card,rotated)
        base=self.external_back_pil if use_back else self.external_card_pil.get(tuple(card))
        if base is None:return self._back_photo(rotated) if use_back else self._face_photo(card,rotated)
        if rotated:base=base.rotate(90,expand=True)
        image=base.resize((max(1,int(width)),max(1,int(height))),getattr(Image,'Resampling',Image).LANCZOS)
        return ImageTk.PhotoImage(image,master=self)
    def update_display(self):
        self.canvas.itemconfigure(self.balance_text,text=f'余额: {self.format_money(self.balance)}')
        text=f'上局返还: {self.format_money(self.last_win_amount)}' if self.summary_mode=='win' else f'本局下注: {self.format_money(self._current_round_total_cost())}'
        self.canvas.itemconfigure(self.total_bet_text,text=text); self.update_bet_chips(); self.update_control_states()


    def update_history_table(self):
        return

    def bet_limit_for(self, bet_type):
        return 500_000.0 if bet_type in ('Player1','Player2','Banker') else 50_000.0

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            visual = getattr(self, 'settlement_visual_bets', None)
            amount = (float(visual.get(key[0], 0.0)) if visual is not None
                      else self.bet_state.current_area_bet(key[0]))
            pending = float(self.pending_bet_visual_amounts.get(key, 0.0))
            if pending > 0 and not self.settlement_running:
                amount = max(0.0, amount - pending)
            if visual is not None and key[0] != 'Banker' and key not in self.winning_spot_keys:
                continue
            if amount <= 0: continue
            x0,y0,x1,y1 = spot['bounds']; positions = [((x0+x1)/2,(y0+y1)/2,amount)]
            if key[0] == 'Banker':
                candidates = [('Player1',x0+(x1-x0)*.25),('Player2',x0+(x1-x0)*.75)]
                if visual is not None:
                    candidates = [(side,x) for side,x in candidates if self.banker_half_wins.get(side)]
                positions = [(x,(y0+y1)/2,
                              self.banker_return_amounts.get(side,amount/2) if getattr(self,'flash_white',False) else amount/2)
                             for side,x in candidates]
            elif visual is not None and getattr(self,'flash_white',False):
                amount=self.flash_return_amounts.get(key,amount)
                positions=[((x0+x1)/2,(y0+y1)/2,amount)]
            for x,y,shown in positions:
                color=self.bet_chip_color(shown); fg=self.contrast_text_color(color); radius=19
                self.canvas.create_oval(x-radius,y-radius,x+radius,y+radius,fill='#292522',outline='#151311',tags=('bet_chip_dynamic',spot['tag']))
                self.canvas.create_oval(x-radius+3,y-radius+3,x+radius-3,y+radius-3,fill=color,outline='#e2ddd5',tags=('bet_chip_dynamic',spot['tag']))
                self.canvas.create_text(x,y,text=self._compact_amount(shown),font=('Arial',9,'bold'),fill=fg,tags=('bet_chip_dynamic',spot['tag']))

    def create_ui(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_rectangle(0, 0, self.WIDTH, self.HEIGHT,
                                     fill=self.BG, outline='', tags='static')
        self.draw_animation_panel()
        self.draw_board()
        self.draw_bottom_controls()

    def draw_animation_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = 12, 4, 1138, 310
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.animation_panel = (x0, y0, x1, y1)
        self.animation_phase_text = c.create_text(575, 22, text='三公 SANGONG',
            font=('Arial', 16, 'bold'), fill='#d4c3a9', tags='animation')
        bounds = ((22,376),(392,758),(774,1128)); names={'Player1':'玩家1','Player2':'玩家2','Banker':'庄家'}
        zones = []
        for side,(zx0,zx1) in zip(self.seat_order,bounds):
            zones.append((side,zx0,zx1,self.BANKER_ZONE_BASE if side=='Banker' else self.PLAYER_ZONE_BASE,
                          '#a56a6d' if side=='Banker' else '#6386a5',names[side]))
        self.zone_rects = {}; self.score_texts = {}; self.type_texts = {}
        for side, zx0, zx1, fill, outline, label in zones:
            zone_tag = 'seat_zone_' + side
            self.zone_rects[side] = c.create_rectangle(zx0, 42, zx1, 303, fill=fill,
                outline=outline, width=2, tags=('animation', zone_tag))
            c.create_text((zx0 + zx1) / 2, 59, text=label, font=('Arial', 18, 'bold'),
                          fill='#ffaaaa' if side == 'Banker' else '#93b9ff', tags=('animation', zone_tag))
            self.type_texts[side] = c.create_text((zx0 + zx1) / 2, 286, text='等待开牌',
                font=('Arial', 24, 'bold'), fill='white', tags=('animation', zone_tag))
        self.player_zone_rect = self.zone_rects['Player1']
        self.banker_zone_rect = self.zone_rects['Banker']
        self.player_zone_label = self.type_texts['Player1']
        self.banker_zone_label = self.type_texts['Banker']
        self.player_score_text = c.create_text(0, 0, text='', state='hidden')
        self.banker_score_text = c.create_text(0, 0, text='', state='hidden')
        self.tie_flash_rect = c.create_rectangle(0, 0, 0, 0, state='hidden')
        self.card_item_ids = []; self.revealed_cards = {s: [] for s in self.zone_rects}
        self._temp_flip_images = {}

    def card_position(self, hand_type, index):
        centre = (199,575,951)[self.seat_order.index(hand_type)]
        # 原版直立牌宽100px；相邻牌边缘保持准确的5px间距。
        return centre - 155 + index * 105, 103

    def clear_card_display(self):
        for item in getattr(self, 'card_item_ids', []):
            self.canvas.delete(item)
        self.card_item_ids = []; self._temp_flip_images = {}
        self.revealed_cards = {s: [] for s in ('Player1', 'Banker', 'Player2')}
        for item in getattr(self, 'type_texts', {}).values():
            self.canvas.itemconfigure(item, text='等待开牌', fill='white')

    def draw_board(self):
        self.canvas.create_rectangle(12, 316, 1138, 620, fill=self.FELT,
                                     outline=self.LINE, width=2, tags='static')
        self.draw_mode_betting_board()

    def draw_mode_betting_board(self):
        c = self.canvas; c.delete('board_dynamic'); c.delete('bet_chip_dynamic')
        self.bet_spots = {}
        bounds=((18,392),(392,766),(766,1132)); names={'Player1':'玩家1','Player2':'玩家2','Banker':'庄家'}
        main_odds={'Player1':'0.95:1 · 888赢88:1','Player2':'0.95:1 · 888赢88:1','Banker':'1:1* · 平局赢 · 444通杀'}
        for side,(x0,x1) in zip(self.bet_seat_order,bounds):
            group='bet_group_'+side
            cut=11
            c.create_polygon(x0+cut,322,x1-cut,322,x1,333,x1,606,x1-cut,617,
                x0+cut,617,x0,606,x0,333,fill='#062f2b',outline='#d9b64c',width=2,
                tags=('board_dynamic',group))
            cx=(x0+x1)/2
            c.create_polygon(cx-92,326,cx-80,316,cx+80,316,cx+92,326,cx+80,346,cx-80,346,
                fill='#071b1b',outline='#e4c357',width=2,tags=('board_dynamic',group))
            title_color='#2785ff' if side!='Banker' else '#ef4048'
            c.create_text(cx,331,text=names[side],font=('Arial',19,'bold'),fill=title_color,
                          tags=('board_dynamic',group))
            if side=='Banker':
                specs=(('Banker PairPlus','庄对子+','1-40:1'),('Banker Sangong','庄家三公','70:1'))
            else:
                prefix=names[side]; specs=((side+' PairPlus',prefix+'对子+','1-40:1'),
                    (side+' Tie',prefix+'平局','24:1'),(side+' Sangong',prefix+'三公','70:1'))
            width=(x1-x0-8)/len(specs)
            for index,(bet_type,label,odds) in enumerate(specs):
                sx0=x0+4+index*width; sx1=x0+4+(index+1)*width
                self._draw_connected_spot(bet_type,sx0,354,sx1,438,label,odds,False,group)
            self._draw_connected_spot(side,x0+4,442,x1-4,612,names[side]+'主注',main_odds[side],True,group)
            if side=='Banker':
                main_x0,main_x1=x0+4,x1-4
                banker_tag = self.spot_tag(('Banker', None))
                c.create_text(main_x0+(main_x1-main_x0)*.25, 565, text='玩家1',
                            font=('Arial',10,'bold'), fill='#ffd9d9',
                            tags=('board_dynamic', group, 'banker_opponent_label', banker_tag))
                c.create_text(main_x0+(main_x1-main_x0)*.75, 565, text='玩家2',
                            font=('Arial',10,'bold'), fill='#ffd9d9',
                            tags=('board_dynamic', group, 'banker_opponent_label', banker_tag))
            c.create_line(x0+13,607,x1-13,607,fill='#8f762f',tags=('board_dynamic',group))
            if x1<1132:c.create_polygon(x1-8,440,x1,432,x1+8,440,x1,448,fill='#d9b64c',outline='#fff0a0',tags=('board_dynamic',group))
        self.update_bet_chips()

    def _draw_connected_spot(self,bet_type,x0,y0,x1,y1,label,odds,main,group):
        c=self.canvas; tag=self.spot_tag((bet_type,None)); fill=self.BET_COLORS.get(bet_type,'#0b4a42'); cut=7
        rect=c.create_polygon(x0+cut,y0,x1-cut,y0,x1,y0+cut,x1,y1-cut,x1-cut,y1,
            x0+cut,y1,x0,y1-cut,x0,y0+cut,fill=fill,outline='#d9b64c',width=1,
            tags=('board_dynamic',tag,group))
        label_item=c.create_text((x0+x1)/2,y0+(28 if main else 25),text=label,
            font=('Arial',23 if main else 14,'bold'),fill='white',tags=('board_dynamic',tag,group))
        odds_item=c.create_text((x0+x1)/2,y1-16,text=odds,
            font=('Arial',16 if main else 11,'bold'),fill='white',tags=('board_dynamic',tag,group))
        self.register_spot(bet_type,x0,y0,x1,y1,((x0+x1)/2,(y0+y1)/2),label)
        self.bet_spots[(bet_type,None)].update({'rect_id':rect,'label_item':label_item,
            'odds_item':odds_item,'base_odds':odds,'main':main,'normal_outline':'#d5cbbd',
            'normal_outline_width':1,'base_fill':fill})
        c.tag_bind(tag,'<Button-1>',lambda _e,bt=bet_type:self.place_bet(bt))
        c.tag_bind(tag,'<Button-3>',lambda _e,bt=bet_type:self.clear_single_bet(bt))

    def place_bet(self, bet_type, amount=None, record_undo=True):
        if bet_type == 'Banker' and (self.bet_state.current_area_bet('Player1') or self.bet_state.current_area_bet('Player2')):
            messagebox.showwarning('下注冲突','庄家与玩家区域不能同时下注。',parent=self.winfo_toplevel()); return False
        if bet_type in ('Player1','Player2') and self.bet_state.current_area_bet('Banker'):
            messagebox.showwarning('下注冲突','玩家与庄家区域不能同时下注。',parent=self.winfo_toplevel()); return False
        if bet_type != 'Banker':
            return self.place_base_bet(bet_type, amount, record_undo)
        if not self.accept_bets or self.animation_running or self.settlement_running: return False
        unit=float(amount if amount is not None else self.selected_chip); total=unit*2
        if total<100 or abs(total/100-round(total/100))>1e-9: return False
        if self.balance<total or self.bet_state.total_at_risk()+total>self.MAX_TABLE_BET or self.bet_state.current_area_bet('Banker')+total>self.bet_limit_for('Banker'):
            messagebox.showwarning('下注限制','余额或下注限额不足。',parent=self.winfo_toplevel()); return False
        key=('Banker',None); self.pending_bet_visual_amounts[key]=self.pending_bet_visual_amounts.get(key,0)+total
        self.bet_state.add_bet('Banker',total); self.balance-=total
        if record_undo:self.undo_stack.append(('Banker',None,total))
        self.summary_mode='bet'; self.update_display(); source=self._chip_rack_source_position()
        x0,y0,x1,y1=self.bet_spots[key]['bounds']; completed=[0]
        def done():
            completed[0]+=1
            if completed[0]==2:self._complete_pending_bet_visual(key,total)
        self._animate_amount_chip(unit,source,(x0+(x1-x0)*.25,(y0+y1)/2),done)
        self._animate_amount_chip(unit,source,(x0+(x1-x0)*.75,(y0+y1)/2),done)
        self.save_balance(); return True

    def repeat_last_bets(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or not self.last_round_bets): return
        repeatable=[(bt,param,amount) for bt,param,amount in self.last_round_bets
                    if (bt,None) in self.bet_spots]
        required=sum(amount for _bt,_param,amount in repeatable)
        self.clear_bets()
        if self.balance<required:
            messagebox.showwarning('余额不足','余额不足以重复上局下注。',parent=self.winfo_toplevel()); return
        for bet_type,_param,amount in repeatable:
            # 庄家历史保存的是两手合计；place_bet 接收的是单手筹码面额。
            self.place_bet(bet_type,amount=amount/2 if bet_type=='Banker' else amount,record_undo=True)

    def show_game_instructions(self):
        """三公完整图解说明，文字通过 \\n 明确分行。"""
        import os
        import tkinter as tk

        try:
            from PIL import Image, ImageTk
        except ImportError:
            Image = ImageTk = None

        parent = self.winfo_toplevel()
        current = getattr(self, "_game_instruction_dialog", None)

        if current is not None:
            try:
                if current.winfo_exists():
                    current.lift()
                    current.focus_force()
                    return
            except tk.TclError:
                pass

        BG = "#faf5e8"
        HEADER = "#f1e7cd"
        SIDEBAR = "#f2e8d0"
        PANEL = "#fffdf7"
        PANEL_2 = "#f5ecd6"
        BORDER = "#c9b88a"
        GOLD = "#a8842c"
        GOLD_BAR = "#e7d36c"
        TEXT = "#3a2f1e"
        MUTED = "#7a6a50"

        font_name = getattr(self, "cn_font", "Microsoft YaHei UI")

        dialog = tk.Toplevel(parent)
        self._game_instruction_dialog = dialog
        dialog.title("三公 · 完整图解玩法")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(parent)

        width, height = 1000, 670
        parent.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw = max(1, parent.winfo_width())
        ph = max(1, parent.winfo_height())
        x = max(0, px + (pw - width) // 2)
        y = max(0, py + (ph - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        def card_images(*items):
            return ("__CARD_IMAGES__", items)

        manual_pages = [
            (
                "玩法",
                "玩家1、玩家2与庄家各持三张牌。\n"
                "两位玩家分别与庄家比较，按下注区域独立结算。",
                [
                    (
                        "游戏目标",
                        "",
                        [
                            (
                                "两位玩家分别对战庄家",
                                "使用一副不含大小王的52张扑克牌。\n"
                                "玩家1、庄家、玩家2各获三张牌，每局共发九张。\n"
                                "玩家1与玩家2分别对战庄家，不互相比牌。\n"
                                "牌靴剩余不足九张时，下一局发牌前重新洗牌。"
                            ),
                            (
                                "主注与边注",
                                "主注可选择玩家1、玩家2或庄家。\n"
                                "玩家1与玩家2主注可以同时下注。\n"
                                "任一玩家主注均不能与庄家主注同时存在。\n"
                                "\n"
                                "对子+、玩家平局及三公属于独立边注。\n"
                                "边注可以单独购买，不要求先下主注。"
                            ),
                        ],
                        [],
                    ),
                    (
                        "一局如何进行",
                        "",
                        [
                            (
                                "① 设置下注",
                                "先选择筹码，再左键点击下注区域。\n"
                                "下注成功时立即扣除余额。\n"
                                "开牌前可右键清除单一区域。\n"
                                "点击“清除”可退回全部未开牌下注。"
                            ),
                            (
                                "② 开始发牌",
                                "点击“开牌”或按Enter开始。\n"
                                "依玩家1、庄家、玩家2的顺序轮流发牌。\n"
                                "每方各获三张牌。\n"
                                "发牌与结算期间不能修改下注。"
                            ),
                            (
                                "③ 自动比牌",
                                "三张牌发齐后，判断最终牌型。\n"
                                "先比较牌型，再比较该牌型规定的数值。\n"
                                "无需换牌、弃牌或追加下注。"
                            ),
                            (
                                "④ 分项结算",
                                "两手主注分别结算，边注独立判奖。\n"
                                "结算后下注板先轮转。\n"
                                "上方牌区在下一次开牌时再轮转。"
                            ),
                        ],
                        [],
                    ),
                    (
                        "点数如何计算",
                        "",
                        [
                            (
                                "三张牌相加，只取个位数",
                                "A计1点，2至9按牌面计点。\n"
                                "10、J、Q、K均计0点。\n"
                                "三张牌的点数相加后，只取个位数。\n"
                                "\n"
                                "例如：7＋8＋3＝18，最终为8点。\n"
                                "J、Q、K称为公牌，10不属于公牌。"
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                "下注 & 限红",
                "常规筹码以$100为单位。\n"
                "全桌下注总额最高$2,000,000。",
                [
                    (
                        "下注项目与限额",
                        "",
                        [],
                        [
                            (
                                "各区限红",
                                ["项目", "最高下注", "作用"],
                                [
                                    [
                                        "玩家1／玩家2\n主注",
                                        "每区$500,000",
                                        "对应玩家\n与庄家比牌",
                                    ],
                                    [
                                        "庄家主注",
                                        "合计$500,000\n每手$250,000",
                                        "平均分为两手\n分别对战两位玩家",
                                    ],
                                    [
                                        "对子+",
                                        "每区$50,000",
                                        "玩家1、玩家2\n及庄家均可下注",
                                    ],
                                    [
                                        "玩家平局",
                                        "每区$50,000",
                                        "对应玩家与庄家\n满足平局边注条件",
                                    ],
                                    [
                                        "三公",
                                        "每区$50,000",
                                        "玩家1、玩家2\n及庄家均可下注",
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        "下注操作",
                        "",
                        [
                            (
                                "添加与清除筹码",
                                "左键选择筹码，再左键点击下注区增加金额。\n"
                                "右键清除对应区域，并退回该区下注。\n"
                                "“清除”退回本局全部尚未开牌的下注。"
                            ),
                            (
                                "庄家下注同时投入两手",
                                "点击庄家主注时，两手各投入一枚所选筹码。\n"
                                "\n"
                                "例如选择$100筹码，再点击一次庄家区：\n"
                                "对玩家1下注$100，对玩家2下注$100。\n"
                                "本次合计扣除$200。\n"
                                "\n"
                                "清除庄家主注时，两手会一并清除。"
                            ),
                            (
                                "余额或限额不足",
                                "玩家主注及边注会根据余额和剩余限额，\n"
                                "以$100整数倍加入本次可下注金额。\n"
                                "\n"
                                "庄家主注必须能够完整投入两手金额。\n"
                                "余额或限额不足时，本次庄家下注不成立。"
                            ),
                            (
                                "重复下注",
                                "点击“重复下注”后，先清除当前下注，\n"
                                "再按保存的上次下注金额恢复。\n"
                                "\n"
                                "庄家记录的是两手合计金额，恢复时不会翻倍。\n"
                                "若清除当前下注后的余额仍不足，\n"
                                "不会恢复上次下注。"
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                "获胜条件 & 赔率",
                "净赔率不包含本金。\n"
                "中奖返还＝下注金额×（净赔率＋1）。",
                [
                    (
                        "主注结算",
                        "庄家总下注平均分为两手。\n"
                        "每手分别使用总下注的一半进行结算。",
                        [
                            (
                                "比较顺序",
                                "先判断庄家是否为“破煞”。\n"
                                "再判断对应玩家是否为“发发发”。\n"
                                "其余情况先比牌型，再比该牌型规定的数值。\n"
                                "\n"
                                "比较结果完全相同时：\n"
                                "玩家主注输，庄家主注赢。"
                            ),
                        ],
                        [
                            (
                                "玩家主注",
                                ["情形", "净赔率", "含本金返还"],
                                [
                                    ["普通获胜", "0.95:1", "下注×1.95"],
                                    ["发发发获胜", "88:1", "下注×89"],
                                    ["落败或主注平局", "输", "0"],
                                    ["庄家破煞", "输", "0"],
                                ],
                            ),
                            (
                                "庄家主注：每手分别计算",
                                ["情形", "净赔率", "该手返还"],
                                [
                                    [
                                        "庄家破煞",
                                        "1:1",
                                        "该手下注×2",
                                    ],
                                    [
                                        "庄家赢或平局\n普通点数0～4点",
                                        "0.5:1",
                                        "该手下注×1.5",
                                    ],
                                    [
                                        "庄家赢或平局\n其他牌型或\n普通5～9点",
                                        "1:1",
                                        "该手下注×2",
                                    ],
                                    [
                                        "输给普通玩家牌",
                                        "输",
                                        "0",
                                    ],
                                    [
                                        "输给玩家发发发",
                                        "输本金\n另扣88倍",
                                        "返还0\n另扣该手下注×88",
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        "对子+",
                        "只使用所下注一方自己的三张牌。\n"
                        "不要求主注获胜。",
                        [
                            (
                                "独立判断牌型",
                                "按赔率表从高到低，只赔最高符合项目一次。\n"
                                "此表仅用于对子+，不是三公主注的牌型顺序。\n"
                                "\n"
                                "A-2-3与Q-K-A均算顺子。\n"
                                "K-A-2不算顺子。\n"
                                "同花Q-K-A按同花顺40:1赔付。"
                            ),
                        ],
                        [
                            (
                                "对子+赔率表",
                                ["牌型", "净赔率", "含本金返还"],
                                [
                                    ["同花顺", "40:1", "下注×41"],
                                    ["三条", "30:1", "下注×31"],
                                    ["顺子", "6:1", "下注×7"],
                                    ["同花", "3:1", "下注×4"],
                                    ["对子", "1:1", "下注×2"],
                                    ["其他", "不中奖", "0"],
                                ],
                            ),
                        ],
                    ),
                    (
                        "玩家平局",
                        "玩家1与玩家2分别有对应的平局下注区。",
                        [
                            (
                                "必须同时满足三个条件",
                                "① 平局边注评估的牌型等级相同。\n"
                                "② J、Q、K的张数相同。\n"
                                "③ 三张牌总点数取个位后相同。\n"
                                "\n"
                                "此边注不比较最大单张或对子大小。\n"
                                "平局边注中奖，不代表主注比较结果为平局。"
                            ),
                            (
                                "特殊牌的评估方式",
                                "按当前代码，平局边注评估玩家8-8-8时，\n"
                                "不启用“发发发”特殊等级，而按对子等级处理。\n"
                                "\n"
                                "庄家4-4-4仍按“破煞”等级处理。"
                            ),
                        ],
                        [
                            (
                                "玩家平局赔率表",
                                ["结果", "净赔率", "含本金返还"],
                                [
                                    ["三个条件均满足", "24:1", "下注×25"],
                                    ["任一条件不满足", "不中奖", "0"],
                                ],
                            ),
                        ],
                    ),
                    (
                        "三公边注",
                        "只使用所下注一方自己的三张牌。",
                        [
                            (
                                "三张必须全是公牌",
                                "三张均为J、Q或K即中奖，允许点数重复。\n"
                                "大三公与小三公均符合，混三公不符合。\n"
                                "\n"
                                "若同时购买对子+与三公边注，\n"
                                "两项可以分别中奖。"
                            ),
                        ],
                        [
                            (
                                "三公边注赔率表",
                                ["结果", "净赔率", "含本金返还"],
                                [
                                    ["三张均为J／Q／K", "70:1", "下注×71"],
                                    ["其他", "不中奖", "0"],
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            (
                "牌型等级表",
                "以下顺序用于三公主注。\n"
                "特殊牌优先于常规牌型。",
                [
                    (
                        "特殊牌与五种常规牌型",
                        "由强到弱排列。\n"
                        "图片为示例，不代表唯一组成方式。",
                        [],
                        [
                            (
                                "牌型与牌例",
                                ["牌型", "判定条件", "牌例"],
                                [
                                    [
                                        "破煞",
                                        "仅庄家4-4-4\n最高优先级",
                                        card_images(
                                            ("♠", "4"), ("♥", "4"), ("♦", "4")
                                        ),
                                    ],
                                    [
                                        "发发发",
                                        "仅玩家8-8-8\n仅输庄家破煞",
                                        card_images(
                                            ("♠", "8"), ("♥", "8"), ("♦", "8")
                                        ),
                                    ],
                                    [
                                        "大三公",
                                        "三张同点公牌",
                                        card_images(
                                            ("♠", "K"), ("♥", "K"), ("♦", "K")
                                        ),
                                    ],
                                    [
                                        "小三公",
                                        "三张均为公牌\n但不全同点",
                                        card_images(
                                            ("♠", "K"), ("♥", "Q"), ("♦", "J")
                                        ),
                                    ],
                                    [
                                        "混三公",
                                        "含至少一张公牌\n且总点数为0",
                                        card_images(
                                            ("♠", "K"), ("♥", "6"), ("♦", "4")
                                        ),
                                    ],
                                    [
                                        "对子",
                                        "未符合更高牌型\n至少两张同点",
                                        card_images(
                                            ("♠", "9"), ("♥", "9"), ("♦", "2")
                                        ),
                                    ],
                                    [
                                        "普通点数",
                                        "不符合以上牌型",
                                        card_images(
                                            ("♠", "7"), ("♥", "8"), ("♦", "3")
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        "同牌型如何分胜负",
                        "",
                        [
                            (
                                "牌面大小与花色",
                                "主注比较牌面时：\n"
                                "K＞Q＞J＞10＞9＞…＞2＞A。\n"
                                "A最小，花色不分大小。\n"
                                "\n"
                                "牌面大小与计点数值不同。\n"
                                "例如K计0点，但比较单张时大于9。"
                            ),
                            (
                                "大三公",
                                "比较三张相同公牌的牌面大小。\n"
                                "K-K-K＞Q-Q-Q＞J-J-J。"
                            ),
                            (
                                "小三公与混三公",
                                "同类只比较最大单张。\n"
                                "最大单张相同，即为主注平局。\n"
                                "不再比较第二张及第三张。\n"
                                "\n"
                                "例如K-Q-J与K-J-J均为小三公，\n"
                                "最大单张都是K，因此主注比较结果为平局。"
                            ),
                            (
                                "对子",
                                "先比较重复牌的牌面大小。\n"
                                "重复牌相同，再比较剩余单牌。\n"
                                "\n"
                                "未触发特殊牌或更高牌型的三张同点牌，\n"
                                "在主注中也归入对子等级。\n"
                                "其单牌比较值使用该重复牌的牌面大小。\n"
                                "\n"
                                "例如玩家4-4-4、庄家8-8-8，\n"
                                "均按对子等级处理。"
                            ),
                            (
                                "普通点数",
                                "先比较总点数，9点最大，0点最小。\n"
                                "点数相同，再比较最大单张。\n"
                                "最大单张也相同，即为主注平局。\n"
                                "不再比较其余两张。"
                            ),
                            (
                                "优先判断更高牌型",
                                "例如J-5-5含公牌，且总点数为0。\n"
                                "主注判为混三公，不是对子。\n"
                                "\n"
                                "同花或顺子本身不会提高三公主注等级，\n"
                                "但可以在对子+边注中中奖。"
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                "特别事项",
                "核对特殊牌优先级、界面显示及返还金额。",
                [
                    (
                        "特殊牌与额外扣款",
                        "",
                        [
                            (
                                "破煞优先",
                                "庄家4-4-4通杀两手玩家主注，\n"
                                "包括玩家8-8-8。\n"
                                "\n"
                                "此时庄家两手均返还2倍。\n"
                                "不会触发发发发的额外扣款。\n"
                                "各项边注仍按自身规则独立判奖。"
                            ),
                            (
                                "下注庄家遇到发发发",
                                "庄家不是破煞，对应玩家为8-8-8时：\n"
                                "该手庄家本金落败，\n"
                                "另外扣除该手下注的88倍。\n"
                                "\n"
                                "两位玩家分别判断，另一手照常结算。\n"
                                "最终余额＝下注后余额＋全部返还－额外扣款。\n"
                                "若结果小于0，余额归零。"
                            ),
                        ],
                        [],
                    ),
                    (
                        "界面显示与轮转",
                        "",
                        [
                            (
                                "牌面显示",
                                "发出一至两张时，显示当前点数。\n"
                                "三张发齐后，显示最终牌型。\n"
                                "对子会整理到前两张，整理不改变判定结果。"
                            ),
                            (
                                "中奖提示",
                                "符合中奖条件的下注格会交替闪烁。\n"
                                "即使该格没有下注，也可能闪烁。\n"
                                "实际返还按已下注金额及对应规则计算。"
                            ),
                            (
                                "下一局位置",
                                "结算后下注板先轮转。\n"
                                "上方牌区在下一次开牌时再轮转。\n"
                                "下注时请认准玩家1、玩家2及庄家标签。"
                            ),
                        ],
                        [],
                    ),
                    (
                        "返还与净盈亏示例",
                        "以下示例均未购买边注。",
                        [
                            (
                                "示例一：玩家普通获胜",
                                "玩家1主注$100，普通获胜。\n"
                                "返还：$100×1.95＝$195。\n"
                                "净赢：$195－$100＝$95。"
                            ),
                            (
                                "示例二：庄家低点赢一手、输一手",
                                "庄家总下注$200，每手$100。\n"
                                "庄家为普通4点。\n"
                                "对玩家1获胜，对玩家2落败。\n"
                                "\n"
                                "第一手返还：$100×1.5＝$150。\n"
                                "第二手返还：$0。\n"
                                "合计返还$150，净输$50。\n"
                                "\n"
                                "半赔只适用于庄家普通0～4点赢或平局。\n"
                                "对子、三公及破煞不受此半赔规则影响。"
                            ),
                            (
                                "示例三：玩家发发发获胜",
                                "玩家1主注$100，玩家1为8-8-8。\n"
                                "庄家不是破煞。\n"
                                "\n"
                                "返还：$100×89＝$8,900。\n"
                                "净赢：$8,900－$100＝$8,800。"
                            ),
                            (
                                "示例四：庄家遇到发发发",
                                "庄家总下注$200，每手$100。\n"
                                "对玩家1的发发发落败。\n"
                                "对玩家2按普通全赔规则获胜。\n"
                                "\n"
                                "第一手返还$0，另扣$100×88＝$8,800。\n"
                                "第二手返还$100×2＝$200。\n"
                                "规则净盈亏：$200－$200－$8,800＝－$8,800。\n"
                                "\n"
                                "若余额不足承担扣款，最终余额归零。"
                            ),
                            (
                                "示例五：主注与平局边注分别判断",
                                "玩家：K-6-2；庄家：Q-7-A。\n"
                                "双方均为普通8点，且均有一张公牌。\n"
                                "\n"
                                "主注比较最大单张，K大于Q，因此玩家胜。\n"
                                "平局边注的三个条件仍全部满足。\n"
                                "已购买的平局边注按24:1中奖。"
                            ),
                        ],
                        [],
                    ),
                ],
            ),
        ]

        def close_dialog():
            if getattr(self, "_game_instruction_dialog", None) is dialog:
                self._game_instruction_dialog = None
            try:
                dialog.destroy()
            except tk.TclError:
                pass

        header = tk.Frame(dialog, bg=HEADER, height=76)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="三公 · 完整图解玩法",
            font=(font_name, 20, "bold"),
            fg=GOLD,
            bg=HEADER,
            anchor="w",
        ).place(x=24, y=6, width=795, height=41)

        tk.Label(
            header,
            text="玩法 · 下注 · 获胜条件 · 牌型 · 特别事项",
            font=(font_name, 14),
            fg=MUTED,
            bg=HEADER,
            anchor="w",
        ).place(x=26, y=46)

        tk.Button(
            header,
            text="关闭  ESC",
            command=close_dialog,
            font=(font_name, 14, "bold"),
            bg="#e8dcc0",
            fg=TEXT,
            activebackground="#d9c895",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
        ).place(x=850, y=17, width=120, height=42)

        tk.Frame(dialog, bg=GOLD_BAR, height=3).pack(fill=tk.X)

        body = tk.Frame(dialog, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(body, bg=SIDEBAR, width=205)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="说明目录",
            font=(font_name, 16, "bold"),
            fg=GOLD,
            bg=SIDEBAR,
            anchor="w",
        ).pack(fill=tk.X, padx=18, pady=(17, 10))

        scroll_host = tk.Frame(body, bg=BG)
        scroll_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(
            scroll_host,
            bg=BG,
            highlightthickness=0,
            bd=0,
            yscrollincrement=36,
        )
        scrollbar = tk.Scrollbar(
            scroll_host,
            orient=tk.VERTICAL,
            command=canvas.yview,
            bg="#ded3b7",
            troughcolor=BG,
            activebackground=GOLD_BAR,
            relief=tk.FLAT,
            bd=0,
            width=13,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
            padx=(10, 0),
            pady=10,
        )
        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y,
            padx=(0, 8),
            pady=10,
        )

        content = tk.Frame(canvas, bg=BG)
        content_window = canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )

        def sync_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event):
            canvas.itemconfigure(content_window, width=event.width)

        content.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", fit_content_width)

        game_dir = os.path.dirname(os.path.abspath(__file__))
        search_roots = (
            game_dir,
            os.path.dirname(game_dir),
            os.path.dirname(os.path.dirname(game_dir)),
        )
        card_dir = getattr(self, "card_asset_dir", None)

        if not card_dir or not os.path.isdir(card_dir):
            card_dir = next(
                (
                    os.path.join(root, "A_Tools", "Card", "Poker1")
                    for root in search_roots
                    if os.path.isdir(
                        os.path.join(root, "A_Tools", "Card", "Poker1")
                    )
                ),
                None,
            )

        suits = {
            "♠": "Spade",
            "♥": "Heart",
            "♦": "Diamond",
            "♣": "Club",
        }
        image_cache = {}

        def get_card_photo(suit, rank):
            key = (suit, rank)
            if key in image_cache:
                return image_cache[key]
            if Image is None or ImageTk is None:
                return None

            asset_key = (suits.get(suit, suit), rank)
            source = getattr(self, "external_card_pil", {}).get(asset_key)

            try:
                if source is not None:
                    source = source.copy()
                elif card_dir:
                    path = os.path.join(
                        card_dir, f"{asset_key[0]}{rank}.png"
                    )
                    with Image.open(path) as original:
                        source = original.convert("RGBA")
                else:
                    return None

                resampling = getattr(Image, "Resampling", Image)
                card_height = max(
                    1, round(source.height * 70 / source.width)
                )
                resized = source.resize(
                    (70, card_height), resampling.LANCZOS
                )
                photo = ImageTk.PhotoImage(resized, master=dialog)
            except (OSError, ValueError, tk.TclError):
                return None

            image_cache[key] = photo
            return photo

        def add_rule(parent_frame, title, detail):
            row = tk.Frame(parent_frame, bg=PANEL)
            row.pack(fill=tk.X, padx=16, pady=5)

            tk.Frame(row, bg=GOLD_BAR, width=5).pack(
                side=tk.LEFT, fill=tk.Y, padx=(0, 11)
            )
            text_box = tk.Frame(row, bg=PANEL)
            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

            if title:
                tk.Label(
                    text_box,
                    text=title,
                    font=(font_name, 15, "bold"),
                    fg=TEXT,
                    bg=PANEL,
                    anchor="w",
                    justify=tk.LEFT,
                    wraplength=650,
                ).pack(fill=tk.X)

            if detail:
                tk.Label(
                    text_box,
                    text=detail,
                    font=(font_name, 14),
                    fg=MUTED,
                    bg=PANEL,
                    anchor="w",
                    justify=tk.LEFT,
                    wraplength=650,
                ).pack(fill=tk.X, pady=(3, 0))

        def is_card_cell(value):
            return (
                isinstance(value, (tuple, list))
                and len(value) == 2
                and value[0] == "__CARD_IMAGES__"
            )

        def add_table(parent_frame, title, headers, rows):
            block = tk.Frame(
                parent_frame,
                bg=PANEL_2,
                highlightbackground=BORDER,
                highlightthickness=1,
                bd=0,
            )
            block.pack(fill=tk.X, padx=16, pady=8)

            if title:
                tk.Label(
                    block,
                    text=title,
                    font=(font_name, 14, "bold"),
                    fg=TEXT,
                    bg=GOLD_BAR,
                    anchor="w",
                    justify=tk.LEFT,
                    wraplength=675,
                    padx=11,
                    pady=7,
                ).pack(fill=tk.X)

            grid = tk.Frame(block, bg=PANEL_2)
            grid.pack(fill=tk.X)

            matrix = ([headers] if headers else []) + rows
            count = max((len(row) for row in matrix), default=0)
            if not count:
                return

            # 牌例列预留三张70px扑克牌的空间。
            picture_columns = {
                c
                for row in rows
                for c, value in enumerate(row)
                if is_card_cell(value)
            }

            if count == 3:
                column_widths = (
                    [150, 316, 234]
                    if picture_columns
                    else [280, 180, 240]
                )
            else:
                column_widths = [700 // count] * count
                column_widths[-1] += 700 - sum(column_widths)

            for c, col_width in enumerate(column_widths):
                grid.grid_columnconfigure(c, minsize=col_width)

            for r, row in enumerate(matrix):
                head = bool(headers) and r == 0
                bg = GOLD_BAR if head else (
                    PANEL if r % 2 else "#fbf6e9"
                )

                for c in range(count):
                    value = row[c] if c < len(row) else ""

                    if is_card_cell(value):
                        cell = tk.Frame(
                            grid,
                            bg=bg,
                            borderwidth=1,
                            relief=tk.SOLID,
                        )
                        cell.grid(row=r, column=c, sticky="nsew")

                        for suit, rank in value[1]:
                            photo = get_card_photo(suit, rank)

                            if photo is not None:
                                label = tk.Label(
                                    cell, image=photo, bg=bg, bd=0
                                )
                                label.image = photo
                                label.pack(
                                    side=tk.LEFT, padx=2, pady=3
                                )
                            else:
                                placeholder = tk.Canvas(
                                    cell,
                                    width=70,
                                    height=98,
                                    bg=PANEL,
                                    highlightthickness=0,
                                )
                                placeholder.pack(
                                    side=tk.LEFT, padx=2, pady=3
                                )
                                placeholder.create_rectangle(
                                    1, 1, 69, 97,
                                    fill="white",
                                    outline=BORDER,
                                )
                                placeholder.create_text(
                                    35, 49,
                                    text=f"{rank}\n{suit}",
                                    font=(font_name, 19, "bold"),
                                    fill=(
                                        "#b33131"
                                        if suit in ("♥", "♦")
                                        else "#252525"
                                    ),
                                    justify=tk.CENTER,
                                )
                    else:
                        tk.Label(
                            grid,
                            text=str(value),
                            font=(
                                font_name,
                                14,
                                "bold" if head else "normal",
                            ),
                            fg=TEXT if head else MUTED,
                            bg=bg,
                            anchor="w",
                            justify=tk.LEFT,
                            wraplength=column_widths[c] - 18,
                            padx=7,
                            pady=7,
                            borderwidth=1,
                            relief=tk.SOLID,
                        ).grid(row=r, column=c, sticky="nsew")

        nav_buttons = []

        def render_page(index):
            for child in content.winfo_children():
                child.destroy()

            for idx, button in enumerate(nav_buttons):
                button.configure(
                    bg="#e6d9b9" if idx == index else SIDEBAR,
                    fg=GOLD if idx == index else MUTED,
                )

            page_title, subtitle, page_cards = manual_pages[index]
            top = tk.Frame(content, bg=BG)
            top.pack(fill=tk.X, padx=14, pady=(7, 2))

            tk.Label(
                top,
                text=page_title,
                font=(font_name, 20, "bold"),
                fg=GOLD,
                bg=BG,
                anchor="w",
                justify=tk.LEFT,
                wraplength=690,
            ).pack(fill=tk.X)

            if subtitle:
                tk.Label(
                    top,
                    text=subtitle,
                    font=(font_name, 14),
                    fg=MUTED,
                    bg=BG,
                    anchor="w",
                    justify=tk.LEFT,
                    wraplength=690,
                ).pack(fill=tk.X, pady=(3, 0))

            for card_title, card_subtitle, rules, tables in page_cards:
                card = tk.Frame(
                    content,
                    bg=PANEL,
                    highlightbackground=BORDER,
                    highlightcolor=BORDER,
                    highlightthickness=1,
                    bd=0,
                )
                card.pack(fill=tk.X, padx=10, pady=7)

                head = tk.Frame(card, bg=PANEL)
                head.pack(fill=tk.X, padx=16, pady=(12, 5))

                tk.Label(
                    head,
                    text=card_title,
                    font=(font_name, 16, "bold"),
                    fg=GOLD,
                    bg=PANEL,
                    anchor="w",
                    justify=tk.LEFT,
                    wraplength=680,
                ).pack(fill=tk.X)

                if card_subtitle:
                    tk.Label(
                        head,
                        text=card_subtitle,
                        font=(font_name, 14),
                        fg=MUTED,
                        bg=PANEL,
                        anchor="w",
                        justify=tk.LEFT,
                        wraplength=680,
                    ).pack(fill=tk.X)

                for rule_title, detail in rules:
                    add_rule(card, rule_title, detail)

                for table_title, table_headers, rows in tables:
                    add_table(card, table_title, table_headers, rows)

                tk.Frame(card, bg=PANEL, height=6).pack(fill=tk.X)

            content.update_idletasks()
            sync_scrollregion()
            canvas.yview_moveto(0)

        for index, (page_title, _subtitle, _cards) in enumerate(manual_pages):
            button = tk.Button(
                sidebar,
                text=page_title,
                command=lambda i=index: render_page(i),
                font=(font_name, 14),
                fg=MUTED,
                bg=SIDEBAR,
                activebackground="#e8d49a",
                activeforeground=GOLD,
                relief=tk.FLAT,
                bd=0,
                anchor="w",
                padx=18,
                pady=10,
                cursor="hand2",
            )
            button.pack(fill=tk.X)
            nav_buttons.append(button)

        def on_mousewheel(event):
            if event.delta:
                step = max(1, abs(int(event.delta / 120)))
                canvas.yview_scroll(
                    -step if event.delta > 0 else step,
                    "units",
                )
            return "break"

        def scroll_linux(direction):
            canvas.yview_scroll(direction, "units")
            return "break"

        dialog.bind("<MouseWheel>", on_mousewheel)
        dialog.bind("<Button-4>", lambda _e: scroll_linux(-1))
        dialog.bind("<Button-5>", lambda _e: scroll_linux(1))
        dialog.bind("<Escape>", lambda _e: close_dialog())
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)

        render_page(0)
        dialog.focus_set()
        
    def deal_cards(self):
        if not self.accept_bets or self.animation_running or self.settlement_running: return
        self.canvas.delete('fafa_award')
        self.accept_bets = False; self.animation_running = True
        self.last_round_bets = self.snapshot_bets() or self.last_round_bets
        self.pre_deal_bets = copy.deepcopy(self.bet_state.bets)
        self.undo_stack.clear(); self.pending_bet_visual_amounts.clear(); self.clear_card_display(); self.update_control_states()
        if self.current_result is not None:self._animate_seat_rotation()
        else:self._begin_sangong_deal()

    def _begin_sangong_deal(self):
        self.current_result=self.engine.deal_round(); self.sangong_card_items={s:{} for s in ('Player1','Player2','Banker')}
        self.canvas.itemconfigure(self.animation_phase_text,text='发牌中…'); self._deal_sangong_sequence()

    def _animate_seat_rotation(self):
        moving=list(self.seat_order); wrapped=moving[-1]; steps=25; dx=376/steps
        def frame(step=0):
            if step==1:
                self.canvas.move('seat_zone_'+wrapped,-1128,0)
            for side in moving:
                self.canvas.move('seat_zone_'+side,dx,0)
            if step<steps:self._queue_animation(20,frame,step+1)
            else:
                self.seat_order=list(self.bet_seat_order)
                self.canvas.delete('animation'); self.draw_animation_panel(); self._begin_sangong_deal()
        frame(0)

    def _deal_sangong_sequence(self):
        self.initial_card_ids = []
        order = [(side, index) for index in range(3) for side in self.seat_order]
        def step(position=0):
            if position >= len(order):
                self._queue_animation(160, self._animate_sangong_sort); return
            side, index = order[position]; card = self.current_result['hands'][side][index]
            def arrived(info):
                self._flip_sangong_card(info, card,
                    on_complete=lambda: self._queue_animation(70, step, position + 1))
            self._animate_card_entrance_original(side, index, rotated=False, on_arrive=arrived)
        step()

    def _flip_sangong_card(self, info, card, step=0, on_complete=None):
        side, card_id, index = info; steps = 12
        if step > steps:
            image = self._face_photo(card, rotated=False)
            if image is not None: self.canvas.itemconfigure(card_id, image=image)
            self.revealed_cards[side].append(card); self.canvas.coords(card_id, *self.card_position(side, index))
            self.sangong_card_items[side][index]=card_id
            name=self._current_hand_type(self.revealed_cards[side],side)
            self.canvas.itemconfigure(self.type_texts[side],text=name,fill='#ffe36e' if name in ('破煞','发发发') else 'white')
            self._temp_flip_images.pop(card_id, None)
            if callable(on_complete): on_complete()
            return
        half = steps // 2
        ratio = 1-step/half if step <= half else (step-half)/half
        image = self._create_scaled_flip_image(card, max(1, int(100*ratio)), 140,
                                               use_back=step <= half, rotated=False)
        if image is not None:
            self._temp_flip_images[card_id] = image; self.canvas.itemconfigure(card_id, image=image)
            x, y = self.card_position(side, index); self.canvas.coords(card_id, x+(100-max(1,int(100*ratio)))/2, y)
        self._queue_animation(20, self._flip_sangong_card, info, card, step+1, on_complete)

    def _current_hand_type(self, cards, side):
        if len(cards)==3:
            ev=SangongEngine.evaluate(cards,side)
            if ev['name']=='普通点数':return f"{ev['point']}点"
            if ev['name']=='对子':
                counts=Counter(card[1] for card in cards)
                rank=max((r for r,n in counts.items() if n>=2),key=lambda r:SangongEngine.POWER[r])
                return '对子'+rank
            return ev['name']
        ranks=[card[1] for card in cards]; point=sum(SangongEngine.point_value(r) for r in ranks)%10
        return f'{point}点'

    @staticmethod
    def _display_sort_key(card, counts):
        rank=card[1]; power=SangongEngine.POWER[rank]
        if rank in ('J','Q','K'): group=0
        elif counts[rank]>=2: group=1
        else: group=2
        return (group,-power)

    def _animate_sangong_sort(self):
        hands=self.current_result['hands']; moves=[]
        for side in ('Player1','Player2','Banker'):
            old=list(hands[side]); counts=Counter(card[1] for card in old)
            if 2 in counts.values():
                # 对子牌固定在前两张，单牌固定在最后。
                indexed=sorted(enumerate(old),key=lambda pair:(0 if counts[pair[1][1]]==2 else 1,
                    -SangongEngine.POWER[pair[1][1]]))
            else:
                indexed=sorted(enumerate(old),key=lambda pair:self._display_sort_key(pair[1],counts))
            sorted_hand=[card for _index,card in indexed]
            for target_index,(old_index,_card) in enumerate(indexed):
                item=self.sangong_card_items[side][old_index]; sx,sy=self.canvas.coords(item)[:2]
                tx,ty=self.card_position(side,target_index); moves.append((item,sx,sy,tx,ty))
            hands[side]=sorted_hand
        steps=20
        def frame(n=1):
            ratio=min(1,n/steps)
            for item,sx,sy,tx,ty in moves:self.canvas.coords(item,sx+(tx-sx)*ratio,sy+(ty-sy)*ratio)
            if n<steps:self._queue_animation(30,frame,n+1)
            else:self._queue_animation(120,self.finish_deal)
        frame()

    def finish_deal(self):
        result = self.current_result; hands = result['hands']
        settlement = SangongEngine.settle(self.pre_deal_bets, hands)
        self.settlement_outcomes=copy.deepcopy(settlement['outcomes'])
        self.balance = max(0.0, self.balance + settlement['credit'] - settlement['liability'])
        self.last_win_amount = settlement['credit']; self.last_net = settlement['net']
        for side in ('Player1', 'Banker', 'Player2'):
            name=self._current_hand_type(hands[side],side)
            self.canvas.itemconfigure(self.type_texts[side],text=name,
                                      fill='#ffe36e' if name in ('破煞','发发发') else 'white')
        self._save_sangong_history(result, settlement)
        self.settlement_visual_bets = copy.deepcopy(self.pre_deal_bets)
        self.banker_half_wins = {'Player1':False,'Player2':False}
        self.banker_return_amounts={}; self.flash_return_amounts={}; self.flash_white=False
        self.winning_spot_keys=set()
        for outcome in settlement['outcomes']:
            if outcome['key'][0]=='Banker' and outcome['return_factor']>0:
                self.banker_half_wins[outcome['key'][1]]=True
                self.banker_return_amounts[outcome['key'][1]]=outcome['return_amount']
                self.winning_spot_keys.add(('Banker',None))
            elif outcome['return_factor']>0:
                key=tuple(outcome['key']); self.winning_spot_keys.add(key); self.flash_return_amounts[key]=outcome['return_amount']
        # 闪烁由客观结果决定，不要求该格已有下注。
        for side in ('Player1','Player2'):
            winner,_,_=SangongEngine.compare(hands[side],hands['Banker'],side)
            self.winning_spot_keys.add(('Banker',None) if winner in ('Banker','Tie') else (side,None))
            if SangongEngine.gong_point_tie(hands[side],hands['Banker']):
                self.winning_spot_keys.add((side+' Tie',None))
        for side in ('Player1','Player2','Banker'):
            if SangongEngine.pair_plus_odds(hands[side])>0:
                self.winning_spot_keys.add((side+' PairPlus',None))
            # 三公边注只接受小三公或大三公；混三公不中奖。
            if SangongEngine.evaluate(hands[side],side)['name'] in ('小三公','大三公'):
                self.winning_spot_keys.add((side+' Sangong',None))
        self.flash_winning_keys=set(self.winning_spot_keys)
        self.bet_state.bets.clear(); self.summary_mode = 'win'; self.animation_running = False
        self.settlement_running = True; self.accept_bets = False
        self.canvas.itemconfigure(self.animation_phase_text, text='三公 SANGONG')
        self.update_display(); self.save_balance(); self.settlement_flash_step = 0
        self._show_fafa_settlement(self._flash_sangong)

    def _show_fafa_settlement(self, on_complete):
        hands=self.current_result['hands']; banker_bet=float(self.pre_deal_bets.get('Banker',0.0))
        events=[]
        for side in ('Player1','Player2'):
            is_fafa=SangongEngine.evaluate(hands[side],side)['name']=='发发发'
            player_bet=float(self.pre_deal_bets.get(side,0.0))
            if is_fafa and (banker_bet>0 or player_bet>0):
                events.append((side,(banker_bet/2)*88 if banker_bet>0 else 0.0))
        if not events:
            on_complete(); return
        remaining=[sum(1 for _side,amount in events if amount>0)]
        for side,amount in events:
            self._draw_fafa_badge(side,amount if amount<=0 else None)
        if remaining[0]==0:
            self.after(250,on_complete); return
        def arrived(side,amount):
            self._draw_fafa_liability_chip(side,amount); remaining[0]-=1
            if remaining[0]<=0:self.after(250,on_complete)
        for side,amount in events:
            if amount<=0:continue
            spot=self.bet_spots[(side,None)]; x0,y0,x1,y1=spot['bounds']; target=((x0+x1)/2,y1-55)
            self._animate_amount_chip(amount,self._chip_rack_source_position(),target,
                on_complete=lambda s=side,a=amount:arrived(s,a),role='return')

    def _draw_fafa_badge(self, side, _unused=None):
        spot=self.bet_spots[(side,None)]; x0,y0,x1,y1=spot['bounds']; cx=(x0+x1)/2; cy=y0+72
        self.canvas.create_polygon(cx-92,cy-32,cx+82,cy-32,cx+94,cy-20,cx+94,cy+28,
            cx+82,cy+40,cx-92,cy+40,cx-104,cy+28,cx-104,cy-20,
            fill='#fff2c2',outline='#d6a928',width=3,tags=('fafa_award',))
        self.canvas.create_text(cx-5,cy+4,text='玩家888·发发发\n庄家赔付88倍',justify='center',
            font=('Arial',11,'bold'),fill='#9b1e27',tags=('fafa_award',))
        self.canvas.tag_raise('fafa_award')

    def _draw_fafa_liability_chip(self, side, amount):
        spot=self.bet_spots[(side,None)]; x0,y0,x1,y1=spot['bounds']; x=(x0+x1)/2; y=y1-55; radius=19
        color=self.bet_chip_color(amount); fg=self.contrast_text_color(color)
        self.canvas.create_oval(x-radius,y-radius,x+radius,y+radius,fill='#292522',outline='#151311',tags=('fafa_award',))
        self.canvas.create_oval(x-radius+3,y-radius+3,x+radius-3,y+radius-3,fill=color,outline='#fff2a0',width=2,tags=('fafa_award',))
        self.canvas.create_text(x,y,text=self._compact_amount(amount),font=('Arial',9,'bold'),fill=fg,tags=('fafa_award',))
        self.canvas.tag_raise('fafa_award')

    def _flash_sangong(self):
        if self.settlement_flash_step >= 6:
            self._set_sangong_flash(False)
            self._return_sangong_winnings(); return
        self._set_sangong_flash(self.settlement_flash_step % 2 == 0)
        self.settlement_flash_step += 1
        self.settlement_after_id = self.after(450, self._flash_sangong)

    def _set_sangong_flash(self, white):
        self.flash_white = bool(white)

        for key in self.winning_spot_keys:
            spot = self.bet_spots.get(key)
            if not spot:
                continue

            self.canvas.itemconfigure(
                spot['rect_id'],
                fill=(
                    'white'
                    if white
                    else spot.get(
                        'base_fill',
                        self.BET_COLORS.get(key[0], '#0b4a42')
                    )
                )
            )
            self.canvas.itemconfigure(
                spot['label_item'],
                fill='#111111' if white else 'white'
            )
            self.canvas.itemconfigure(
                spot['odds_item'],
                fill='#111111' if white else 'white'
            )

        # 庄家主注获胜时，“玩家1／玩家2”标识跟随主注格闪烁。
        if ('Banker', None) in self.winning_spot_keys:
            self.canvas.itemconfigure(
                'banker_opponent_label',
                fill='#111111' if white else '#ffd9d9'
            )

        self.update_bet_chips()
        self.canvas.tag_raise('bet_chip_dynamic')

    def _return_sangong_winnings(self):
        winners=[o for o in getattr(self,'settlement_outcomes',[]) if o['return_factor']>0 and o['return_amount']>0]
        self.settlement_visual_bets=None; self.update_bet_chips()
        if not winners:self._finish_sangong_settlement(); return
        remaining=[len(winners)]
        def done():
            remaining[0]-=1
            if remaining[0]<=0:self._finish_sangong_settlement()
        for index,outcome in enumerate(winners):
            bet_type,target_side=outcome['key']; spot=self.bet_spots.get((bet_type,None)); x0,y0,x1,y1=spot['bounds']
            if bet_type=='Banker':
                x=x0+(x1-x0)*(.25 if target_side=='Player1' else .75)
            else:x=(x0+x1)/2
            self._animate_amount_chip(outcome['return_amount'],(x,(y0+y1)/2),self._chip_rack_return_position(index,len(winners)),done,role='return')

    def _finish_sangong_settlement(self):
        self.settlement_after_id=None; self._animate_bet_rotation()

    def _animate_bet_rotation(self):
        moving=list(self.bet_seat_order); wrapped=moving[-1]; steps=25; dx=376/steps
        def frame(step=0):
            if step==1:self.canvas.move('bet_group_'+wrapped,-1128,0)
            for side in moving:self.canvas.move('bet_group_'+side,dx,0)
            if step<steps:self._queue_animation(20,frame,step+1)
            else:
                self.bet_seat_order=[self.bet_seat_order[-1]]+self.bet_seat_order[:-1]
                self.draw_mode_betting_board(); self.settlement_running=False; self.accept_bets=True
                self.canvas.itemconfigure(self.animation_phase_text,text='三公 SANGONG'); self.update_display()
        frame()

    @staticmethod
    def _history_card(card):
        return card[1] + {'Club':'♣','Diamond':'♦','Heart':'♥','Spade':'♠'}[card[0]]

    def _save_sangong_history(self, result, settlement):
        path = self.history_file
        default_stats = {
            'player1_win': 0,
            'dealer_win': 0,
            'player2_win': 0,
            'tie': 0,
            'game': 0,
        }
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError):
            data = {}

        # 兼容旧版把 history_record 保存成整数或其他结构的存档。
        raw_stats = data.get('history_record')
        stats = copy.deepcopy(default_stats)
        if isinstance(raw_stats, dict):
            for key in stats:
                try:
                    stats[key] = max(0, int(raw_stats.get(key, 0)))
                except (TypeError, ValueError):
                    stats[key] = 0
        elif isinstance(raw_stats, (int, float)) and not isinstance(raw_stats, bool):
            stats['game'] = max(0, int(raw_stats))
        data['history_record'] = stats

        history = data.get('history')
        if not isinstance(history, list):
            history = []
            data['history'] = history

        stats['game'] += 1
        comparisons = {}
        hands = result['hands']
        for side, label in (('Player1','player1'),('Player2','player2')):
            winner,_,_ = SangongEngine.compare(hands[side],hands['Banker'],side)
            comparisons[label] = winner
            counter = label+'_win' if winner == side else 'dealer_win' if winner == 'Banker' else 'tie'
            stats[counter] = int(stats.get(counter,0)) + 1
        history.append({
            'game_id':stats['game'],'timestamp':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'seat_order':list(self.seat_order),
            'deck_order':[self._history_card(c) for c in result['deck_order']],
            'player1_cards':[self._history_card(c) for c in hands['Player1']],
            'dealer_cards':[self._history_card(c) for c in hands['Banker']],
            'player2_cards':[self._history_card(c) for c in hands['Player2']],
            'bets':copy.deepcopy(self.pre_deal_bets),
            'result':{'comparisons':comparisons,'winnings':settlement['credit'],
                      'liability':settlement['liability'],'net':settlement['net']}})
        try:
            with open(path,'w',encoding='utf-8') as handle: json.dump(data,handle,ensure_ascii=False,indent=4)
        except OSError: pass
    def _restore_enter_binding(self, event):
        if event.widget is not self:
            return
        binding_id = getattr(self, '_enter_binding_id', None)
        if not binding_id:
            return
        self._enter_binding_id = None
        top = self._enter_window
        try:
            if binding_id in (top.bind('<Return>') or ''):
                top.bind('<Return>', self._previous_enter_binding)
            top.deletecommand(binding_id)
        except tk.TclError:
            pass

    def cancel_pending_callbacks(self):
        for aid in list(self.animation_after_ids)+list(self.chip_motion_after_ids):
            try:self.after_cancel(aid)
            except (tk.TclError,ValueError):pass
        self.animation_after_ids.clear(); self.chip_motion_after_ids.clear()
        if self.settlement_after_id is not None:
            try:self.after_cancel(self.settlement_after_id)
            except (tk.TclError,ValueError):pass
            self.settlement_after_id=None
        try:self.canvas.delete('chip_motion')
        except (tk.TclError,AttributeError):pass
    def on_close(self):self.exit_game()
    def exit_game(self):
        if self._closing:return
        self._closing=True; self.cancel_pending_callbacks(); self.animation_running=False; self.accept_bets=False
        self.balance+=self.bet_state.total_at_risk(); self.bet_state.bets.clear(); self.final_balance=float(self.balance)
        try:self.save_balance()
        except Exception:pass
        if callable(self.on_back):self.on_back(self.final_balance)
        else:
            try:self.winfo_toplevel().destroy()
            except tk.TclError:pass

class SangongGame(SangongV13):
    def __init__(self,root,username=None,initial_balance=10000,on_back=None,on_balance_change=None,game_mode=None):
        super().__init__(root,initial_balance,username,on_back,on_balance_change); self.pack(fill=tk.BOTH,expand=True)
def main(parent=None,balance=10000,user=None,on_back=None,on_balance_change=None,username=None,game_mode=None):
    if username is not None and user is None:user=username
    if parent is not None and not isinstance(parent,tk.Misc):balance=parent; parent=None
    if parent is not None:return SangongV13(parent,balance,user,on_back,on_balance_change)
    root=tk.Tk(); root.title('三公')
    root.geometry('1150x750+50+10'); root.resizable(False,False)
    game=SangongV13(root,balance,user,on_back,on_balance_change); game.pack(fill=tk.BOTH,expand=True)
    root.protocol('WM_DELETE_WINDOW',game.exit_game); root.mainloop(); return game
if __name__=='__main__':main(balance=10_000_000)

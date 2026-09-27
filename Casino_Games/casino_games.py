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


CASINO_GAMES_VERSION = "V26"

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(THIS_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, "A_Tools/Account/saving_data.json")

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


# This page owns all of its translations. index.py passes only a language code.
_TRANSLATION_ROWS = [
    ('← 返回主目录', '← Back to home', '← 返回主目錄', '← Hoki ki te kāinga', '← Reen al hejmo'),
    ('赌场游戏中心', 'Casino Games', '賭場遊戲中心', 'Kēmu whare petipeti', 'Kazinaj ludoj'),
    ('游戏分类', 'Categories', '遊戲分類', 'Ngā kāwai', 'Kategorioj'),
    ('请选择游戏', 'Choose a game', '請選擇遊戲', 'Kōwhiria he kēmu', 'Elektu ludon'),
    ('游戏运行中…', 'Game running…', '遊戲執行中…', 'Kei te haere te kēmu…', 'Ludo funkcias…'),
    ('扑克', 'Poker', '撲克', 'Poker', 'Pokero'),
    ('百家乐', 'Baccarat', '百家樂', 'Baccarat', 'Bakarao'),
    ('黑杰克', 'Blackjack', '黑傑克', 'Blackjack', 'Nigra Joĉjo'),
    ('骰子', 'Dice', '骰子', 'Mataono', 'Ĵetkuboj'),
    ('对决', 'Head-to-head', '對決', 'Whakataetae', 'Duelo'),
    ('轮盘赌', 'Roulette', '輪盤賭', 'Roulette', 'Ruleto'),
    ('地区特色', 'Regional Specialties', '地區特色', 'Ngā Motuhake ā-Rohe', 'Regionaj Specialaĵoj'),
    ('中国', 'China', '中國', 'Haina', 'Ĉinio'),
    ('菲律宾', 'Philippines', '菲律賓', 'Piripīni', 'Filipinoj'),
    ('颜色骰子', 'Color Sicbo', '顏色骰子', 'Sic Bo Tae', 'Kolora Sic Bo'),
    ('乒乓落球', 'Ping Pong Drop', '乒乓落球', 'Poro Tukituki', 'Pingponga Falo'),
    ('红白落球', 'Red White Ball Drop', '紅白落球', 'Poro Whero me te Mā', 'Ruĝ-Blanka Pilka Falo'),
    ('三张牌扑克', 'Three Card Poker', '三張牌撲克', 'Poker Kāri Toru', 'Trikarta Pokero'),
    ('三公', 'San Gong', '三公', 'San Gong', 'San Gong'),
    ('视频扑克', 'Video Poker', '視訊撲克', 'Poker Ataata', 'Videopokero'),
    ('加勒比梭哈扑克', 'Caribbean Stud Poker', '加勒比梭哈撲克', 'Poker Stud Karapīpiana', 'Karibia Stud-Pokero'),
    ('月亮梭哈扑克', 'Lunar Stud Poker', '月亮梭哈撲克', 'Poker Stud Marama', 'Luna Stud-Pokero'),
    ('四张牌扑克', 'Four Card Poker', '四張牌撲克', 'Poker Kāri Whā', 'Kvarkarta Pokero'),
    ('赌场扑克', "Casino Hold'em", '賭場撲克', "Hold'em Whare Petipeti", "Kazina Hold'em"),
    ('DJ Wild梭哈扑克', 'DJ Wild Stud Poker', 'DJ Wild梭哈撲克', 'Poker Stud DJ Wild', 'DJ Wild Stud-Pokero'),
    ('密西西比梭哈扑克', 'Mississippi Stud Poker', '密西西比梭哈撲克', 'Poker Stud Misisipi', 'Misisipa Stud-Pokero'),
    ('纵横交叉扑克', 'Criss Cross Poker', '縱橫交叉撲克', 'Poker Whakawhiti', 'Kruc-Pokero'),
    ('任逍遥扑克', 'Let It Ride Poker', '任逍遙撲克', 'Poker Let It Ride', 'Let It Ride-Pokero'),
    ('单挑扑克', "Heads Up Hold'em", '單挑撲克', "Hold'em Kanohi-ki-te-kanohi", "Duopa Hold'em"),
    ('迷你终极德州扑克', "Mini Ultimate Texas Hold'em", '迷你終極德州撲克', "Texas Hold'em Whakamutunga Iti", "Mini Ultimate Texas Hold'em"),
    ('终极德州扑克', "Ultimate Texas Hold'em", '終極德州撲克', "Texas Hold'em Whakamutunga", "Ultimate Texas Hold'em"),
    ('终极奥马哈扑克', 'Ultimate Omaha', '終極奧馬哈撲克', 'Omaha Whakamutunga', 'Ultimate Omaha'),
    ('内外注', 'In or Out', '內外注', 'Ki Roto, Ki Waho rānei', 'Ene aŭ Ekstere'),
    ('牌九扑克', 'Pai Gow Poker', '牌九撲克', 'Poker Pai Gow', 'Pai Gow-Pokero'),
    ('王牌五张扑克', 'Wild Five Card Poker', '王牌五張撲克', 'Poker Kāri Rima Wild', 'Sovaĝa Kvinkarta Pokero'),
    ('终极三张牌扑克', 'Ultimate Three Card Poker', '終極三張牌撲克', 'Poker Kāri Toru Whakamutunga', 'Ultimate Trikarta Pokero'),
    ('赌场战争', 'Casino War', '賭場戰爭', 'Pakanga Whare Petipeti', 'Kazina Milito'),
    ('我爱同花', 'I Love Suits', '我愛同花', 'E Aroha Ana Au ki ngā Momo Kāri', 'Mi Amas Samkolorojn'),
    ('特殊百家乐', 'Special Baccarat', '特殊百家樂', 'Baccarat Motuhake', 'Speciala Bakarao'),
    ('龙虎斗', 'Dragon Tiger', '龍虎鬥', 'Tarakona me te Taika', 'Drako kaj Tigro'),
    ('龙虎凤', 'Dragon Tiger Phoenix', '龍虎鳳', 'Tarakona, Taika me te Manu Ahi', 'Drako Tigro Fenikso'),
    ('简单黑杰克', 'Easy Blackjack', '簡單黑傑克', 'Blackjack Māmā', 'Facila Nigra Joĉjo'),
    ('经典黑杰克', 'Classic Blackjack', '經典黑傑克', 'Blackjack Tauhira', 'Klasika Nigra Joĉjo'),
    ('双副牌黑杰克', 'Double Deck Blackjack', '雙副牌黑傑克', 'Blackjack Pūkei Takirua', 'Du-Ferdeka Nigra Joĉjo'),
    ('永6 黑杰克', 'Always 6 Blackjack', '永6 黑傑克', 'Blackjack Ono Tonu', 'Ĉiam-6 Nigra Joĉjo'),
    ('西班牙式黑杰克', 'Spanish Blackjack', '西班牙式黑傑克', 'Blackjack Pāniora', 'Hispana Nigra Joĉjo'),
    ('双向黑杰克', 'Breakout Blackjack', '雙向黑傑克', 'Blackjack Breakout', 'Breakout Nigra Joĉjo'),
    ('免费黑杰克', 'Free Blackjack', '免費黑傑克', 'Blackjack Koreutu', 'Senpaga Nigra Joĉjo'),
    ('免牌加倍黑杰克', 'No Card Double Blackjack', '免牌加倍黑傑克', 'Blackjack Whakarua Kāri-Kore', 'Senkarta Duobla Blackjack'),
    ('倍注黑杰克', 'Power Blackjack', '倍注黑傑克', 'Blackjack Mana', 'Potenca Nigra Joĉjo'),
    ('无限加倍黑杰克', 'Unlimited Double Blackjack', '無限加倍黑傑克', 'Blackjack Whakarua Mutunga Kore', 'Senlima Duobla Nigra Joĉjo'),
    ('豪赢黑杰克', 'Multiply Blackjack', '豪贏黑傑克', 'Blackjack Whakarea', 'Multobliga Nigra Joĉjo'),
    ('闪电黑杰克', 'Lightning Blackjack', '閃電黑傑克', 'Blackjack Uira', 'Fulma Nigra Joĉjo'),
    ('投注叠堆黑杰克', 'Bet Stacker Blackjack', '投注疊堆黑傑克', 'Blackjack Tāpae Peti', 'Vet-Stakiga Nigra Joĉjo'),
    ('骰宝', 'Sic Bo', '骰寶', 'Sic Bo', 'Sic Bo'),
    ('超级骰宝', 'Super Sic Bo', '超級骰寶', 'Sic Bo Nui', 'Supera Sic Bo'),
    ('花旗骰', 'Craps', '花旗骰', 'Craps', 'Krapso'),
    ('骰子百家乐', 'Bac Bo', '骰子百家樂', 'Bac Bo', 'Bac Bo'),
    ('德州扑克双人对决', "Texas Hold'em Duel", '德州撲克雙人對決', "Tauwhāinga Texas Hold'em", "Texas Hold'em-Duelo"),
    ('梭哈扑克双人对决', 'Stud Poker Duel', '梭哈撲克雙人對決', 'Tauwhāinga Poker Stud', 'Stud-Pokera Duelo'),
    ('德州扑克彩票购买', "Texas Hold'em Ticket", '德州撲克彩票購買', "Tīkiti Texas Hold'em", "Texas Hold'em-Bileto"),
    ('美式轮盘', 'American Roulette', '美式輪盤', 'Roulette Amerikana', 'Usona Ruleto'),
    ('欧式轮盘', 'European Roulette', '歐式輪盤', 'Roulette Ūropi', 'Eŭropa Ruleto'),
    ('大六之轮', 'Big Six Wheel', '大六之輪', 'Wīra Ono Nui', 'Granda Ses-Rado'),
    ('温州牌九', 'Wenzhou Pai Gow', '溫州牌九', 'Pai Gow Wenzhou', 'Wenzhou Pai Gow'),
    ('经典牌九', 'Classic Pai Gow', '經典牌九', 'Pai Gow Tauhira', 'Klasika Pai Gow'),
    ('经典翻摊', 'Classic Fan Tan', '經典翻攤', 'Fan Tan Tauhira', 'Klasika Fan Tan'),
    ('体验账号不会储存收藏。', 'Guest accounts do not save favorites.', '體驗帳號不會儲存我的最愛。', 'Kāore ngā pūkete manuhiri e tiaki tino pai.', 'Gastaj kontoj ne konservas ŝatatajn ludojn.'),
    ('我的最爱最多只能储存 8 个游戏。', 'Favorites can contain up to 8 games.', '我的最愛最多只能儲存 8 個遊戲。', 'E waru rawa ngā kēmu tino pai ka taea te tiaki.', 'Ŝatataj povas enhavi maksimume 8 ludojn.'),
    ('找不到玩家资料，无法储存收藏。', 'Player data was not found; the favorite could not be saved.', '找不到玩家資料，無法儲存我的最愛。', 'Kāore i kitea ngā raraunga kaitākaro; kāore i tiakina te tino pai.', 'Ludantaj datumoj ne estis trovitaj; la ŝatata ludo ne konserviĝis.'),
    ('维护', 'Maintenance', '維護', 'Tiaki', 'Prizorgado'),
    ('提示', 'Notice', '提示', 'Pānui', 'Avizo'),
    ('越南', 'Vietnam', '越南', 'Whitināmu', 'Vjetnamio'),
    ('越南色碟', 'Xóc đĩa', '越南色碟', 'Xóc đĩa', 'Xóc đĩa'),
    ('游戏运行中', 'Game running', '遊戲執行中', 'Kei te haere te kēmu', 'Ludo funkcias'),
    ('无法打开《{name}》：\n\n{error}', 'Could not open “{name}”:\n\n{error}', '無法開啟《{name}》：\n\n{error}', 'Kāore i taea te whakatuwhera “{name}”:\n\n{error}', 'Ne eblis malfermi “{name}”:\n\n{error}'),
    ('《{name}》目前正在维护。', '“{name}” is under maintenance.', '《{name}》目前正在維護。', 'Kei te tiakina “{name}” ināianei.', '“{name}” estas nun prizorgata.'),
    ('《{name}》没有设置对应的程序模块。', 'No program module is configured for “{name}”.', '《{name}》沒有設定對應的程式模組。', 'Kāore he kōwae papatono kua whakaritea mō “{name}”.', 'Neniu programmodulo estas agordita por “{name}”.'),
    ('{name} 未正常结束：\n\n{error}', '“{name}” did not finish normally:\n\n{error}', '《{name}》未正常結束：\n\n{error}', 'Kāore i mutu tika “{name}”:\n\n{error}', '“{name}” ne finiĝis normale:\n\n{error}'),
    ('{file} 应由项目根目录的 index.py 启动。', 'Open {file} through index.py in the project root.', '{file} 應由專案根目錄的 index.py 啟動。', 'Whakatuwheratia {file} mā te index.py i te pūtake o te kaupapa.', 'Malfermu {file} per index.py en la projekta radiko.'),
]

_TRANSLATIONS = {code: {} for code in ("en", "zh_CN", "zh_TW", "mi", "eo")}
for _source, _en, _zh_tw, _mi, _eo in _TRANSLATION_ROWS:
    for _code, _text in zip(("en", "zh_TW", "mi", "eo"), (_en, _zh_tw, _mi, _eo)):
        _TRANSLATIONS[_code][_source] = _text

_GAME_NAMES = ('百家乐', '黑杰克', '骰子', '对决', '轮盘赌', '地区特色', '中国', '菲律宾', '颜色骰子', '乒乓落球', '红白落球', '三张牌扑克', '三公', '视频扑克', '加勒比梭哈扑克', '月亮梭哈扑克', '四张牌扑克', '赌场扑克', 'DJ Wild梭哈扑克', '密西西比梭哈扑克', '纵横交叉扑克', '任逍遥扑克', '单挑扑克', '迷你终极德州扑克', '终极德州扑克', '终极奥马哈扑克', '内外注', '牌九扑克', '王牌五张扑克', '终极三张牌扑克', '赌场战争', '我爱同花', '特殊百家乐', '龙虎斗', '龙虎凤', '简单黑杰克', '经典黑杰克', '双副牌黑杰克', '永6 黑杰克', '西班牙式黑杰克', '双向黑杰克', '免费黑杰克', '免牌加倍黑杰克', '倍注黑杰克', '无限加倍黑杰克', '豪赢黑杰克', '闪电黑杰克', '投注叠堆黑杰克', '骰宝', '超级骰宝', '花旗骰', '骰子百家乐', '德州扑克双人对决', '梭哈扑克双人对决', '德州扑克彩票购买', '美式轮盘', '欧式轮盘', '大六之轮', '温州牌九', '经典牌九', '经典翻摊', '越南色碟')
_DYNAMIC_PHRASES = {'en': {'已启动：': 'Started: ',
        '已结束，余额已更新': ' finished; balance updated',
        '已关闭': ' closed',
        '已加入我的最爱：': 'Added to favorites: ',
        '已从我的最爱移除：': 'Removed from favorites: ',
        '余额': 'Balance',
        '维护通知': 'Maintenance',
        '目前正在维护。': ' is under maintenance.',
        '启动失败': 'Launch failed',
        '无法打开': 'Could not open ',
        '游戏运行出错': 'Game error',
        '请选择游戏': 'Choose a game',
        '没有设置对应的程序模块。': ' has no program module configured.',
        '请先关闭当前运行中的游戏。': 'Close the running game first.',
        '未正常结束：': ' did not finish normally: '},
 'zh_TW': {'已启动：': '已啟動：',
           '已结束，余额已更新': '已結束，餘額已更新',
           '已关闭': '已關閉',
           '已加入我的最爱：': '已加入我的最愛：',
           '已从我的最爱移除：': '已從我的最愛移除：',
           '余额': '餘額',
           '维护通知': '維護通知',
           '目前正在维护。': '目前正在維護。',
           '启动失败': '啟動失敗',
           '无法打开': '無法開啟',
           '游戏运行出错': '遊戲執行出錯',
           '没有设置对应的程序模块。': '沒有設定對應的程式模組。',
           '请先关闭当前运行中的游戏。': '請先關閉目前執行中的遊戲。',
           '未正常结束：': '未正常結束：'},
 'mi': {'已启动：': 'Kua tīmata: ',
        '已结束，余额已更新': ' kua mutu; kua whakahōutia te toenga',
        '已关闭': ' kua katia',
        '已加入我的最爱：': 'Kua tāpiritia ki ngā tino pai: ',
        '已从我的最爱移除：': 'Kua tangohia i ngā tino pai: ',
        '余额': 'Toenga',
        '维护通知': 'Pānui tiaki',
        '目前正在维护。': ' kei te tiakina ināianei.',
        '启动失败': 'I rahua te tīmata',
        '无法打开': 'Kāore i taea te whakatuwhera ',
        '游戏运行出错': 'Hapa kēmu',
        '没有设置对应的程序模块。': ' kāore he kōwae papatono kua whakaritea.',
        '请先关闭当前运行中的游戏。': 'Katia te kēmu e haere ana i te tuatahi.',
        '未正常结束：': ' kāore i mutu tika: '},
 'eo': {'已启动：': 'Lanĉita: ',
        '已结束，余额已更新': ' finiĝis; saldo ĝisdatigita',
        '已关闭': ' fermiĝis',
        '已加入我的最爱：': 'Aldonita al ŝatataj: ',
        '已从我的最爱移除：': 'Forigita el ŝatataj: ',
        '余额': 'Saldo',
        '维护通知': 'Prizorga avizo',
        '目前正在维护。': ' estas nun prizorgata.',
        '启动失败': 'Lanĉo malsukcesis',
        '无法打开': 'Ne eblis malfermi ',
        '游戏运行出错': 'Luderaro',
        '没有设置对应的程序模块。': ' ne havas agorditan programmodulon.',
        '请先关闭当前运行中的游戏。': 'Unue fermu la rulantan ludon.',
        '未正常结束：': ' ne finiĝis normale: '}}


def normalise_language(value) -> str:
    aliases = {"sc": "zh_CN", "tc": "zh_TW", "zh-cn": "zh_CN", "zh-tw": "zh_TW",
               "zh_cn": "zh_CN", "zh_tw": "zh_TW"}
    code = aliases.get(str(value).lower(), str(value).lower())
    return code if code in _TRANSLATIONS else "en"


def translate_text(text: str, language: str = "en") -> str:
    """Translate this page's UI and game names without importing index.py."""
    text = str(text)
    language = normalise_language(language)
    if language == "zh_CN":
        return text
    translated = _TRANSLATIONS[language].get(text)
    if translated is not None:
        return translated
    if text.startswith("余额  $"):
        labels = {"en": "Balance", "zh_TW": "餘額", "mi": "Toenga", "eo": "Saldo"}
        return f"{labels[language]}  ${text.split('$', 1)[1]}"
    greetings = {
        "en": ("Good morning", "Good morning", "Good afternoon", "Good evening"),
        "zh_TW": ("凌晨好", "早安", "午安", "晚安"),
        "mi": ("Ata mārie", "Ata mārie", "Kia ora i te ahiahi", "Pō mārie"),
        "eo": ("Bonan matenon", "Bonan matenon", "Bonan posttagmezon", "Bonan vesperon"),
    }
    for index, prefix in enumerate(("凌晨好，", "早上好，", "中午好，", "晚上好，")):
        if text.startswith(prefix) and text.endswith("！"):
            name = text[len(prefix):-1]
            if language == "zh_TW":
                return f"{greetings[language][index]}，{name}！"
            return f"{greetings[language][index]}, {name}!"
    # Composite launch/favorite status messages contain this page's game names.
    for source in sorted(_GAME_NAMES, key=len, reverse=True):
        text = text.replace(source, _TRANSLATIONS[language].get(source, source))
    for source, target in sorted(_DYNAMIC_PHRASES[language].items(),
                                 key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, target)
    return text


def greeting_for(username: str) -> str:
    hour = datetime.now().hour
    period = "凌晨好" if hour < 6 else "早上好" if hour < 12 else "中午好" if hour < 18 else "晚上好"
    return f"{period}，{username}！"


def _ui_colour(master: tk.Misc, colour: str) -> str:
    resolver = getattr(master.winfo_toplevel(), "theme_colour", None)
    return resolver(colour) if callable(resolver) else colour


EMBEDDED_GAME_MODULES = {
    "Casino_Games.Mississippi_Stud_Poker",
    "Casino_Games.Criss_Cross_Poker",
    "Casino_Games.Three_Card_Poker",
    "Casino_Games.Ultimate_Omaha_Holdem",
    "Casino_Games.Mini_Ultimate_Texas_Holdem",
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
    "Casino_Games.Sicbo_Super",
    "Casino_Games.Baccarat",
    "Casino_Games.Baccarat_Special",
    "Casino_Games.Dragon_Tiger",
    "Casino_Games.Blackjack_Easy",
    "Casino_Games.Blackjack_Classic",
    "Casino_Games.Blackjack_Spanish",
    "Casino_Games.Blackjack_Double",
    "Casino_Games.Blackjack_Free_Double",
    "Casino_Games.Blackjack_Breakout",
    "Casino_Games.Pai_Gow_Poker",
    "Casino_Games.Texas_Holdem_Ticket",
    "Casino_Games.Blackjack_Double_Up",
    "Casino_Games.Blackjack_Double_Deck",
    "Casino_Games.Wenzhou_Pai_Gow",
    "Casino_Games.Classic_Pai_Gow",
    "Casino_Games.Classic_Fan_Tan",
    "Casino_Games.Blackjack_Lightning",
    "Casino_Games.Blackjack_Easy",
    "Casino_Games.Sangong",
    "Casino_Games.Big_Six_Wheel",
    "Casino_Games.Roulette_American",
    "Casino_Games.Roulette_Europe",
    "Casino_Games.Blackjack_Always6",
    "Casino_Games.Blackjack_Power",
    "Casino_Games.Blackjack_Bet_Stacker",
    "Casino_Games.Color_Sicbo",
    "Casino_Games.Hulog_Bola",
    "Casino_Games.Pula_Puti",
    "Casino_Games.Xóc_Dĩa",
}


# Embedded blackjack pages that use the shared Tk root.  For these games the
# window-manager X button is a page-level Back action to casino_games.
CLOSE_RETURNS_TO_CASINO_MODULES = {
    "Casino_Games.Blackjack_Easy",
    "Casino_Games.Blackjack_Classic",
    "Casino_Games.Blackjack_Spanish",
    "Casino_Games.Blackjack_Double",
    "Casino_Games.Blackjack_Free_Double",
    "Casino_Games.Blackjack_Breakout",
    "Casino_Games.Blackjack_Double_Up",
    "Casino_Games.Blackjack_Double_Deck",
    "Casino_Games.Blackjack_Lightning",
    "Casino_Games.Blackjack_Always6",
    "Casino_Games.Blackjack_Power",
    "Casino_Games.Blackjack_Bet_Stacker",
}

GAME_SECTIONS = {
    "扑克": [
        ("三张牌扑克", "Casino_Games.Three_Card_Poker", False),
        ("三公", "Casino_Games.Sangong", False),
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
        ("迷你终极德州扑克", "Casino_Games.Mini_Ultimate_Texas_Holdem", False),
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
        ("特殊百家乐", "Casino_Games.Baccarat_Special", False),
        ("龙虎斗", "Casino_Games.Dragon_Tiger", False),
        ("龙虎凤", "Casino_Games.Dragon_Tiger_Phoenix", False),
    ],
    "黑杰克": [
        ("简单黑杰克", "Casino_Games.Blackjack_Easy", False),
        ("经典黑杰克", "Casino_Games.Blackjack_Classic", False),
        ("双副牌黑杰克", "Casino_Games.Blackjack_Double_Deck", False),

        ("永6 黑杰克", "Casino_Games.Blackjack_Always6", False),
        ("西班牙式黑杰克", "Casino_Games.Blackjack_Spanish", False),
        ("双向黑杰克", "Casino_Games.Blackjack_Breakout", False),

        ("免费黑杰克", "Casino_Games.Blackjack_Free_Double", False),
        ("免牌加倍黑杰克", "Casino_Games.Blackjack_Double_Up", False),
        ("倍注黑杰克", "Casino_Games.Blackjack_Power", False),

        ("无限加倍黑杰克", "Casino_Games.Blackjack_Double", False),
        ("豪赢黑杰克", "Casino_Games.Blackjack_Multiply", False),
        ("闪电黑杰克", "Casino_Games.Blackjack_Lightning", False),

        ("投注叠堆黑杰克", "Casino_Games.Blackjack_Bet_Stacker", False),
    ],
    "骰子": [
        ("骰宝", "Casino_Games.Sicbo", False),
        ("超级骰宝", "Casino_Games.Sicbo_Super", False),
        ("花旗骰", "Casino_Games.Craps", False),
        ("骰子百家乐", "Casino_Games.BacBo", False),
    ],
    "对决": [
        ("德州扑克双人对决", "Casino_Games.Auto_Texas_Holdem", False),
        ("梭哈扑克双人对决", "Casino_Games.Auto_Stud_Poker", False),
        ("德州扑克彩票购买", "Casino_Games.Texas_Holdem_Ticket", False),
    ],
    "轮盘赌": [
        ("美式轮盘", "Casino_Games.Roulette_American", False),
        ("欧式轮盘", "Casino_Games.Roulette_Europe", False),
        ("大六之轮", "Casino_Games.Big_Six_Wheel", False),
    ],
    "地区特色": [],
}

REGION_SECTIONS = {
    "中国": [
        ("温州牌九", "Casino_Games.Wenzhou_Pai_Gow", False),
        ("经典牌九", "Casino_Games.Classic_Pai_Gow", False),
        ("经典翻摊", "Casino_Games.Classic_Fan_Tan", False),
    ],
    "菲律宾": [
        ("颜色骰子", "Casino_Games.Color_Sicbo", False),
        ("乒乓落球", "Casino_Games.Hulog_Bola", False),
        ("红白落球", "Casino_Games.Pula_Puti", False),
    ],
    "越南": [
        ("越南色碟", "Casino_Games.Xóc_Dĩa", False),
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


class CasinoGamesPage(tk.Frame):
    """嵌入 index.py 唯一根窗口的赌场选择页面。"""

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
        language: Optional[str] = None,
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
        # translator is accepted for compatibility; this page owns its translations.
        self.language = normalise_language(
            language if language is not None else
            getattr(master.winfo_toplevel(), "language", "en")
        )

        self.current_category = "扑克"
        self.process: Optional[subprocess.Popen] = None
        self.result_file: Optional[str] = None
        self.running_game_name = ""

        self.current_region = "中国"
        self.region_buttons: dict = {}
        self._region_tabs_visible = False

        self.balance_var = tk.StringVar()
        self.status_var = tk.StringVar(value=self._tr("请选择游戏"))
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
        return translate_text(text, self.language)

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg=self.PANEL, height=82)
        top.pack(fill="x")
        top.pack_propagate(False)

        title_text = self._tr("赌场游戏中心")
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

        self.region_tabs_frame = tk.Frame(content, bg=self.BG)
        self._build_region_tabs()

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

    def _build_region_tabs(self) -> None:
        """为“地区特色”分类建立中国 / 菲律宾 / 越南三个子页面按钮。"""
        for widget in self.region_tabs_frame.winfo_children():
            widget.destroy()

        self.region_buttons = {}
        for region in REGION_SECTIONS:
            button = tk.Button(
                self.region_tabs_frame,
                text=self._tr(region),
                command=lambda name=region: self._show_region_games(name),
                font=("Microsoft YaHei UI", 12, "bold"),
                bg=self.PANEL_2,
                fg=self.TEXT,
                activebackground=self.HOVER,
                activeforeground=self.GOLD,
                relief="flat",
                padx=26,
                pady=9,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0, 10))
            self.region_buttons[region] = button

    def _show_region_games(self, region: str) -> None:
        """切换地区特色内的中国 / 菲律宾 / 越南子页面。"""
        if self.process is not None:
            return
        self.current_region = region
        for name, button in self.region_buttons.items():
            selected = name == region
            button.config(
                bg=self.PANEL_2 if selected else self.PANEL,
                fg=self.GOLD if selected else self.TEXT,
            )
        self._render_games(REGION_SECTIONS[region])

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
            CasinoGamesPage._bind_to_all_children(child, sequence, callback)

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

        if category == "地区特色":
            # 显示中国 / 菲律宾 / 越南三个按钮（放在游戏网格上方）
            if not self._region_tabs_visible:
                self.region_tabs_frame.pack(
                    fill="x", pady=(0, 12), before=self.games_container
                )
                self._region_tabs_visible = True
            self._show_region_games(self.current_region)
        else:
            # 隐藏地区按钮，按常规分类渲染游戏
            if self._region_tabs_visible:
                self.region_tabs_frame.pack_forget()
                self._region_tabs_visible = False
            self._render_games(GAME_SECTIONS[category])

    def _render_games(self, games: list) -> None:
        """按 3 列网格渲染给定游戏列表，并重建滚动范围。"""
        # 切换时先回到顶部，并清除上一个分类的网格配置。
        self.games_canvas.yview_moveto(0)

        for widget in self.games_frame.winfo_children():
            widget.destroy()

        for column in range(self.games_frame.grid_size()[0]):
            self.games_frame.grid_columnconfigure(column, weight=0, minsize=0)

        for row in range(self.games_frame.grid_size()[1]):
            self.games_frame.grid_rowconfigure(row, weight=0, minsize=0)

        self.game_cards.clear()

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
            language = self.language
            preferences_callback = self.on_preferences
            category = self.current_category
            region = self.current_region

            returned_to_casino = False

            def return_to_casino(final_balance: float) -> None:
                # 同一个关闭动作只允许执行一次，避免 WM_DELETE_WINDOW、Escape
                # 或游戏内部返回按钮在同一时刻重复触发 replace_page()。
                nonlocal returned_to_casino
                if returned_to_casino:
                    return
                returned_to_casino = True

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
                    on_preferences=preferences_callback,
                    language=language,
                )
                new_page.current_region = region
                if new_page.current_category != category:
                    new_page.show_category(category)
                replace_page = getattr(master, "replace_page", None)
                if not callable(replace_page):
                    raise RuntimeError("父窗口没有 replace_page(page) 方法。")
                replace_page(new_page)

            game_kwargs = {
                "parent": master,
                "balance": self.balance,
                "user": username,
                "on_back": return_to_casino,
                "on_balance_change": balance_callback,
            }

            # 这些 Blackjack 模块从 casino_games 进入时，右上角 X
            # 被解释为“返回赌场游戏中心”，而不是关闭整个 Tk 根窗口。
            if module_name in CLOSE_RETURNS_TO_CASINO_MODULES:
                game_kwargs["close_returns_to_parent"] = True

            game_page = game_main(**game_kwargs)

            if not isinstance(game_page, tk.Widget):
                raise TypeError(
                    f"{module_name}.main() 必须返回一个 Tkinter Widget/Frame。"
                )

            self._replace_root_page(game_page)

            # Install the shared-root close protocol only AFTER replace_page().
            # This prevents index.py from overwriting WM_DELETE_WINDOW during the swap.
            if module_name in CLOSE_RETURNS_TO_CASINO_MODULES:
                install_close = getattr(game_page, "_install_embedded_close_handler", None)
                if callable(install_close):
                    install_close()

                    # Re-assert once when Tk becomes idle.  This catches hosts that
                    # defer their own window-protocol setup until after replace_page().
                    try:
                        master.after_idle(lambda: install_close(force=True))
                    except tk.TclError:
                        pass

        except Exception as exc:
            messagebox.showerror(
                self._tr("启动失败"),
                self._tr('无法打开《{name}》：\n\n{error}').format(name=self._tr(display_name), error=f"{type(exc).__name__}: {exc}"),
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
                self._tr("维护通知"),
                self._tr('《{name}》目前正在维护。').format(name=self._tr(display_name)),
                parent=self,
            )
            return

        if not module_name:
            messagebox.showerror(
                self._tr("启动失败"),
                self._tr('《{name}》没有设置对应的程序模块。').format(name=self._tr(display_name)),
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
            messagebox.showerror(self._tr("启动失败"), self._tr(str(exc)), parent=self)
            self.process = None
            return

        self.result_file = result_file
        self.running_game_name = display_name
        self.status_var.set(self._tr(f"已启动：{display_name}"))
        self.running_label.config(text=self._tr("游戏运行中…"))
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
                    self._tr("游戏运行出错"),
                    self._tr('{name} 未正常结束：\n\n{error}').format(name=self._tr(old_name), error=error),
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
                self._tr("游戏运行中"),
                self._tr("请先关闭当前运行中的游戏。"),
                parent=self,
            )
            return
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
    language: Optional[str] = None,
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
        on_preferences=on_preferences,
        translator=translator,
        language=language,
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
        translate_text("提示"),
        translate_text("{file} 应由项目根目录的 index.py 启动。").format(file='casino_games.py'),
        parent=root,
    )
    root.destroy()

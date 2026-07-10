from __future__ import annotations

import json
import secrets
import sys
from dataclasses import dataclass
from typing import List, Sequence


# 扑克牌花色和点数
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


@dataclass(frozen=True)
class Card:
    suit: str
    rank: str

    def __repr__(self) -> str:
        return f"{self.rank}{self.suit}"

    def to_dict(self) -> dict:
        return {"suit": self.suit, "rank": self.rank}


def build_deck(has_joker: bool = False, deck_count: int = 1) -> List[Card]:
    """构造牌组。"""
    if deck_count < 1:
        raise ValueError("deck_count must be >= 1")

    deck: List[Card] = []
    for _ in range(deck_count):
        deck.extend(Card(s, r) for s in SUITS for r in RANKS)
        if has_joker:
            # 保持与原脚本一致：每副牌 1 张 Joker
            deck.append(Card("JOKER", "A"))
    return deck


def fisher_yates_shuffle(deck: Sequence[Card]) -> List[Card]:
    """
    标准 Fisher–Yates 洗牌。

    这是严格均匀的前提是：每次 randbelow(i+1) 都是真正均匀且独立的。
    Python 的 secrets.randbelow() 由系统 CSPRNG 支持，适合该用途。
    """
    cards = list(deck)
    for i in range(len(cards) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        cards[i], cards[j] = cards[j], cards[i]
    return cards


def sattolo_shuffle(deck: Sequence[Card]) -> List[Card]:
    """
    Sattolo 算法：生成无不动点的均匀随机循环排列。

    要求 len(deck) >= 2。若长度为 0 或 1，直接返回原列表（无法避免不动点）。
    算法：与 Fisher–Yates 类似，但随机选择 j 的范围是 [0, i-1]（不包含 i）。
    结果保证没有元素留在原始位置，且所有循环排列等概率出现。
    """
    cards = list(deck)
    n = len(cards)
    if n <= 1:
        # Sattolo 算法在 n<=1 时无法满足无不动点要求，原样返回
        return cards
    for i in range(n - 1, 0, -1):
        # 关键区别：j 从 0 到 i-1（不包括 i）
        j = secrets.randbelow(i)  # 0 <= j <= i-1
        cards[i], cards[j] = cards[j], cards[i]
    return cards


def physical_cut(deck: Sequence[Card]) -> List[Card]:
    """
    随机切牌。

    这是一种“物理感”步骤：把牌堆在随机位置切开并交换上下两段。
    它本身只是一个置换，不会破坏 Fisher–Yates 的均匀性。
    """
    cards = list(deck)
    if len(cards) <= 1:
        return cards

    cut_position = secrets.randbelow(len(cards))
    return cards[cut_position:] + cards[:cut_position]


def extra_independent_mix(deck: Sequence[Card]) -> List[Card]:
    """
    额外独立混洗层。

    这里不模拟有偏的“近似洗牌”，而是再做一次标准 Fisher–Yates。
    这样做不会引入偏差，也不会依赖任何自制随机算法。
    """
    return fisher_yates_shuffle(deck)


def generate_shuffled_deck(
    has_joker: bool = False, deck_count: int = 1, algorithm: str = "fisher"
) -> tuple[List[dict], List[str]]:
    """
    生成洗牌后的牌组。

    参数:
        has_joker: 是否包含 Joker
        deck_count: 牌副数
        algorithm: "fisher" 或 "sattolo"
            - fisher: 原有多层混合 (FY + 切牌 + FY + 切牌)
            - sattolo: 仅使用 Sattolo 洗牌（无额外步骤，保证无不动点）

    返回:
        (cards_dict_list, warnings_list)
    """
    warnings = []
    deck = build_deck(has_joker=has_joker, deck_count=deck_count)

    if algorithm == "sattolo":
        # Sattolo 模式：仅做一次 Sattolo 洗牌，不添加任何额外置换（避免破坏无不动点性质）
        if len(deck) <= 1:
            warnings.append(f"Sattolo algorithm requires at least 2 cards, but got {len(deck)}. Returning original deck.")
        else:
            deck = sattolo_shuffle(deck)
    else:  # default "fisher"
        # 第 1 层：标准 Fisher–Yates
        deck = fisher_yates_shuffle(deck)
        # 第 2 层：物理感切牌
        deck = physical_cut(deck)
        # 第 3 层：再次独立 Fisher–Yates
        deck = extra_independent_mix(deck)
        # 第 4 层：再次切牌
        deck = physical_cut(deck)

    return [card.to_dict() for card in deck], warnings


def parse_args(argv: List[str]) -> tuple[bool, int, str]:
    """
    解析命令行参数：
    argv[1] -> has_joker (true/1/yes)
    argv[2] -> deck_count
    argv[3] -> algorithm (fisher / sattolo)，默认 fisher
    """
    has_joker = False
    deck_count = 1
    algorithm = "fisher"

    if len(argv) > 1:
        has_joker_arg = argv[1].strip().lower()
        if has_joker_arg in {"true", "1", "yes", "y"}:
            has_joker = True

    if len(argv) > 2:
        try:
            deck_count = int(argv[2])
        except ValueError as exc:
            raise ValueError("deck_count must be an integer") from exc

    if len(argv) > 3:
        alg_arg = argv[3].strip().lower()
        if alg_arg in {"sattolo", "s"}:
            algorithm = "sattolo"
        elif alg_arg in {"fisher", "f", "fy"}:
            algorithm = "fisher"
        else:
            raise ValueError(f"Unknown algorithm '{alg_arg}'. Use 'fisher' or 'sattolo'.")

    return has_joker, deck_count, algorithm


def main() -> int:
    try:
        has_joker, deck_count, algorithm = parse_args(sys.argv)
        shuffled_deck, warnings = generate_shuffled_deck(
            has_joker=has_joker, deck_count=deck_count, algorithm=algorithm
        )
        total_cards = len(shuffled_deck)

        # 切牌位置（仅作为额外信息输出，不对牌序产生影响，Sattolo 模式下同样保留该字段）
        cut_position = secrets.randbelow(total_cards) if total_cards > 0 else 0

        output = {
            "deck": shuffled_deck,
            "cut_position": cut_position,
            "has_joker": has_joker,
            "deck_count": deck_count,
            "total_cards": total_cards,
            "algorithm": algorithm,
        }
        if warnings:
            output["warnings"] = warnings

        print(json.dumps(output, ensure_ascii=False))
        return 0

    except Exception as exc:
        # 让错误可审计、可定位，但避免输出不必要的内部细节
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
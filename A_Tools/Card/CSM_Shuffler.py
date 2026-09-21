from __future__ import annotations

"""R5: local 8-deck, 15-chamber continuous shuffler with round cooldown.

The module owns every physical card.  Games lease a complete random chamber,
use cards from that lease, and return dealt cards by their temporary IDs.
State is encrypted on disk with AES-256-GCM and protected by a process lock.
"""

import base64
import json
import os
import secrets
import string
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DECK_COUNT = 8
CSM_RELEASE = "R7-OVERFLOW-LIVE"
OVERFLOW_LIMIT = 58
CHAMBER_COUNT = 15
SUITS = ("Club", "Diamond", "Heart", "Spade")
SUIT_CODES = {"Club": "C", "Diamond": "D", "Heart": "H", "Spade": "S"}
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
TOTAL_CARDS = DECK_COUNT * len(SUITS) * len(RANKS)
STATE_AAD = b"CSM-STATE-V1"


class CSMError(RuntimeError):
    pass


class _ProcessFileLock:
    """Small cross-platform exclusive lock for one fixed lock file."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def _log_failures(operation: str):
    def decorate(function):
        @wraps(function)
        def wrapped(self, *args, **kwargs):
            try:
                return function(self, *args, **kwargs)
            except Exception as exc:
                try:
                    self.log_error(operation, exc)
                except Exception:
                    pass
                # Requirement: any CSM operation error invalidates the old
                # warehouse state. Rebuild once, then re-raise the ORIGINAL
                # exception. Callers must discard their local lease IDs.
                try:
                    self.reset_after_error(operation, exc)
                except Exception as reset_exc:
                    try:
                        self.log_error('RESET_AFTER_ERROR', reset_exc, source_operation=operation)
                    except Exception:
                        pass
                raise
        return wrapped
    return decorate


def _fisher_yates(items: Iterable[dict]) -> List[dict]:
    result = [dict(item) for item in items]
    for index in range(len(result) - 1, 0, -1):
        other = secrets.randbelow(index + 1)
        result[index], result[other] = result[other], result[index]
    return result


def _batch_number(moment: Optional[datetime] = None) -> str:
    """Create ZYHGXWFEDVUCBA from DDMMYYYY (ABCDEFGH) + HHMMSS (UVWXYZ)."""

    moment = moment or datetime.now()
    date_part = moment.strftime("%d%m%Y")
    time_part = moment.strftime("%H%M%S")
    a, b, c, d, e, f, g, h = date_part
    u, v, w, x, y, z = time_part
    combined = a + b + c + u + v + d + e + f + w + x + g + h + y + z
    return combined[::-1]


def _temporary_suffix(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class ContinuousShuffleMachine:
    def __init__(
        self,
        state_path: Optional[os.PathLike] = None,
        key_path: Optional[os.PathLike] = None,
    ):
        root = Path(__file__).resolve().parent
        self.state_path = Path(state_path or root / "A_Logs" / "Json" / "CSM_State.enc")
        self.key_path = Path(key_path or root / "A_Logs" / "Keys" / "CSM_State.key")
        self.lock_path = self.state_path.with_suffix(self.state_path.suffix + ".lock")
        self.error_log_path = self.state_path.with_name("CSM_Error.jsonl")
        self.error_lock_path = self.error_log_path.with_suffix(self.error_log_path.suffix + ".lock")
        self._lock = _ProcessFileLock(self.lock_path)
        if self.state_path.exists() and not self.key_path.exists():
            raise CSMError('已有牌靴但缺少密鑰，不能建立替代密鑰。')
        self._ensure_key()
        try:
            with self._locked_state() as state:
                if not state:
                    state.update(self._new_state())
        except Exception as exc:
            try:
                self.log_error('INIT', exc)
            except Exception:
                pass
            self.reset_after_error('INIT', exc)

    def _ensure_key(self) -> None:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            key = self.key_path.read_bytes()
            if len(key) != 32:
                raise CSMError("CSM key must contain exactly 32 bytes")
            return
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            descriptor = os.open(self.key_path, flags, 0o600)
        except FileExistsError:
            return
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(secrets.token_bytes(32))
            handle.flush()
            os.fsync(handle.fileno())

    def _key(self) -> bytes:
        key = self.key_path.read_bytes()
        if len(key) != 32:
            raise CSMError("Invalid CSM encryption key")
        return key

    def _read_state(self) -> dict:
        if not self.state_path.exists():
            return {}
        try:
            envelope = json.loads(self.state_path.read_text(encoding="utf-8"))
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
            plain = AESGCM(self._key()).decrypt(nonce, ciphertext, STATE_AAD)
            state = json.loads(plain.decode("utf-8"))
        except Exception as exc:
            raise CSMError("CSM state could not be authenticated or decrypted") from exc
        # Version-1 states created before the discard shoe was introduced are
        # upgraded in memory and written in the next normal transaction.
        state.setdefault("discard_shoe", [])
        state.setdefault('round_counter', 0)
        state.setdefault('rounds', {})
        state.setdefault('last_used_round', {})
        state.setdefault('preselected_warehouse', None)
        self._validate_state(state)
        return state

    def _write_state(self, state: dict) -> None:
        self._validate_state(state)
        state["state_version"] = int(state.get("state_version", 0)) + 1
        plain = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self._key()).encrypt(nonce, plain, STATE_AAD)
        envelope = {
            "format": "CSM-STATE",
            "version": 1,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=self.state_path.name + ".", suffix=".tmp", dir=self.state_path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(envelope, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(6):
                try:
                    os.replace(temp_name, self.state_path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise CSMError('STATE_REPLACE_DENIED: Windows 拒絕替換狀態檔，短暫重試後仍失敗；檢查唯讀或佔用。')
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass

    def reset_after_error(self, operation: str = '', error=None) -> None:
        """Delete the old warehouse state and atomically create a fresh 15-chamber shoe.

        The encryption key is retained; all old warehouses, batches, rounds and
        discard references are intentionally invalidated. Games must clear their
        local batch/round IDs after the triggering error.
        """
        with self._lock:
            fresh = self._new_state()
            self._write_state(fresh)

    @contextmanager
    def _locked_state(self):
        with self._lock:
            state = self._read_state()
            before = (
                json.dumps(state, sort_keys=True, separators=(",", ":"))
                if state else None
            )

            if state:
                self._sweep_overflow(state)

            yield state

            if state:
                self._sweep_overflow(state)

                # 只有首次建立牌靴、尚未選定第一倉時才初始化。
                # 已有牌靴的輪詢、歸還、洗牌等操作均不重新選倉。
                if before is None and state.get("preselected_warehouse") is None:
                    self._preselect_warehouse(state)

            after = (
                json.dumps(state, sort_keys=True, separators=(",", ":"))
                if state else None
            )

            if before != after:
                self._write_state(state)

    @staticmethod
    def _sweep_overflow(state):
        """Move >62 cards to the discard tail, in warehouse/list order.

        A drained warehouse ignores old round protection until its next
        successful acquisition. It still needs >=8 cards. Issued batches and
        their card ownership never change during this operation.
        """
        moved = 0
        for warehouse_id in sorted(state['warehouses'], key=int):
            cards = state['warehouses'][warehouse_id]
            if len(cards) <= OVERFLOW_LIMIT:
                continue
            count = len(cards)
            state['discard_shoe'].extend(cards)
            state['warehouses'][warehouse_id] = []
            state.setdefault('overflow_exempt', {})[warehouse_id] = True
            state.setdefault('last_used_round', {}).pop(warehouse_id, None)
            state['last_overflow'] = {
                'warehouse_id': int(warehouse_id), 'cards': count,
                'timestamp': datetime.now().isoformat(timespec='seconds'),
            }
            state['overflow_events'] = state.get('overflow_events', 0) + 1
            state.setdefault('overflow_pending_since', time.time())
            moved += count
        return moved

    def _new_state(self) -> dict:
        number = _batch_number()
        cards = []
        for deck_no in range(1, DECK_COUNT + 1):
            for suit in SUITS:
                for rank in RANKS:
                    permanent_id = f"D{deck_no}-{number}-{rank}{SUIT_CODES[suit]}"
                    cards.append(
                        {
                            "permanent_id": permanent_id,
                            "deck_no": deck_no,
                            "suit": suit,
                            "rank": rank,
                        }
                    )
        cards = _fisher_yates(cards)
        warehouses = {str(index): [] for index in range(1, CHAMBER_COUNT + 1)}
        for card in cards:
            warehouses[str(secrets.randbelow(CHAMBER_COUNT) + 1)].append(card)
        return {
            "format": "CSM-INTERNAL",
            "version": 1,
            "state_version": 0,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "warehouses": warehouses,
            "batches": {},
            "discard_shoe": [],
            "round_counter": 0,
            "rounds": {},
            "last_used_round": {},
            "preselected_warehouse": None,
        }

    @staticmethod
    def _validate_state(state: dict, expected_count=CHAMBER_COUNT) -> None:
        if not state:
            return
        warehouses = state.get("warehouses")
        batches = state.get("batches")
        if not isinstance(warehouses, dict) or set(warehouses) != {str(i) for i in range(1, expected_count+1)}:
            raise CSMError("R5 requires 15 warehouses. 關閉舊版遊戲後執行 migrate_15；不要刪除密鑰或狀態。")
        if not isinstance(batches, dict):
            raise CSMError("Invalid CSM batch table")
        all_cards = []
        for cards in warehouses.values():
            all_cards.extend(cards)
        for batch in batches.values():
            all_cards.extend(batch.get("cards", []))
        discard_shoe = state.get("discard_shoe", [])
        if not isinstance(discard_shoe, list):
            raise CSMError("Invalid discard shoe")
        all_cards.extend(discard_shoe)
        ids = [card.get("permanent_id") for card in all_cards]
        if len(ids) != TOTAL_CARDS or len(set(ids)) != TOTAL_CARDS or None in ids:
            raise CSMError("Card conservation failed: expected 416 unique cards")

    @classmethod
    def migrate_15(cls, root=None):
        """Offline one-time migration; refuse if any old game still holds cards."""
        import shutil
        root = Path(root or Path(__file__).resolve().parent)
        machine = cls.__new__(cls)
        machine.state_path = root/'A_Logs/Json/CSM_State.enc'
        machine.key_path = root/'A_Logs/Keys/CSM_State.key'
        lock = machine.state_path.with_suffix('.enc.lock')
        with _ProcessFileLock(lock):
            envelope = json.loads(machine.state_path.read_text(encoding='utf-8'))
            state = json.loads(AESGCM(machine._key()).decrypt(
                base64.b64decode(envelope['nonce']), base64.b64decode(envelope['ciphertext']), STATE_AAD))
            if len(state.get('warehouses', {})) == 15:
                cls._validate_state(state)
                return '已經是15倉，未修改。'
            cls._validate_state(state, 20)
            if state.get('batches'):
                raise CSMError('MIGRATION_BLOCKED: 舊版仍有外借牌，先用舊版正常退出歸還，禁止自動回收。')
            backup = machine.state_path.with_name('CSM_State.before_R5.'+secrets.token_hex(6)+'.enc')
            shutil.copy2(machine.state_path, backup)
            cards = _fisher_yates(c for group in state['warehouses'].values() for c in group)
            state['warehouses'] = {str(i):[] for i in range(1,16)}
            for card in cards:
                state['warehouses'][str(secrets.randbelow(15)+1)].append(card)
            state.update(round_counter=0, rounds={}, last_used_round={})
            state.setdefault('discard_shoe', [])
            machine._write_state(state)
            return '升級為15倉；保留永久牌號、廢牌、密鑰。備份：'+str(backup)

    @_log_failures("ACQUIRE_CHAMBER")
    def acquire_chamber(self, game_id: str, round_id: str) -> dict:
        if not game_id:
            raise ValueError("game_id is required")

        with self._locked_state() as state:
            round_record = self._round(state, game_id, round_id)
            candidates = self._eligible(state, round_record["number"])

            if not candidates:
                raise CSMError(
                    "NO_ELIGIBLE_CHAMBER: 沒有至少8張且最近三局未使用的牌倉。"
                )

            # 優先使用 JSON 已保存的預選倉。若沒有預選倉，或預選倉已不再
            # 符合本局條件，則立即從當前符合要求的 candidates 隨機選一個。
            # 這樣遊戲要求牌倉時不會因 preselected_warehouse 為空而失敗。
            warehouse_id = str(state.get("preselected_warehouse") or "")
            if warehouse_id not in candidates:
                warehouse_id = str(secrets.choice(candidates))
                state["preselected_warehouse"] = int(warehouse_id)

            cards = state["warehouses"][warehouse_id]
            state["warehouses"][warehouse_id] = []
            state.get("overflow_exempt", {}).pop(warehouse_id, None)
            round_record["used"].append(warehouse_id)
            state["last_used_round"][warehouse_id] = round_record["number"]

            batch_id = "BATCH-" + secrets.token_hex(12).upper()
            issued = []
            stored = []

            for card in cards:
                suffix = _temporary_suffix()
                temp_id = f"{card['permanent_id']}-{suffix}"

                saved = dict(card)
                saved["temporary_id"] = temp_id
                stored.append(saved)

                issued.append({
                    "card_id": temp_id,
                    "permanent_id": card["permanent_id"],
                    "deck_no": card["deck_no"],
                    "suit": card["suit"],
                    "rank": card["rank"],
                })

            state["batches"][batch_id] = {
                "batch_id": batch_id,
                "game_id": game_id,
                "round_id": round_id,
                "warehouse_id": int(warehouse_id),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "cards": stored,
            }

            # 當前倉已取出並建立外借批次，現在才重選下一倉一次。
            self._preselect_warehouse(state)

            # 離開 with 時先完成狀態寫入，然後才回傳給遊戲。
            return {
                "batch_id": batch_id,
                "warehouse_id": int(warehouse_id),
                "cards": issued,
            }

    @_log_failures("RETURN_CARDS")
    def return_cards(self, game_id: str, batch_id: str, card_ids: Iterable[str]) -> dict:
        requested = list(card_ids)
        if len(requested) != len(set(requested)):
            raise CSMError("The same temporary card ID was returned more than once")
        with self._locked_state() as state:
            batch = state["batches"].get(batch_id)
            if batch is None or batch.get("game_id") != game_id:
                raise CSMError("Invalid batch ID or game ID")
            by_temp = {card["temporary_id"]: card for card in batch["cards"]}
            unknown = [card_id for card_id in requested if card_id not in by_temp]
            if unknown:
                raise CSMError("A returned card does not belong to this batch")
            for card_id in requested:
                card = by_temp[card_id]
                batch["cards"].remove(card)
                state["discard_shoe"].append(dict(card))
            # Used cards remain visible in the discard shoe until 30 cards have
            # accumulated.  Then all waiting discards are shuffled and every
            # card independently chooses a random destination warehouse.
            self._mix_discards(state)
            if not batch["cards"]:
                del state["batches"][batch_id]
            return {"returned": len(requested), "batch_closed": batch_id not in state["batches"]}

    @_log_failures("RELEASE_GAME")
    def release_game(self, game_id: str, force_shuffle: bool = False) -> int:
        """Return every unused/used leased card for one local game instance."""

        with self._locked_state() as state:
            batch_ids = [key for key, value in state["batches"].items() if value.get("game_id") == game_id]
            released = 0
            for batch_id in batch_ids:
                batch = state["batches"].pop(batch_id)
                for card in batch["cards"]:
                    state["discard_shoe"].append(dict(card))
                    released += 1
            # Return and forced mixing commit atomically under the same lock.
            self._mix_discards(state, force=force_shuffle)
            for rid in [r for r,v in state.get('rounds', {}).items() if v['game_id'] == game_id]:
                del state['rounds'][rid]
            return released

    @staticmethod
    def _round(state, game_id, round_id):
        record = state.get('rounds', {}).get(round_id)
        if not record or record['game_id'] != game_id:
            raise CSMError('INVALID_ROUND: 牌局不存在或不屬於該遊戲。')
        return record

    @staticmethod
    def _eligible(state, number):
        active = {w for r in state.get('rounds', {}).values() for w in r['used']}
        return [w for w,cards in state['warehouses'].items()
                if len(cards) >= 8 and (
                    state.get('overflow_exempt', {}).get(w, False)
                    or (w not in active and
                        state.get('last_used_round', {}).get(w, -100) <= number - 3))]

    @classmethod
    def _preselect_warehouse(cls, state):
        """Choose and persist the warehouse that the next request must borrow."""
        active_numbers = [record['number'] for record in state.get('rounds', {}).values()]
        number = max(active_numbers, default=state.get('round_counter', 0) + 1)
        candidates = cls._eligible(state, number)
        state['preselected_warehouse'] = int(secrets.choice(candidates)) if candidates else None

    @_log_failures('BEGIN_ROUND')
    def begin_round(self, game_id, buffered_batch=None):
        with self._locked_state() as state:
            if any(r['game_id'] == game_id for r in state['rounds'].values()):
                raise CSMError('上一局尚未關閉。')
            number = state['round_counter'] + 1
            used = []
            if buffered_batch:
                batch = state['batches'].get(buffered_batch)
                if not batch or batch['game_id'] != game_id:
                    raise CSMError('Invalid batch ID or game ID')
                # Continuing a previously issued packet is not a new chamber acquisition.
                used.append(str(batch['warehouse_id']))
            if not buffered_batch and not self._eligible(state, number):
                raise CSMError('NO_ELIGIBLE_CHAMBER: 無可用倉，未建立新局。')
            rid = 'ROUND-' + secrets.token_hex(12)
            state['round_counter'] = number
            state['rounds'][rid] = {'game_id':game_id, 'number':number, 'used':used}
            for w in used:
                state['last_used_round'][w] = number
            return rid

    @_log_failures('END_ROUND')
    def end_round(self, game_id, round_id):
        with self._locked_state() as state:
            self._round(state, game_id, round_id)
            del state['rounds'][round_id]

    @staticmethod
    def _mix_discards(state: dict, force: bool = False) -> int:
        if not state["discard_shoe"] or (not force and len(state["discard_shoe"]) < 30):
            return 0
        discards = _fisher_yates(state["discard_shoe"])
        state["discard_shoe"] = []
        state.pop('overflow_pending_since', None)
        for card in discards:
            clean = {k: v for k, v in card.items() if k != "temporary_id"}
            target = str(secrets.randbelow(CHAMBER_COUNT) + 1)
            cards = state["warehouses"][target]
            cards.insert(secrets.randbelow(len(cards) + 1), clean)
        state["last_discard_mix"] = {"cards": len(discards), "forced": force,
                                     "timestamp": datetime.now().isoformat(timespec="seconds")}
        return len(discards)

    @_log_failures("FORCE_SHUFFLE")
    def force_shuffle(self) -> int:
        """Mix all waiting discards without touching any active game lease."""
        with self._locked_state() as state:
            return self._mix_discards(state, force=True)

    @_log_failures("AVAILABLE_CARDS")
    def available_cards(self) -> int:
        with self._locked_state() as state:
            return sum(len(cards) for cards in state["warehouses"].values())

    @_log_failures("READ_STATUS")
    def status(self) -> dict:
        with self._locked_state() as state:
            return {
                "total_cards": TOTAL_CARDS,
                "available_cards": sum(len(cards) for cards in state["warehouses"].values()),
                "warehouse_counts": {
                    key: len(cards) for key, cards in state["warehouses"].items()
                },
                "active_batches": len(state["batches"]),
                "discard_cards": len(state.get("discard_shoe", [])),
                "state_version": state.get("state_version", 0),
            }

    @_log_failures("ADMIN_SNAPSHOT")
    def admin_snapshot(self) -> dict:
        """Return a detached, read-only view for the local administration UI."""

        with self._locked_state() as state:
            return json.loads(json.dumps(state, ensure_ascii=False))

    @_log_failures('MAINTENANCE')
    def maintenance_snapshot(self):
        """One bounded maintenance tick; launcher calls this every 100 ms.

        Overflow is committed in discard order before the automatic remix.
        Gameplay return/force commands are allowed to mix earlier.
        """
        with self._locked_state() as state:
            pending = state.get('overflow_pending_since')
            if pending is not None and time.time() - pending >= 1.0:
                self._mix_discards(state)
                self._sweep_overflow(state)
            return json.loads(json.dumps(state, ensure_ascii=False))

    def log_error(self, operation: str, error, **context) -> None:
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "level": "ERROR",
            "operation": str(operation),
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context,
        }
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        with _ProcessFileLock(self.error_lock_path):
            with open(self.error_log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def read_error_log(self, limit: int = 2000) -> List[dict]:
        limit = max(1, min(int(limit), 10000))
        if not self.error_log_path.exists():
            return []
        records = []
        with _ProcessFileLock(self.error_lock_path):
            with open(self.error_log_path, "r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        records.append({
                            "timestamp": "",
                            "level": "ERROR",
                            "operation": "LOG_PARSE",
                            "error_type": "JSONDecodeError",
                            "message": f"Error log line {line_number} is damaged",
                            "context": {},
                        })
        return records[-limit:]


def main() -> int:
    try:
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == 'migrate_15':
            print(ContinuousShuffleMachine.migrate_15())
            return 0
        machine = ContinuousShuffleMachine()
        print(json.dumps(machine.status(), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

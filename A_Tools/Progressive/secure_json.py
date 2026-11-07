"""Encrypted Progressive JSON storage; installed after Account's open adapter."""

import base64
import builtins
import io
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from A_Tools.Account.secure_json import _ProcessFileLock


PROGRESSIVE_DIR = Path(__file__).resolve().parent
DATA_PATH = PROGRESSIVE_DIR / "Progressive.json"
KEY_PATH = PROGRESSIVE_DIR / "Progressive.key"
LOCK_PATH = PROGRESSIVE_DIR / "Progressive.json.lock"
AAD = b"POKER-PROGRESSIVE-DATA-V1"
FORMAT = "POKER-PROGRESSIVE-DATA"

_PREVIOUS_OPEN = builtins.open
_INSTALL_GUARD = threading.Lock()
_INSTALLED = False


class ProgressiveStorageError(RuntimeError):
    pass


def _ensure_key():
    PROGRESSIVE_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        key = KEY_PATH.read_bytes()
        if len(key) != 32:
            raise ProgressiveStorageError("Progressive key must contain 32 bytes")
        return key
    if DATA_PATH.exists():
        raise ProgressiveStorageError("Progressive data exists but its key is missing")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        fd = os.open(KEY_PATH, flags, 0o600)
    except FileExistsError:
        return _ensure_key()
    key = secrets.token_bytes(32)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
        f.flush()
        os.fsync(f.fileno())
    return key


def _decrypt():
    try:
        envelope = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if envelope.get("format") != FORMAT or envelope.get("version") != 1:
            raise ValueError("Unsupported Progressive format")
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        plain = AESGCM(_ensure_key()).decrypt(nonce, ciphertext, AAD).decode("utf-8")
        json.loads(plain)
        return plain
    except Exception as exc:
        raise ProgressiveStorageError("Progressive data cannot be decrypted") from exc


def _encrypt_and_replace(plain):
    try:
        json.loads(plain)
    except Exception as exc:
        raise ProgressiveStorageError("Invalid Progressive JSON") from exc
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_ensure_key()).encrypt(nonce, plain.encode("utf-8"), AAD)
    envelope = {
        "format": FORMAT,
        "version": 1,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    fd, temp_name = tempfile.mkstemp(
        prefix=DATA_PATH.name + ".", suffix=".tmp", dir=PROGRESSIVE_DIR
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(6):
            try:
                os.replace(temp_name, DATA_PATH)
                break
            except PermissionError:
                if attempt == 5:
                    raise ProgressiveStorageError("Cannot replace Progressive data")
                time.sleep(0.05 * (attempt + 1))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class _EncryptedTextFile(io.StringIO):
    def __init__(self, mode):
        self._mode = mode
        self._lock = _ProcessFileLock(LOCK_PATH)
        self._lock.__enter__()
        try:
            if "x" in mode and DATA_PATH.exists():
                raise FileExistsError(DATA_PATH)
            if "r" in mode or "+" in mode or "a" in mode:
                if not DATA_PATH.exists():
                    raise FileNotFoundError(DATA_PATH)
                initial = _decrypt()
            else:
                # A failed read in a game must never allow its broad except
                # clause to overwrite an existing, unauthenticated jackpot.
                if DATA_PATH.exists():
                    _decrypt()
                initial = ""
            super().__init__(initial)
            self.name = str(DATA_PATH)
            if "a" in mode:
                self.seek(0, os.SEEK_END)
            elif "w" in mode:
                self.seek(0)
                self.truncate(0)
        except Exception:
            self._lock.__exit__(None, None, None)
            raise

    def writable(self):
        return any(flag in self._mode for flag in ("w", "a", "+", "x"))

    def readable(self):
        return "r" in self._mode or "+" in self._mode

    def close(self):
        if self.closed:
            return
        try:
            if self.writable():
                _encrypt_and_replace(self.getvalue())
        finally:
            super().close()
            self._lock.__exit__(None, None, None)

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            super().close()
            self._lock.__exit__(exc_type, exc, tb)
            return False
        self.close()
        return False


def _is_progressive_file(file):
    if isinstance(file, int):
        return False
    try:
        return Path(file).resolve() == DATA_PATH
    except (TypeError, OSError):
        return False


def _secure_open(file, mode="r", buffering=-1, encoding=None, errors=None,
                 newline=None, closefd=True, opener=None):
    if not _is_progressive_file(file):
        return _PREVIOUS_OPEN(
            file, mode, buffering, encoding, errors, newline, closefd, opener
        )
    if "b" in mode:
        raise ProgressiveStorageError("Progressive data only supports text mode")
    return _EncryptedTextFile(mode)


def install_secure_json():
    global _INSTALLED
    with _INSTALL_GUARD:
        if _INSTALLED:
            return
        _ensure_key()
        builtins.open = _secure_open
        _INSTALLED = True

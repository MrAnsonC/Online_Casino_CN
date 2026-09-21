"""Transparent AES-256-GCM storage for the shared account JSON file.

The encryption envelope, 96-bit random nonce, authenticated additional data,
32-byte key, process lock, and atomic replacement mirror CSM_Shuffler.py.
"""

from __future__ import annotations

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


ACCOUNT_DIR = Path(__file__).resolve().parent
DATA_PATH = ACCOUNT_DIR / "saving_data.json"
KEY_PATH = ACCOUNT_DIR / "saving_data.key"
LOCK_PATH = ACCOUNT_DIR / "saving_data.json.lock"
LEGACY_PATH = ACCOUNT_DIR.parents[1] / "saving_data.json"
ACCOUNT_AAD = b"POKER-ACCOUNT-DATA-V1"

_ORIGINAL_OPEN = builtins.open
_INSTALL_GUARD = threading.Lock()
_INSTALLED = False


class AccountStorageError(RuntimeError):
    """Raised when encrypted account data cannot be safely processed."""


class _ProcessFileLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = _ORIGINAL_OPEN(self.path, "a+b")
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
            return False
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
        return False


def _ensure_key() -> bytes:
    ACCOUNT_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        key = KEY_PATH.read_bytes()
        if len(key) != 32:
            raise AccountStorageError("Account key must contain exactly 32 bytes")
        return key
    if DATA_PATH.exists():
        raise AccountStorageError("Encrypted account data exists but its key is missing")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(KEY_PATH, flags, 0o600)
    except FileExistsError:
        return _ensure_key()
    key = secrets.token_bytes(32)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key)
        handle.flush()
        os.fsync(handle.fileno())
    return key


def _decrypt() -> str:
    try:
        envelope = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if envelope.get("format") != "POKER-ACCOUNT-DATA" or envelope.get("version") != 1:
            raise ValueError("unsupported account envelope")
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        plain = AESGCM(_ensure_key()).decrypt(nonce, ciphertext, ACCOUNT_AAD)
        json.loads(plain.decode("utf-8"))
        return plain.decode("utf-8")
    except Exception as exc:
        raise AccountStorageError(
            "Account data could not be authenticated or decrypted"
        ) from exc


def _encrypt_and_replace(plain_text: str) -> None:
    try:
        json.loads(plain_text)
    except Exception as exc:
        raise AccountStorageError("Refusing to save invalid account JSON") from exc

    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_ensure_key()).encrypt(
        nonce, plain_text.encode("utf-8"), ACCOUNT_AAD
    )
    envelope = {
        "format": "POKER-ACCOUNT-DATA",
        "version": 1,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    descriptor, temp_name = tempfile.mkstemp(
        prefix=DATA_PATH.name + ".", suffix=".tmp", dir=ACCOUNT_DIR
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(envelope, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(6):
            try:
                os.replace(temp_name, DATA_PATH)
                break
            except PermissionError:
                if attempt == 5:
                    raise AccountStorageError(
                        "Windows denied replacement of encrypted account data"
                    )
                time.sleep(0.05 * (attempt + 1))
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


class _EncryptedTextFile(io.StringIO):
    def __init__(self, mode: str):
        self._mode = mode
        self._lock = _ProcessFileLock(LOCK_PATH)
        self._lock.__enter__()
        try:
            if "r" in mode or "+" in mode or "a" in mode:
                if not DATA_PATH.exists():
                    raise FileNotFoundError(DATA_PATH)
                initial = _decrypt()
            else:
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


def _is_account_file(file) -> bool:
    if isinstance(file, int):
        return False
    try:
        return Path(file).resolve() == DATA_PATH
    except (TypeError, OSError):
        return False


def _secure_open(file, mode="r", buffering=-1, encoding=None, errors=None,
                 newline=None, closefd=True, opener=None):
    if not _is_account_file(file):
        return _ORIGINAL_OPEN(
            file, mode, buffering, encoding, errors, newline, closefd, opener
        )
    if "b" in mode:
        raise AccountStorageError("Encrypted account storage only supports text mode")
    if "x" in mode and DATA_PATH.exists():
        raise FileExistsError(DATA_PATH)
    return _EncryptedTextFile(mode)


def _migrate_legacy_file() -> None:
    with _ProcessFileLock(LOCK_PATH):
        if DATA_PATH.exists() or not LEGACY_PATH.exists():
            return
        plain_text = LEGACY_PATH.read_text(encoding="utf-8")
        _encrypt_and_replace(plain_text)
        LEGACY_PATH.unlink()


def install_secure_json() -> None:
    """Install the narrow open() adapter and migrate the old plaintext once."""
    global _INSTALLED
    with _INSTALL_GUARD:
        if _INSTALLED:
            return
        _ensure_key()
        _migrate_legacy_file()
        builtins.open = _secure_open
        _INSTALLED = True


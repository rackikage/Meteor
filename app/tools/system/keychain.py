"""Keychain / Credential Management — secure OS-level credential storage."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class KeychainError(Exception):
    pass


class KeychainManager:
    def __init__(self, fallback_path: Optional[str] = None) -> None:
        self._platform = {"Darwin": "macos", "Linux": "linux"}.get(os.uname().sysname, "unknown")
        self._fallback_path = fallback_path or os.path.expanduser("~/.meteor/keychain.enc")
        self._use_fallback = not self._check_native()

    def _check_native(self) -> bool:
        try:
            if self._platform == "macos":
                subprocess.run(["security", "--version"], capture_output=True, timeout=3)
                return True
            elif self._platform == "linux":
                subprocess.run(["secret-tool", "--version"], capture_output=True, timeout=3)
                return True
        except FileNotFoundError:
            pass
        return False

    def store(self, service: str, account: str, secret: str) -> bool:
        try:
            if self._platform == "macos" and not self._use_fallback:
                subprocess.run(["security", "delete-generic-password", "-s", service, "-a", account], capture_output=True, check=False, timeout=5)
                subprocess.run(["security", "add-generic-password", "-s", service, "-a", account, "-w", secret], capture_output=True, check=True, timeout=5)
            elif self._platform == "linux" and not self._use_fallback:
                # secret-tool store requires --label; without it, the process
                # exits with rc=2 and the secret is never persisted.
                label = f"{service}/{account}"
                proc = subprocess.Popen(
                    ["secret-tool", "store", "--label", label,
                     "service", service, "account", account],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                out, err = proc.communicate(secret.encode("utf-8"), timeout=5)
                if proc.returncode != 0:
                    raise KeychainError(f"secret-tool store failed: {err.decode(errors='replace').strip()}")
            else:
                self._store_fallback(service, account, secret)
            logger.info("Stored credential: %s/%s", service, account)
            return True
        except Exception as e:
            raise KeychainError(f"Failed to store: {e}") from e

    def retrieve(self, service: str, account: str) -> Optional[str]:
        try:
            if self._platform == "macos" and not self._use_fallback:
                result = subprocess.run(["security", "find-generic-password", "-s", service, "-a", account, "-w"], capture_output=True, text=True, timeout=5)
                return result.stdout.strip() if result.returncode == 0 else None
            elif self._platform == "linux" and not self._use_fallback:
                result = subprocess.run(
                    ["secret-tool", "lookup", "service", service, "account", account],
                    capture_output=True, text=True, timeout=5,
                )
                return result.stdout.strip() if result.returncode == 0 else None
            else:
                return self._retrieve_fallback(service, account)
        except Exception as e:
            logger.error("Retrieve failed: %s", e)
            return None

    def delete(self, service: str, account: str) -> bool:
        try:
            if self._platform == "macos" and not self._use_fallback:
                subprocess.run(["security", "delete-generic-password", "-s", service, "-a", account], capture_output=True, check=False, timeout=5)
            elif self._platform == "linux" and not self._use_fallback:
                subprocess.run(
                    ["secret-tool", "clear", "service", service, "account", account],
                    capture_output=True, check=False, timeout=5,
                )
            else:
                self._delete_fallback(service, account)
            return True
        except Exception:
            return False

    def list_services(self) -> list[dict]:
        try:
            if self._platform == "macos" and not self._use_fallback:
                result = subprocess.run(["security", "dump-keychain", "-r"], capture_output=True, text=True, timeout=10)
                entries = []
                for line in result.stdout.splitlines():
                    if '"acct"' in line:
                        entries.append({"account": line.split("=")[-1].strip().strip('"')})
                return entries
            else:
                return self._list_fallback()
        except Exception:
            return []

    def _get_fernet(self):
        from cryptography.fernet import Fernet
        key_file = os.path.expanduser("~/.meteor/keychain.key")
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        # Fernet.generate_key() already returns url-safe base64 bytes; persist
        # and reload them verbatim. (An earlier version base64-decoded on read,
        # producing 32 raw bytes that Fernet rejects — self-heal that here, and
        # regenerate if the key file is empty/corrupt.)
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                key = f.read().strip()
            try:
                return Fernet(key)
            except (ValueError, TypeError):
                logger.warning("Keychain key at %s was invalid — regenerating", key_file)
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        return Fernet(key)

    def _load_fallback_store(self) -> dict:
        if not os.path.exists(self._fallback_path):
            return {}
        f = self._get_fernet()
        try:
            with open(self._fallback_path, "rb") as fh:
                raw = fh.read()
            if not raw:
                return {}
            return json.loads(f.decrypt(raw))
        except Exception as exc:
            # Empty/corrupt/undecryptable store (e.g. key was rotated) — treat as
            # empty and let the next store() rewrite it fresh rather than crash.
            logger.warning("Keychain store unreadable (%s) — starting fresh", exc.__class__.__name__)
            return {}

    def _save_fallback_store(self, store: dict) -> None:
        f = self._get_fernet()
        encrypted = f.encrypt(json.dumps(store).encode())
        os.makedirs(os.path.dirname(self._fallback_path), exist_ok=True)
        with open(self._fallback_path, "wb") as fh:
            fh.write(encrypted)

    def _store_fallback(self, service: str, account: str, secret: str) -> None:
        store = self._load_fallback_store()
        store.setdefault(service, {})[account] = secret
        self._save_fallback_store(store)

    def _retrieve_fallback(self, service: str, account: str) -> Optional[str]:
        return self._load_fallback_store().get(service, {}).get(account)

    def _delete_fallback(self, service: str, account: str) -> None:
        store = self._load_fallback_store()
        if service in store and account in store[service]:
            del store[service][account]
            if not store[service]:
                del store[service]
            self._save_fallback_store(store)

    def _list_fallback(self) -> list[dict]:
        store = self._load_fallback_store()
        entries = []
        for service, accounts in store.items():
            for account in accounts:
                entries.append({"service": service, "account": account})
        return entries

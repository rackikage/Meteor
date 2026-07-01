"""Filesystem Agent — read, write, traverse, and search files."""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
import re
import shutil
import stat as stat_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FilesystemAgent:
    def __init__(self, allowed_dirs: Optional[list[str]] = None, max_file_size: int = 100 * 1024 * 1024) -> None:
        self._allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [os.path.expanduser("~")])]
        self._max_file_size = max_file_size
        self._operation_count: dict[str, int] = {}

    def _resolve(self, path: str) -> Path:
        return Path(path).resolve()

    def read_file(self, path: str, encoding: str = "utf-8") -> str:
        self._operation_count["read_file"] = self._operation_count.get("read_file", 0) + 1
        return self._resolve(path).read_text(encoding)

    def read_binary(self, path: str) -> bytes:
        self._operation_count["read_binary"] = self._operation_count.get("read_binary", 0) + 1
        return self._resolve(path).read_bytes()

    def read_lines(self, path: str, encoding: str = "utf-8") -> list[str]:
        self._operation_count["read_lines"] = self._operation_count.get("read_lines", 0) + 1
        return self._resolve(path).read_text(encoding).splitlines()

    def read_range(self, path: str, start_line: int, end_line: int, encoding: str = "utf-8") -> list[str]:
        lines = self.read_lines(path, encoding)
        return lines[max(0, start_line - 1):end_line]

    def write_file(self, path: str, content: str, encoding: str = "utf-8") -> int:
        self._operation_count["write_file"] = self._operation_count.get("write_file", 0) + 1
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding)
        return len(content)

    def write_binary(self, path: str, content: bytes) -> int:
        self._operation_count["write_binary"] = self._operation_count.get("write_binary", 0) + 1
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return len(content)

    def append_file(self, path: str, content: str, encoding: str = "utf-8") -> int:
        self._operation_count["append_file"] = self._operation_count.get("append_file", 0) + 1
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding=encoding) as f:
            f.write(content)
        return len(content)

    def edit(self, path: str, old_string: str, new_string: str,
             replace_all: bool = False, encoding: str = "utf-8") -> dict:
        """Surgical in-place edit: replace old_string with new_string.

        Unlike write_file (whole-file rewrite), this preserves the rest of the
        file. old_string must be unique unless replace_all=True. Returns a small
        report the model can reason over instead of the whole file."""
        self._operation_count["edit"] = self._operation_count.get("edit", 0) + 1
        p = self._resolve(path)
        text = p.read_text(encoding)
        count = text.count(old_string)
        if count == 0:
            raise ValueError(f"old_string not found in {path}")
        if count > 1 and not replace_all:
            raise ValueError(
                f"old_string is not unique in {path} ({count} matches) — "
                f"add more surrounding context or pass replace_all=true"
            )
        new_text = text.replace(old_string, new_string) if replace_all \
            else text.replace(old_string, new_string, 1)
        p.write_text(new_text, encoding)
        return {"path": str(p), "replacements": count if replace_all else 1,
                "bytes": len(new_text)}

    def glob(self, pattern: str) -> list[str]:
        self._operation_count["glob"] = self._operation_count.get("glob", 0) + 1
        from pathlib import Path as P
        pp = P(pattern)
        if pp.is_absolute():
            if pp.is_dir():
                return sorted([str(f) for f in pp.glob("*")])
            return sorted([str(f) for f in pp.parent.glob(pp.name)])
        if "**" in pattern:
            return sorted([str(f) for f in Path(".").resolve().glob(pattern)])
        return sorted(fnmatch.filter([str(f) for f in Path(".").resolve().rglob("*") if f.is_file()], pattern))

    def grep(self, pattern: str, path: Optional[str] = None, regex: bool = True, max_results: int = 100, include_pattern: Optional[str] = None) -> list[dict]:
        self._operation_count["grep"] = self._operation_count.get("grep", 0) + 1
        search_root = self._resolve(path) if path else self._resolve(".")
        flags = re.MULTILINE | re.DOTALL
        compiled = re.compile(pattern, flags) if regex else re.compile(re.escape(pattern), flags)
        results = []
        files = [search_root] if search_root.is_file() else [f for f in search_root.rglob("*") if f.is_file()]
        for filepath in files:
            if include_pattern and not fnmatch.fnmatch(str(filepath), include_pattern):
                continue
            try:
                if filepath.stat().st_size > self._max_file_size:
                    continue
                text = filepath.read_text("utf-8", errors="replace")
                for lineno, line in enumerate(text.splitlines(), 1):
                    for match in compiled.finditer(line):
                        results.append({"file": str(filepath), "line": lineno, "content": line.strip(), "matched": match.group(), "start": match.start(), "end": match.end()})
                        if len(results) >= max_results:
                            return results
            except (OSError, UnicodeDecodeError):
                continue
        return results

    def list_dir(self, path: str, include_hidden: bool = False) -> list[dict]:
        self._operation_count["list_dir"] = self._operation_count.get("list_dir", 0) + 1
        p = self._resolve(path)
        entries = []
        for entry in p.iterdir():
            if not include_hidden and entry.name.startswith("."):
                continue
            try:
                s = entry.stat()
                entries.append({"name": entry.name, "path": str(entry), "type": "dir" if entry.is_dir() else "file" if entry.is_file() else "other", "size": s.st_size, "modified": datetime.fromtimestamp(s.st_mtime, tz=timezone.utc).isoformat(), "permissions": stat_module.filemode(s.st_mode)})
            except OSError:
                continue
        return sorted(entries, key=lambda e: (e["type"] != "dir", e["name"]))

    def walk(self, path: str, max_depth: int = 10) -> list[str]:
        self._operation_count["walk"] = self._operation_count.get("walk", 0) + 1
        p = self._resolve(path)
        if not p.is_dir():
            return [str(p)]
        result = []
        base_depth = len(p.parts)
        for root, dirs, files in os.walk(str(p)):
            if len(Path(root).parts) - base_depth > max_depth:
                dirs.clear()
                continue
            for name in files:
                result.append(os.path.join(root, name))
        return sorted(result)

    def mkdir(self, path: str, parents: bool = True, exist_ok: bool = True) -> bool:
        self._operation_count["mkdir"] = self._operation_count.get("mkdir", 0) + 1
        self._resolve(path).mkdir(parents=parents, exist_ok=exist_ok)
        return True

    def remove(self, path: str) -> bool:
        self._operation_count["remove"] = self._operation_count.get("remove", 0) + 1
        p = self._resolve(path)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            p.rmdir()
        return not p.exists()

    def remove_tree(self, path: str) -> bool:
        self._operation_count["remove_tree"] = self._operation_count.get("remove_tree", 0) + 1
        shutil.rmtree(str(self._resolve(path)))
        return True

    def copy(self, src: str, dst: str) -> bool:
        self._operation_count["copy"] = self._operation_count.get("copy", 0) + 1
        src_p, dst_p = self._resolve(src), self._resolve(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        if src_p.is_dir():
            shutil.copytree(str(src_p), str(dst_p), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src_p), str(dst_p))
        return dst_p.exists()

    def move(self, src: str, dst: str) -> bool:
        self._operation_count["move"] = self._operation_count.get("move", 0) + 1
        src_p, dst_p = self._resolve(src), self._resolve(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        return dst_p.exists()

    def stat(self, path: str) -> dict:
        self._operation_count["stat"] = self._operation_count.get("stat", 0) + 1
        p = self._resolve(path)
        s = p.stat()
        return {"path": str(p), "exists": p.exists(), "type": "dir" if p.is_dir() else "file" if p.is_file() else "other", "size": s.st_size, "modified": datetime.fromtimestamp(s.st_mtime, tz=timezone.utc).isoformat(), "permissions": stat_module.filemode(s.st_mode), "uid": s.st_uid, "gid": s.st_gid, "is_symlink": p.is_symlink(), "symlink_target": str(p.readlink()) if p.is_symlink() else None}

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def which(self, executable: str) -> Optional[str]:
        return shutil.which(executable)

    def md5(self, path: str) -> str:
        return self._hash(path, "md5")

    def sha256(self, path: str) -> str:
        return self._hash(path, "sha256")

    def _hash(self, path: str, algorithm: str) -> str:
        self._operation_count[f"hash_{algorithm}"] = self._operation_count.get(f"hash_{algorithm}", 0) + 1
        p = self._resolve(path)
        h = hashlib.new(algorithm)
        with p.open("rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def get_stats(self) -> dict:
        return {"operation_counts": dict(self._operation_count), "total_operations": sum(self._operation_count.values()), "allowed_dirs": [str(d) for d in self._allowed_dirs]}

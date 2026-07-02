"""Reverse engineering layer — static analysis helpers for local files."""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Optional


class ReverseEngineeringLayer:
    """Static RE primitives — no execution, no injection."""

    _MAX_READ = 512 * 1024  # 512 KiB for entropy sample
    _MAX_STRINGS_OUT = 200
    _MAX_OUTPUT = 100_000

    def _resolve(self, path: str) -> Path:
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Not a file: {path}")
        return p

    @staticmethod
    def _run(cmd: list[str], *, timeout: float = 120.0) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            return {
                "command": " ".join(cmd),
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:ReverseEngineeringLayer._MAX_OUTPUT],
                "stderr": (proc.stderr or "")[:20_000],
            }
        except subprocess.TimeoutExpired:
            return {"command": " ".join(cmd), "returncode": -1, "stdout": "", "stderr": "timeout"}
        except FileNotFoundError:
            return {"command": " ".join(cmd), "returncode": -1, "stdout": "", "stderr": "binary not installed"}

    @staticmethod
    def _entropy(data: bytes) -> float:
        if not data:
            return 0.0
        counts = Counter(data)
        length = len(data)
        return -sum((c / length) * math.log2(c / length) for c in counts.values())

    def identify(self, path: str) -> dict[str, Any]:
        """File type, size, hashes, and entropy sample."""
        p = self._resolve(path)
        stat = p.stat()
        sample = p.read_bytes()[: self._MAX_READ]
        file_cmd = shutil.which("file") or "file"
        file_out = self._run([file_cmd, "-b", str(p)])

        magic = sample[:16].hex() if sample else ""
        ent = self._entropy(sample)
        packed_hint = ent > 7.2

        return {
            "path": str(p),
            "size_bytes": stat.st_size,
            "file_type": file_out.get("stdout", "").strip(),
            "magic_hex": magic,
            "sha256": hashlib.sha256(sample).hexdigest() if sample else "",
            "entropy_sample": round(ent, 3),
            "likely_packed_or_encrypted": packed_hint,
            "note": "Static metadata only — see docs/reverse-engineering.md for workflow.",
        }

    def strings(self, path: str, min_len: int = 6) -> dict[str, Any]:
        """Extract printable strings (uses `strings` when installed)."""
        p = self._resolve(path)
        binary = shutil.which("strings")
        if binary:
            out = self._run([binary, "-n", str(max(4, int(min_len))), str(p)])
            lines = [ln for ln in out.get("stdout", "").splitlines() if ln.strip()]
        else:
            raw = p.read_bytes()[:2_000_000]
            pattern = rb"[\x20-\x7e]{%d,}" % max(4, int(min_len))
            lines = [m.decode("ascii", errors="replace") for m in re.findall(pattern, raw)]

        interesting = [
            ln for ln in lines
            if any(k in ln.lower() for k in (
                "http", "password", "api", "key", "secret", "cmd", "exec", "shell",
            ))
        ][:30]

        return {
            "path": str(p),
            "string_count": len(lines),
            "sample": lines[: self._MAX_STRINGS_OUT],
            "interesting": interesting,
            "tool": binary or "builtin_regex",
        }

    def scan(self, path: str) -> dict[str, Any]:
        """Signature scan via binwalk (no extraction — read-only)."""
        p = self._resolve(path)
        binary = shutil.which("binwalk")
        if not binary:
            return {
                "path": str(p),
                "signatures": [],
                "error": "binwalk not installed — install via package manager",
            }
        out = self._run([binary, str(p)])
        sigs = [
            ln.strip() for ln in out.get("stdout", "").splitlines()
            if ln.strip() and not ln.startswith("DECIMAL")
        ]
        return {
            "path": str(p),
            "signatures": sigs[:100],
            "binwalk": out,
            "note": "Signature scan only — extraction disabled in this tool.",
        }

    def symbols(self, path: str) -> dict[str, Any]:
        """Dynamic symbol table via readelf/objdump when available."""
        p = self._resolve(path)
        readelf = shutil.which("readelf")
        objdump = shutil.which("objdump")
        nm = shutil.which("nm")

        results: dict[str, Any] = {"path": str(p)}
        if readelf:
            results["readelf_dynamic"] = self._run(
                [readelf, "-s", str(p)], timeout=60.0,
            )
        elif objdump:
            results["objdump_symbols"] = self._run(
                [objdump, "-T", str(p)], timeout=60.0,
            )
        elif nm:
            results["nm"] = self._run([nm, "-D", str(p)], timeout=60.0)
        else:
            results["error"] = "No readelf/objdump/nm found — install binutils"

        return results

    def analyze(self, path: str, *, include_strings: bool = True) -> dict[str, Any]:
        """Full static RE report combining identify, strings, scan, symbols."""
        report: dict[str, Any] = {
            "identify": self.identify(path),
            "scan": self.scan(path),
            "symbols": self.symbols(path),
        }
        if include_strings:
            report["strings"] = self.strings(path)
        report["workflow_doc"] = "docs/reverse-engineering.md"
        report["recommended_next"] = [
            "searchsploit.search if suspicious service strings found",
            "binwalk.scan via arsenal for deeper firmware work (authorized samples)",
            "exiftool.extract for document/metadata artifacts",
        ]
        return report

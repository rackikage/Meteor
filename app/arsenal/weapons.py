"""Weapon wrappers + arsenal discovery.

`ArsenalTool` gives any driver two primitives:
  - detect(): what catalog tools are installed, grouped by pipeline phase
  - run(tool, args): execute an arbitrary installed tool with structured output

The heavy hitters get typed first-class wrappers (sqlmap, nuclei, hydra, …) so a
driver gets discoverable operations + parsed-ish output instead of free-form
argv. Every weapon is a plain tool object with named methods; `register_arsenal`
puts them in the shared registry and `ARSENAL_CAPABILITIES` advertises them to
the ToolExecutor (and therefore the MCP server).
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from app.arsenal.catalog import CATALOG

_DEFAULT_TIMEOUT = 600.0
_MAX_STDOUT = 200_000
_MAX_STDERR = 20_000


def _exec(binary: str, args: list[str], timeout: Optional[float] = None) -> dict:
    """Run `binary args`, capture output, never raise. Structured result."""
    path = shutil.which(binary)
    if path is None:
        return {"installed": False, "binary": binary,
                "error": f"{binary} is not installed on this box"}
    cmd = [path, *[str(a) for a in args]]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout or _DEFAULT_TIMEOUT)
        return {
            "installed": True,
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout[:_MAX_STDOUT],
            "stderr": proc.stderr[:_MAX_STDERR],
            "truncated": len(proc.stdout) > _MAX_STDOUT,
        }
    except subprocess.TimeoutExpired:
        return {"installed": True, "command": " ".join(cmd),
                "returncode": -1, "stdout": "", "stderr": "timed out", "timed_out": True}
    except Exception as exc:  # noqa: BLE001 — surface, never crash the driver
        return {"installed": True, "command": " ".join(cmd),
                "returncode": -1, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


# ── Arsenal discovery + generic runner ──────────────────────────────────────

class ArsenalTool:
    """Discovery + generic execution over the installed toolkit."""

    def detect(self, phase: str = "") -> dict:
        """Report installed catalog tools grouped by pipeline phase. Pass a
        phase name to filter (recon/ingest/analyze/exploit/pivot/crack/
        wireless/c2_tunnel/evasion/forensic)."""
        phases = {phase: CATALOG[phase]} if phase and phase in CATALOG else CATALOG
        out: dict[str, list[dict]] = {}
        total = 0
        for ph, tools in phases.items():
            installed = []
            for binary, desc in tools.items():
                if shutil.which(binary):
                    installed.append({"tool": binary, "description": desc})
            if installed:
                out[ph] = installed
                total += len(installed)
        return {"installed_count": total, "phases": out}

    def run(self, tool: str, args: str = "", timeout: float = _DEFAULT_TIMEOUT) -> dict:
        """Run any installed tool with a raw argument string, structured output.
        `args` is shell-split. Use the typed weapon wrappers when one exists."""
        import shlex
        arg_list = shlex.split(args) if args else []
        return _exec(tool, arg_list, timeout=timeout)

    def health(self) -> dict:
        return {"healthy": True, "backend": "arsenal"}


# ── First-class weapon wrappers (the heavy hitters) ─────────────────────────

class _Weapon:
    binary = ""

    def health(self) -> dict:
        return {"healthy": shutil.which(self.binary) is not None,
                "binary": self.binary, "backend": self.binary}


class SqlmapWeapon(_Weapon):
    binary = "sqlmap"

    def scan(self, url: str, data: str = "", level: int = 1, risk: int = 1,
             extra: str = "") -> dict:
        args = ["-u", url, "--batch", "--level", str(level), "--risk", str(risk)]
        if data:
            args += ["--data", data]
        if extra:
            import shlex
            args += shlex.split(extra)
        return _exec(self.binary, args)


class NucleiWeapon(_Weapon):
    binary = "nuclei"

    def scan(self, target: str, templates: str = "", severity: str = "") -> dict:
        args = ["-u", target, "-nc", "-silent"]
        if templates:
            args += ["-t", templates]
        if severity:
            args += ["-severity", severity]
        return _exec(self.binary, args)


class NiktoWeapon(_Weapon):
    binary = "nikto"

    def scan(self, target: str) -> dict:
        return _exec(self.binary, ["-h", target, "-ask", "no"])


class WhatWebWeapon(_Weapon):
    binary = "whatweb"

    def fingerprint(self, target: str, aggression: int = 1) -> dict:
        return _exec(self.binary, [f"--aggression={aggression}", "--color=never", target])


class WpscanWeapon(_Weapon):
    binary = "wpscan"

    def scan(self, url: str, extra: str = "") -> dict:
        args = ["--url", url, "--no-banner", "--random-user-agent"]
        if extra:
            import shlex
            args += shlex.split(extra)
        return _exec(self.binary, args)


class GobusterWeapon(_Weapon):
    binary = "gobuster"

    def dir(self, url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt",
            extensions: str = "") -> dict:
        args = ["dir", "-u", url, "-w", wordlist, "-q", "--no-color"]
        if extensions:
            args += ["-x", extensions]
        return _exec(self.binary, args)

    def dns(self, domain: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> dict:
        return _exec(self.binary, ["dns", "-d", domain, "-w", wordlist, "-q", "--no-color"])


class FfufWeapon(_Weapon):
    binary = "ffuf"

    def fuzz(self, url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> dict:
        # URL must contain the FUZZ keyword, e.g. http://host/FUZZ
        target = url if "FUZZ" in url else url.rstrip("/") + "/FUZZ"
        return _exec(self.binary, ["-u", target, "-w", wordlist, "-s"])


class FeroxbusterWeapon(_Weapon):
    binary = "feroxbuster"

    def scan(self, url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> dict:
        return _exec(self.binary, ["-u", url, "-w", wordlist, "--silent", "--no-state"])


class HydraWeapon(_Weapon):
    binary = "hydra"

    def bruteforce(self, target: str, service: str, userlist: str = "",
                   passlist: str = "", username: str = "") -> dict:
        args = []
        if username:
            args += ["-l", username]
        elif userlist:
            args += ["-L", userlist]
        if passlist:
            args += ["-P", passlist]
        args += ["-f", f"{service}://{target}"]
        return _exec(self.binary, args)


class SearchsploitWeapon(_Weapon):
    binary = "searchsploit"

    def search(self, term: str) -> dict:
        import shlex
        return _exec(self.binary, [*shlex.split(term)])


class DnsreconWeapon(_Weapon):
    binary = "dnsrecon"

    def enum(self, domain: str) -> dict:
        return _exec(self.binary, ["-d", domain])


class Enum4linuxWeapon(_Weapon):
    binary = "enum4linux-ng"

    def scan(self, target: str) -> dict:
        # Prefer the -ng rewrite, fall back to classic enum4linux.
        binary = "enum4linux-ng" if shutil.which("enum4linux-ng") else "enum4linux"
        args = ["-A", target] if binary == "enum4linux-ng" else ["-a", target]
        return _exec(binary, args)


class SmbmapWeapon(_Weapon):
    binary = "smbmap"

    def scan(self, target: str, username: str = "", password: str = "") -> dict:
        args = ["-H", target]
        if username:
            args += ["-u", username, "-p", password or ""]
        return _exec(self.binary, args)


class MasscanWeapon(_Weapon):
    binary = "masscan"

    def scan(self, target: str, ports: str = "1-1000", rate: int = 1000) -> dict:
        return _exec(self.binary, [target, "-p", ports, "--rate", str(rate)])


class ExiftoolWeapon(_Weapon):
    binary = "exiftool"

    def extract(self, path: str) -> dict:
        return _exec(self.binary, [path])


class BinwalkWeapon(_Weapon):
    binary = "binwalk"

    def scan(self, path: str, extract: bool = False) -> dict:
        args = ["-e", path] if extract else [path]
        return _exec(self.binary, args)


# ── Registry glue ───────────────────────────────────────────────────────────
# tool_name -> instance. Registered into the shared SystemToolRegistry so the
# app loop AND the MCP server both see them.
WEAPON_TOOLS: dict[str, object] = {
    "arsenal": ArsenalTool(),
    "sqlmap": SqlmapWeapon(),
    "nuclei": NucleiWeapon(),
    "nikto": NiktoWeapon(),
    "whatweb": WhatWebWeapon(),
    "wpscan": WpscanWeapon(),
    "gobuster": GobusterWeapon(),
    "ffuf": FfufWeapon(),
    "feroxbuster": FeroxbusterWeapon(),
    "hydra": HydraWeapon(),
    "searchsploit": SearchsploitWeapon(),
    "dnsrecon": DnsreconWeapon(),
    "enum4linux": Enum4linuxWeapon(),
    "smbmap": SmbmapWeapon(),
    "masscan": MasscanWeapon(),
    "exiftool": ExiftoolWeapon(),
    "binwalk": BinwalkWeapon(),
}

# tool.operation -> (method_name, [required_params], description). Merged into
# ToolExecutor.CAPABILITIES so both the agent loop and MCP advertise them.
ARSENAL_CAPABILITIES: dict[str, tuple] = {
    "arsenal.detect": ("detect", [], "List installed pentest tools grouped by pipeline phase"),
    "arsenal.run": ("run", ["tool"], "Run any installed tool with a raw arg string (structured output)"),
    "sqlmap.scan": ("scan", ["url"], "sqlmap automated SQL injection against a URL"),
    "nuclei.scan": ("scan", ["target"], "nuclei template-based vulnerability scan"),
    "nikto.scan": ("scan", ["target"], "nikto web server vulnerability scan"),
    "whatweb.fingerprint": ("fingerprint", ["target"], "whatweb tech-stack fingerprint"),
    "wpscan.scan": ("scan", ["url"], "WordPress security scan"),
    "gobuster.dir": ("dir", ["url"], "gobuster directory/file brute-force"),
    "gobuster.dns": ("dns", ["domain"], "gobuster DNS subdomain brute-force"),
    "ffuf.fuzz": ("fuzz", ["url"], "ffuf web fuzzer (URL needs FUZZ keyword)"),
    "feroxbuster.scan": ("scan", ["url"], "feroxbuster recursive content discovery"),
    "hydra.bruteforce": ("bruteforce", ["target", "service"], "hydra network login brute-force"),
    "searchsploit.search": ("search", ["term"], "search Exploit-DB for a term"),
    "dnsrecon.enum": ("enum", ["domain"], "DNS enumeration for a domain"),
    "enum4linux.scan": ("scan", ["target"], "SMB/Samba enumeration of a host"),
    "smbmap.scan": ("scan", ["target"], "enumerate SMB shares on a host"),
    "masscan.scan": ("scan", ["target"], "masscan high-rate port scan"),
    "exiftool.extract": ("extract", ["path"], "extract file metadata"),
    "binwalk.scan": ("scan", ["path"], "firmware/file signature analysis"),
}


def register_arsenal(registry) -> None:
    """Register every weapon into the shared SystemToolRegistry. Idempotent."""
    for name, instance in WEAPON_TOOLS.items():
        registry.register(name, instance, f"arsenal:{name}", version="1.0")

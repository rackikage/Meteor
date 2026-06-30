"""Meteor Hackmachine — minimal chat UI for LAN infiltration."""

from __future__ import annotations

import asyncio
import socket
import sys
import threading
import tkinter as tk
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tkinter import font
from typing import Callable, Optional

from app.gui.intent_llm import resolve_intent
from app.gui.macos_window import configure_macos_window, macos_content_padx
from app.runtime.depth_session_store import SessionFindings, get_depth_session_store
from app.runtime.rate_limiter import OpClass, get_rate_limiter
from app.tools.pentest.network_scope import NetworkScope, discover_network_scope

REPO = Path(__file__).resolve().parent
ICON_PATH = REPO / "assets" / "meteor_icon_64.png"
SOCKET_PATH = Path.home() / ".meteor" / "gui.sock"

# ── Palette ───────────────────────────────────────────────────────────
BLACK = "#000000"
PANEL = "#0A0A0F"
CARD = "#12121A"
BUBBLE_USER = "#1A1030"
BUBBLE_BOT = "#14141E"
BORDER = "#2A2A3A"
GRID = "#1E1E2E"
SILVER = "#9AA0B8"
DIM = "#5C6078"
WHITE = "#E8E8F0"
PURPLE = "#B026FF"
VIOLET = "#7C3AED"
MAGENTA = "#D946EF"
CYAN = "#22D3EE"
GREEN = "#00E676"
AMBER = "#FBBF24"
RED = "#FF5252"

APP_NAME = "METEOR HACKMACHINE"

WELCOME = """Hackmachine online. Tell me what to hit.

dig into the network · scan the gateway · infiltrate the subnet"""

HELP_TEXT = """Commands
────────
  dig into the network   full LAN sweep
  scan <ip>              port probe (default: gateway)
  infiltrate <cidr>      subnet infiltration
  graph                  asset map
  posture / firewall     kernel + perimeter assessment
  pivot <ip>             lateral paths
  stats                  runtime status
  help                   this panel"""


FONT_MONO = "Menlo"
FONT_UI = "Helvetica Neue"


def _resolve_fonts(root: tk.Tk) -> tuple[str, str]:
    try:
        families = {f.lower() for f in font.families(root=root)}
        mono = next((n for n in ("Menlo", "SF Mono", "Monaco", "Courier New") if n.lower() in families), FONT_MONO)
        ui = next((n for n in ("Helvetica Neue", "Helvetica", "Arial") if n.lower() in families), FONT_UI)
        return mono, ui
    except Exception:
        return FONT_MONO, FONT_UI


class SingleInstanceGuard:
    """Ensure one GUI instance; refocus the existing window on relaunch."""

    def __init__(self, on_focus: Callable[[], None], root: tk.Tk) -> None:
        self._on_focus = on_focus
        self._root = root
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    def try_acquire(self) -> bool:
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.settimeout(0.5)
            probe.connect(str(SOCKET_PATH))
            probe.sendall(b"focus\n")
            return False
        except (FileNotFoundError, ConnectionRefusedError, TimeoutError, OSError):
            return self._start_listener()
        finally:
            probe.close()

    def _start_listener(self) -> bool:
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            if SOCKET_PATH.exists():
                SOCKET_PATH.unlink()
            self._server.bind(str(SOCKET_PATH))
            self._server.listen(5)
        except OSError:
            return False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return True

    def _serve(self) -> None:
        assert self._server is not None
        while True:
            try:
                conn, _ = self._server.accept()
            except OSError:
                break
            with conn:
                try:
                    data = conn.recv(64)
                except OSError:
                    continue
                if b"focus" in data:
                    self._root.after(0, self._on_focus)

    def cleanup(self) -> None:
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        if SOCKET_PATH.exists():
            try:
                SOCKET_PATH.unlink()
            except OSError:
                pass


class MeteorHackmachine:
    """Minimal hackmachine chat UI."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Meteor Hackmachine")
        self.root.configure(bg=BLACK)
        self.root.minsize(340, 420)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Free-floating default size; user resizes freely
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(540, int(sw * 0.38)), min(680, int(sh * 0.62))
        x, y = (sw - w) // 2, (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.session_id = f"hk-{datetime.now(timezone.utc).strftime('%H%M%S')}"
        self._instance_guard: Optional[SingleInstanceGuard] = None
        self._busy = False
        self._runtime_ready = False
        self._scope: Optional[NetworkScope] = None
        self._typing_mark: Optional[str] = None
        self._stream_body_mark: Optional[str] = None

        if ICON_PATH.exists():
            self._icon = tk.PhotoImage(file=str(ICON_PATH))
            self.root.iconphoto(True, self._icon)

        self._font_mono, self._font_ui = _resolve_fonts(root)
        configure_macos_window(self.root, dark=True)

        self._build_shell()
        self.root.after(100, self._boot_sequence)
        self.root.after(200, self._warm_runtime)

    def focus_input(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(50, lambda: self.root.attributes("-topmost", False))
        self.root.after(75, self._input.focus_set)
        self.root.after(75, lambda: self._input.icursor(tk.END))

    def _build_shell(self) -> None:
        pad_l, pad_r = macos_content_padx(14)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)

        self._build_header(pad_l, pad_r).grid(row=0, column=0, sticky="ew")
        self._build_chat(pad_l, pad_r).grid(row=1, column=0, sticky="nsew")
        self._build_bottom(pad_l, pad_r).grid(row=2, column=0, sticky="ew")
        self._bind_keys()
        self.root.bind("<Configure>", self._on_root_configure, add="+")

    def _on_root_configure(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        width = max(event.width - 40, 120)
        self._footer.config(wraplength=width)

    def _build_header(self, pad_l: int, pad_r: int) -> tk.Frame:
        strip = tk.Frame(self.root, bg=BLACK)
        strip.columnconfigure(0, weight=1)

        inner = tk.Frame(strip, bg=BLACK)
        inner.grid(row=0, column=0, sticky="ew", padx=(pad_l, pad_r), pady=(8, 6))
        inner.columnconfigure(1, weight=1)

        tk.Label(
            inner, text="☄ hackmachine", bg=BLACK, fg=WHITE,
            font=(self._font_ui, 12, "bold"),
        ).grid(row=0, column=0, sticky="w")

        right = tk.Frame(inner, bg=BLACK)
        right.grid(row=0, column=2, sticky="e")

        self._link_led = tk.Canvas(right, width=6, height=6, bg=BLACK, highlightthickness=0)
        self._link_led.create_oval(0, 0, 6, 6, fill=AMBER, outline="")
        self._link_led.pack(side="left", padx=(0, 5))

        self._status = tk.Label(
            right, text="boot", bg=BLACK, fg=DIM,
            font=(self._font_mono, 9),
        )
        self._status.pack(side="left")
        return strip

    def _build_chat(self, pad_l: int, pad_r: int) -> tk.Frame:
        wrap = tk.Frame(self.root, bg=BLACK)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)

        self._chat = tk.Text(
            wrap, bg=BLACK, fg=SILVER, insertbackground=PURPLE,
            font=(self._font_mono, 11), wrap="word", bd=0,
            highlightthickness=0, padx=0, pady=8,
            state="disabled", cursor="arrow", spacing3=4,
        )
        scroll = tk.Scrollbar(
            wrap, command=self._chat.yview,
            bg=BLACK, troughcolor=BLACK, width=8,
            highlightthickness=0, bd=0,
        )
        self._chat.configure(yscrollcommand=scroll.set)
        self._chat.grid(row=0, column=0, sticky="nsew", padx=(pad_l, 4), pady=(0, 4))
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, pad_r), pady=(0, 4))

        tags = {
            "welcome": {"foreground": DIM, "font": (self._font_ui, 11)},
            "user_label": {"foreground": CYAN, "font": (self._font_mono, 8), "spacing1": 12},
            "user_body": {
                "foreground": WHITE, "lmargin1": 16, "lmargin2": 16, "rmargin": 12,
                "spacing1": 0, "spacing3": 8,
            },
            "bot_label": {"foreground": PURPLE, "font": (self._font_mono, 8), "spacing1": 12},
            "bot_body": {
                "foreground": WHITE, "lmargin1": 8, "lmargin2": 8, "rmargin": 12,
                "spacing1": 0, "spacing3": 8,
            },
            "system": {"foreground": DIM, "font": (self._font_mono, 9)},
            "stdout": {"foreground": GREEN},
            "info": {"foreground": SILVER},
            "warn": {"foreground": AMBER},
            "error": {"foreground": RED},
            "head": {"foreground": MAGENTA, "font": (self._font_mono, 11, "bold")},
            "accent": {"foreground": CYAN},
            "dim": {"foreground": DIM},
            "typing": {"foreground": DIM, "font": (self._font_mono, 10, "italic")},
        }
        for name, opts in tags.items():
            self._chat.tag_configure(name, **opts)
        return wrap

    def _build_bottom(self, pad_l: int, pad_r: int) -> tk.Frame:
        panel = tk.Frame(self.root, bg=BLACK)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=0)
        panel.rowconfigure(1, weight=0)

        composer = tk.Frame(panel, bg=BLACK)
        composer.grid(row=0, column=0, sticky="ew", padx=(pad_l, pad_r), pady=(0, 4))
        composer.columnconfigure(0, weight=1)

        inner = tk.Frame(composer, bg=GRID, highlightthickness=1, highlightbackground=BORDER)
        inner.grid(row=0, column=0, sticky="ew")
        inner.columnconfigure(0, weight=1)

        self._input = tk.Entry(
            inner, bg=GRID, fg=WHITE, insertbackground=PURPLE,
            font=(self._font_ui, 12), bd=0, relief="flat",
            highlightthickness=0,
        )
        self._input.grid(row=0, column=0, sticky="ew", padx=(10, 4), ipady=6)

        self._send_btn = tk.Button(
            inner, text="↵", bg=GRID, fg=PURPLE,
            activebackground=GRID, activeforeground=WHITE,
            font=(self._font_ui, 13), bd=0, cursor="hand2",
            width=2, command=self._send,
        )
        self._send_btn.grid(row=0, column=1, padx=(0, 6), pady=4, sticky="ns")

        footer_bar = tk.Frame(panel, bg=BLACK)
        footer_bar.grid(row=1, column=0, sticky="ew", padx=(pad_l, pad_r), pady=(0, 8))
        footer_bar.columnconfigure(0, weight=1)

        self._footer = tk.Label(
            footer_bar, text="", bg=BLACK, fg=DIM,
            font=(self._font_mono, 8), anchor="w", justify="left",
        )
        self._footer.grid(row=0, column=0, sticky="ew")
        return panel

    def _bind_keys(self) -> None:
        self._input.bind("<Return>", lambda _e: self._send())
        self.root.bind("<Escape>", lambda _e: self.focus_input())

    def _boot_sequence(self) -> None:
        self._bot_message(WELCOME, tag="welcome")

    def _warm_runtime(self) -> None:
        def work() -> None:
            try:
                from app.runtime.ollama_launcher import ensure_ollama_running, is_ollama_running

                if not is_ollama_running() and not ensure_ollama_running():
                    self.root.after(
                        0,
                        self._bot_message,
                        "Ollama is not running — chat and LLM intent routing will be limited.\n"
                        "Install: curl -fsSL https://ollama.com/install.sh | sh\n"
                        "Or start manually: ollama serve",
                        "warn",
                    )

                scope = discover_network_scope()
                self._scope = scope
                self.root.after(0, self._on_scope_ready, scope)

                from app.api.main import get_runtime
                get_runtime()
                self._runtime_ready = True
                self.root.after(0, self._set_status, "armed", GREEN)
                self.root.after(0, self._set_footer, target=scope.gateway, scope=scope.cidr)
                lines = "\n".join(f"  {line}" for line in scope.summary_lines())
                self.root.after(
                    0,
                    self._bot_message,
                    f"Scope locked.\n{lines}\n\nReady — try \"dig into the network\".",
                    "info",
                )
            except Exception as exc:
                self.root.after(0, self._set_status, "fault", RED)
                self.root.after(0, self._bot_message, f"Runtime fault: {exc}", "error")

        threading.Thread(target=work, daemon=True).start()

    def _on_scope_ready(self, scope: NetworkScope) -> None:
        self._set_footer(target=scope.gateway, scope=scope.cidr)

    def _scope_gateway(self) -> str:
        return self._scope.gateway if self._scope else "127.0.0.1"

    def _scope_cidr(self) -> str:
        return self._scope.cidr if self._scope else "127.0.0.1/32"

    def _append(self, text: str, tag: str = "stdout") -> None:
        self._chat.configure(state="normal")
        self._chat.insert(tk.END, text, tag)
        self._chat.configure(state="disabled")
        self._chat.see(tk.END)

    def _user_message(self, text: str) -> None:
        self._chat.configure(state="normal")
        self._chat.insert(tk.END, "YOU\n", "user_label")
        self._chat.insert(tk.END, f"{text}\n", "user_body")
        self._chat.configure(state="disabled")
        self._chat.see(tk.END)

    def _bot_message(self, text: str, tag: str = "stdout") -> None:
        self._chat.configure(state="normal")
        self._chat.insert(tk.END, "hackmachine\n", "bot_label")
        if tag in ("stdout", "info", "warn", "error", "head", "accent", "dim", "welcome"):
            self._chat.insert(tk.END, f"{text}\n", tag)
        else:
            self._chat.insert(tk.END, f"{text}\n", "bot_body")
        self._chat.configure(state="disabled")
        self._chat.see(tk.END)

    def _show_typing(self) -> None:
        self._hide_typing()
        self._chat.configure(state="normal")
        self._typing_mark = self._chat.index(tk.END)
        self._chat.insert(tk.END, "working…\n", "typing")
        self._chat.configure(state="disabled")
        self._chat.see(tk.END)

    def _hide_typing(self) -> None:
        if self._typing_mark is None:
            return
        self._chat.configure(state="normal")
        self._chat.delete(self._typing_mark, tk.END)
        self._chat.configure(state="disabled")
        self._typing_mark = None

    def _begin_stream_bubble(self) -> None:
        self._hide_typing()
        self._chat.configure(state="normal")
        self._chat.insert(tk.END, "hackmachine\n", "bot_label")
        self._stream_body_mark = self._chat.index(tk.END)
        self._chat.insert(self._stream_body_mark, "", "bot_body")
        self._chat.configure(state="disabled")

    def _update_stream_bubble(self, text: str) -> None:
        if self._stream_body_mark is None:
            return
        self._chat.configure(state="normal")
        self._chat.delete(self._stream_body_mark, tk.END)
        self._chat.insert(self._stream_body_mark, f"{text}\n", "bot_body")
        self._chat.configure(state="disabled")
        self._chat.see(tk.END)

    def _end_stream_bubble(self) -> None:
        self._stream_body_mark = None

    def _set_status(self, text: str, color: str = GREEN) -> None:
        self._status.config(text=text.upper(), fg=color)
        self._link_led.itemconfig(1, fill=color)

    def _set_footer(self, **parts: str) -> None:
        defaults = {"scope": "—", "target": "—", "graph": "—", "signal": "OK"}
        defaults.update(parts)
        self._footer.config(text=" · ".join(f"{k}:{v}" for k, v in defaults.items()))

    def _send(self) -> None:
        text = self._input.get().strip()
        if not text or self._busy:
            return
        self._input.delete(0, tk.END)

        if text.lower() in ("/clear", "clear"):
            self._clear_chat()
            return
        if text.lower().startswith("help") or text.strip() == "?":
            self._user_message(text)
            self._bot_message(HELP_TEXT, "head")
            return

        self._user_message(text)
        self._busy = True
        self._send_btn.config(state="disabled", bg=DIM)
        self.root.after(0, self._show_typing)
        threading.Thread(target=self._dispatch, args=(text,), daemon=True).start()

    def _finish_command(self) -> None:
        self._busy = False
        self.root.after(0, self._hide_typing)
        self.root.after(0, lambda: self._send_btn.config(state="normal", bg=PURPLE))
        self.root.after(0, self.focus_input)

    def _op_class_for(self, cmd: str) -> OpClass:
        if cmd in ("investigate", "infiltrate"):
            return OpClass.DEEP
        return OpClass.QUICK

    def _dispatch(self, raw: str) -> None:
        try:
            from app.api.main import get_runtime
            runtime = get_runtime()

            depth_store = get_depth_session_store()
            depth_ctx = depth_store.context_block(self.session_id)

            cmd, args, routed = resolve_intent(
                raw,
                default_gateway=self._scope_gateway(),
                default_cidr=self._scope_cidr(),
                model_registry=runtime.model_registry,
                depth_context=depth_ctx,
            )

            if routed:
                self.root.after(0, self._bot_message, f"→ {routed.reason}", "system")

            op_class = self._op_class_for(cmd)
            limiter = get_rate_limiter()
            limit = limiter.acquire(self.session_id, op_class)
            if not limit.allowed:
                self.root.after(0, self._bot_message, limit.reason, "warn")
                return

            try:
                if cmd == "scan":
                    self._do_scan(runtime, args)
                elif cmd == "investigate":
                    self._do_investigate(runtime, args)
                elif cmd == "infiltrate":
                    self._do_infiltrate(runtime, args)
                elif cmd == "research":
                    self._do_scan(runtime, {
                        "target": self._scope_gateway(),
                        **({"port": args["service"]} if args.get("service") else {}),
                    })
                elif cmd == "graph":
                    self._do_graph(runtime)
                elif cmd == "pivot":
                    self._do_pivot(runtime, args)
                elif cmd == "stats":
                    self._do_stats(runtime)
                elif cmd == "posture":
                    self._do_posture(runtime, args)
                elif cmd == "help":
                    self.root.after(0, self._bot_message, HELP_TEXT, "head")
                elif cmd == "chat":
                    if depth_ctx:
                        args["depth_context"] = depth_ctx
                    self._do_chat(runtime, args)
                else:
                    self.root.after(0, self._bot_message, f"Unknown operation: {cmd}", "error")
            finally:
                if op_class == OpClass.DEEP:
                    limiter.release(self.session_id, op_class)
        except Exception as exc:
            self.root.after(0, self._set_status, "fault", RED)
            self.root.after(0, self._bot_message, str(exc), "error")
        finally:
            self.root.after(0, self._finish_command)

    def _do_scan(self, runtime, args: dict) -> None:
        target = args["target"]
        self.root.after(0, self._set_status, "scanning", AMBER)
        self.root.after(0, self._set_footer, target=target, signal="BUSY")

        from app.tools.pentest.ports import DEFAULT_GUI_SCAN_PORTS
        stats = asyncio.run(runtime.grinder.grind_host(target, ports=DEFAULT_GUI_SCAN_PORTS))

        self.root.after(0, self._bot_message, (
            f"Scan complete on {target}\n"
            f"  open services: {stats.services_discovered}\n"
            f"  elapsed: {stats.wall_time_ms:.0f}ms\n"
            f"  errors: {stats.errors}"
        ), "stdout")
        self.root.after(0, self._set_status, "armed", GREEN)
        self.root.after(0, self._set_footer, target=target, signal="OK")

    def _do_investigate(self, runtime, args: dict) -> None:
        depth = args.get("depth", 2)
        scope = self._scope or discover_network_scope()
        self._scope = scope

        self.root.after(0, self._set_status, "intercepting", MAGENTA)
        self.root.after(0, self._set_footer, target=scope.gateway, signal="BUSY")
        self.root.after(0, self._bot_message, "Digging into the network…", "warn")

        from app.tools.pentest.ports import DEFAULT_GUI_SCAN_PORTS

        depth_mgr = None
        depth_session = None
        if depth >= 3 and runtime.model_registry is not None:
            from app.runtime.depth_context import DepthContextManager, DepthSession

            profile = runtime.config.models.profiles[runtime.config.models.default_profile]
            model = runtime.model_registry.resolve_for_request({"complexity": "heavy"})
            depth_mgr = DepthContextManager(model, profile)
            depth_session = DepthSession(max_depth=depth)

        async def run_flow() -> tuple[int, object, list[str]]:
            phase_notes: list[str] = []
            from app.tools.pentest.ports import DEFAULT_GUI_SCAN_PORTS

            if depth >= 3:
                batch_stats, subnet_stats = await asyncio.gather(
                    runtime.grinder.grind_hosts_batch(
                        list(scope.priority_targets),
                        ports=DEFAULT_GUI_SCAN_PORTS,
                    ),
                    runtime.grinder.grind_subnet(scope.cidr, scan="subset"),
                )
                scanned = batch_stats.tasks_completed
                probe_output = (
                    f"parallel probe: {batch_stats.services_discovered} services on "
                    f"{batch_stats.hosts_discovered} hosts; "
                    f"subnet sweep: {subnet_stats.services_discovered} services "
                    f"({subnet_stats.wall_time_ms:.0f}ms)"
                )
            else:
                scanned = 0
                probe_lines = []
                for ip in scope.priority_targets:
                    stats = await runtime.grinder.grind_host(ip, ports=DEFAULT_GUI_SCAN_PORTS)
                    scanned += 1
                    probe_lines.append(f"{ip}: {stats.services_discovered} services")
                probe_output = "\n".join(probe_lines)

            if depth_mgr and depth_session:
                summary = depth_mgr.record_step(depth_session, "priority_probe", probe_output)
                phase_notes.append(f"Probe phase: {summary}")

            report = await runtime.agent.infiltrate(scope.cidr, depth=depth)
            if depth_mgr and depth_session:
                infil_output = (
                    f"hosts={report.hosts_discovered} services={report.services_discovered} "
                    f"crit/high={report.critical_vulns}/{report.high_vulns}"
                )
                summary = depth_mgr.record_step(depth_session, "subnet_infiltration", infil_output)
                phase_notes.append(f"Infiltration: {summary}")
                nxt = depth_mgr.suggest_next_command(depth_session)
                if nxt:
                    phase_notes.append(f"Next: {nxt.get('intent')} — {nxt.get('reason', '')}")

                top_svc = [
                    f"{i.service}:{i.port}" for i in
                    sorted(report.intelligence, key=lambda x: x.attack_surface_score, reverse=True)[:6]
                ] if report.intelligence else []
                get_depth_session_store().update_from_depth_session(
                    self.session_id,
                    depth_session,
                    SessionFindings(
                        gateway=scope.gateway,
                        cidr=scope.cidr,
                        hosts_discovered=report.hosts_discovered,
                        services_discovered=report.services_discovered,
                        top_services=top_svc,
                        notes=phase_notes,
                    ),
                )
            return scanned, report, phase_notes

        scanned, report, phase_notes = asyncio.run(run_flow())

        top_svc = [
            f"{intel.service}:{intel.port}" for intel in
            sorted(report.intelligence, key=lambda x: x.attack_surface_score, reverse=True)[:6]
        ] if report.intelligence else []
        store = get_depth_session_store()
        stored = store.get_or_create(self.session_id, depth)
        stored.findings = asdict(SessionFindings(
            gateway=scope.gateway,
            cidr=scope.cidr,
            hosts_discovered=report.hosts_discovered,
            services_discovered=report.services_discovered,
            top_services=top_svc,
            notes=phase_notes,
        ))
        store.save(stored)

        lines = [
            "Network infiltration complete",
            f"  gateway: {scope.gateway}",
            f"  subnet: {scope.cidr}",
            f"  hosts probed: {scanned}",
            f"  hosts discovered: {report.hosts_discovered}",
            f"  services: {report.services_discovered}",
            f"  critical/high: {report.critical_vulns}/{report.high_vulns}",
            f"  exploits: {report.exploits_found}",
            f"  elapsed: {report.wall_time_ms:.0f}ms",
        ]
        if report.intelligence:
            lines.append("  top surface:")
            top = sorted(report.intelligence, key=lambda x: x.attack_surface_score, reverse=True)[:5]
            for intel in top:
                lines.append(
                    f"    · {intel.ip}:{intel.port}/{intel.service} score={intel.attack_surface_score:.1f}"
                )
        if phase_notes:
            lines.append("  AI-compressed phases:")
            for note in phase_notes:
                lines.append(f"    · {note}")
        self.root.after(0, self._bot_message, "\n".join(lines), "stdout")
        self.root.after(0, self._set_status, "armed", GREEN)
        self.root.after(0, self._set_footer, target=scope.gateway, graph=str(report.hosts_discovered), signal="OK")

    def _do_infiltrate(self, runtime, args: dict) -> None:
        target, depth = args["target"], args["depth"]
        self.root.after(0, self._set_status, f"infil d{depth}", AMBER)
        self.root.after(0, self._set_footer, target=target, signal="BUSY")
        self.root.after(0, self._bot_message, f"Infiltrating {target} at depth {depth}…", "warn")

        report = asyncio.run(runtime.agent.infiltrate(target, depth=depth))
        lines = [
            f"Infiltration report — {report.target}",
            f"  depth reached: {report.depth_reached}",
            f"  hosts: {report.hosts_discovered}",
            f"  services: {report.services_discovered}",
            f"  critical/high: {report.critical_vulns}/{report.high_vulns}",
            f"  exploits: {report.exploits_found}",
            f"  elapsed: {report.wall_time_ms:.0f}ms",
        ]
        if report.intelligence:
            lines.append("  top surface:")
            top = sorted(report.intelligence, key=lambda x: x.attack_surface_score, reverse=True)[:5]
            for intel in top:
                lines.append(f"    · {intel.ip}:{intel.port}/{intel.service} score={intel.attack_surface_score:.1f}")
        self.root.after(0, self._bot_message, "\n".join(lines), "stdout")
        self.root.after(0, self._set_status, "armed", GREEN)
        self.root.after(0, self._set_footer, target=target, graph=str(report.hosts_discovered), signal="OK")

    def _do_research(self, runtime, args: dict) -> None:
        from app.agent.web_search import WebSearcher

        query = args["service"]
        self.root.after(0, self._set_status, "intel", CYAN)

        intel = asyncio.run(WebSearcher().research_service("target", 0, query))
        lines = [f"Intel on {query}", f"  attack surface: {intel.attack_surface_score:.1f}/10"]
        for cve in intel.cves[:5]:
            flag = " · EXPLOIT" if cve.exploit_available else ""
            lines.append(f"  {cve.cve_id} ({cve.severity}/{cve.cvss_score}){flag}")
        for ex in intel.exploits[:3]:
            lines.append(f"  exploit: {ex.title}")
        self.root.after(0, self._bot_message, "\n".join(lines), "stdout")
        self.root.after(0, self._set_status, "armed", GREEN)

    def _do_graph(self, runtime) -> None:
        stats = runtime.graph_tool.stats()
        hosts = runtime.graph_tool.query("SELECT ip, hostname, source FROM hosts LIMIT 10")
        edges = runtime.graph_tool.query("SELECT edge_type, COUNT(*) as n FROM asset_edges GROUP BY edge_type")

        lines = ["Asset graph"]
        for table, count in stats.items():
            if count > 0:
                lines.append(f"  {table}: {count}")
        lines.append(f"  hosts sampled: {len(hosts.rows)}")
        for host in hosts.rows[:8]:
            lines.append(f"    · {host['ip']} ({host.get('hostname', '?')})")
        for edge in edges.rows:
            lines.append(f"  edge {edge['edge_type']}: {edge['n']}")
        self.root.after(0, self._bot_message, "\n".join(lines), "stdout")
        self.root.after(0, self._set_footer, graph=str(stats.get("hosts", 0)))

    def _do_pivot(self, runtime, args: dict) -> None:
        ip = args["ip"]
        hosts = runtime.graph_tool.query(f"SELECT id FROM hosts WHERE ip = '{ip}'")
        if not hosts.rows:
            self.root.after(0, self._bot_message, f"{ip} not in graph — scan or investigate first.", "warn")
            return
        neighbors = runtime.graph.find_neighbors("host", hosts.rows[0]["id"])
        lines = [f"Pivots from {ip}"]
        if neighbors:
            for n in neighbors[:10]:
                lines.append(f"  → {n['neighbor_type']}:{n['neighbor_id']} [{n['edge_type']}]")
        else:
            lines.append("  (no lateral edges yet)")
        self.root.after(0, self._bot_message, "\n".join(lines), "stdout")

    def _do_stats(self, runtime) -> None:
        bus = runtime.event_bus.stats()
        noise = runtime.noise.get_state()
        self.root.after(0, self._bot_message, (
            "Runtime telemetry\n"
            f"  events: {bus['events_published']} pub / {bus['events_dropped']} drop\n"
            f"  subscribers: {bus['subscriber_count']}\n"
            f"  noise: {noise.camouflage_multiplier}x idle={noise.is_host_idle}\n"
            f"  workers: {runtime.noise.worker_count()}"
        ), "stdout")

    def _do_posture(self, runtime, args: dict) -> None:
        from app.tools.pentest.tool_executor import get_pentest_executor

        scope = self._scope or discover_network_scope()
        self._scope = scope
        self.root.after(0, self._set_status, "posture", CYAN)
        self.root.after(0, self._set_footer, target=scope.gateway, signal="BUSY")
        self.root.after(0, self._bot_message, "Assessing kernel firewall posture…", "warn")

        result = get_pentest_executor().execute(
            "posture",
            graph_tool=runtime.graph_tool,
            gateway=scope.gateway,
            cidr=scope.cidr,
        )
        if result.status != "ok":
            self.root.after(0, self._bot_message, result.error or "Posture assessment failed.", "error")
            self.root.after(0, self._set_status, "fault", RED)
            return

        self.root.after(0, self._bot_message, result.markdown, "stdout")
        self.root.after(0, self._set_status, "armed", GREEN)
        self.root.after(0, self._set_footer, target=scope.gateway, signal="OK")

    def _do_chat(self, runtime, args: dict) -> None:
        from app.runtime.orchestrator import OrchestratorRequest

        self.root.after(0, self._set_status, "thinking", MAGENTA)
        self.root.after(0, self._begin_stream_bubble)

        meta = {"task_mode": "creative", "complexity": "heavy"}
        if args.get("depth_context"):
            meta["depth_context"] = args["depth_context"]

        request = OrchestratorRequest(
            prompt=args["prompt"],
            session_id=f"gui-{self.session_id}",
            streaming=True,
            max_tokens=1024,
            metadata=meta,
        )

        tokens: list[str] = []
        try:
            for token in runtime.orchestrator.handle_stream(request):
                tokens.append(token)
                self.root.after(0, self._update_stream_bubble, "".join(tokens))
        finally:
            self.root.after(0, self._end_stream_bubble)
            self.root.after(0, self._set_status, "armed", GREEN)

    def _clear_chat(self) -> None:
        self._chat.configure(state="normal")
        self._chat.delete("1.0", tk.END)
        self._chat.configure(state="disabled")
        self._typing_mark = None
        self._boot_sequence()

    def _on_close(self) -> None:
        if self._instance_guard is not None:
            self._instance_guard.cleanup()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = MeteorHackmachine(root)

    guard = SingleInstanceGuard(app.focus_input, root)
    if not guard.try_acquire():
        sys.exit(0)
    app._instance_guard = guard

    try:
        root.createcommand("::tk::mac::ReopenApplication", app.focus_input)
    except tk.TclError:
        pass

    root.after(150, app.focus_input)
    root.mainloop()


if __name__ == "__main__":
    main()

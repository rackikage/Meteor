"""Meteor — local-first agentic chat UI with full-shell tool access."""

from __future__ import annotations

import os
import socket
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import font
from typing import Callable, Optional

from app.gui.macos_window import configure_macos_window, macos_content_padx
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

APP_NAME = "METEOR"

WELCOME = """Meteor online. Local-first agentic AI, full shell + nmap + pentest tools.

Ask anything. If it needs the box or the network, I'll reach for a tool."""

HELP_TEXT = """Slash commands
──────────────
  /help              this panel
  /clear             wipe the chat
  /tools             list every registered tool
  /model             show the active model + provider
  /scope             re-discover local network scope

Everything else is free-form. Examples:
  scan the gateway with nmap
  read /etc/os-release and summarise
  what services are exposed on 10.0.0.5?
  run: ip route show
  posture check on the local firewall"""


FONT_MONO = "Menlo"
FONT_UI = "Helvetica Neue"


def _describe_active_model() -> str:
    try:
        from app.api.main import get_runtime
        rt = get_runtime()
        name = rt.model_registry._effective_default_profile()
        prof = rt.model_registry.config.models.profiles[name]
        return f"{name} ({prof.backend}:{prof.model_path})"
    except Exception:
        return "unknown"


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
        self.root.title("Meteor")
        self.root.configure(bg=BLACK)
        self.root.minsize(340, 420)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Free-floating default size; user resizes freely
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(540, int(sw * 0.38)), min(680, int(sh * 0.62))
        x, y = (sw - w) // 2, (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.session_id = f"met-{datetime.now(timezone.utc).strftime('%H%M%S')}"
        self._instance_guard: Optional[SingleInstanceGuard] = None
        self._busy = False
        self._runtime_ready = False
        self._scope: Optional[NetworkScope] = None
        self._typing_mark: Optional[str] = None
        self._stream_body_mark: Optional[str] = None
        self._history: list[dict] = []
        self._stream_text: str = ""

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
                model_hint = _describe_active_model()
                self.root.after(
                    0,
                    self._bot_message,
                    f"Scope locked.\n{lines}\n\nModel: {model_hint}\nReady — /help for slash commands, everything else is chat.",
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

        low = text.lower()
        if low in ("/clear", "clear"):
            self._clear_chat()
            return
        if low in ("/help", "help", "?"):
            self._user_message(text)
            self._bot_message(HELP_TEXT, "head")
            return
        if low in ("/tools",):
            self._user_message(text)
            self._show_tools()
            return
        if low in ("/model",):
            self._user_message(text)
            self._show_model()
            return
        if low in ("/scope",):
            self._user_message(text)
            self._rediscover_scope()
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

    def _show_tools(self) -> None:
        try:
            from app.tools.system.registry import get_registry
            tools = get_registry().list_tools()
        except Exception as exc:
            self._bot_message(f"Could not list tools: {exc}", "error")
            return
        if not tools:
            self._bot_message("No tools registered yet — runtime still warming.", "warn")
            return
        lines = ["Registered tools"]
        for t in tools:
            state = "on" if t.get("enabled", True) else "off"
            lines.append(f"  · {t['name']:<12} {state:>3}  {t.get('description', '')}")
        self._bot_message("\n".join(lines), "stdout")

    def _show_model(self) -> None:
        try:
            from app.api.main import get_runtime
            rt = get_runtime()
            registry = rt.model_registry
            profile_name = registry._effective_default_profile()
            profile = registry.config.models.profiles[profile_name]
            self._bot_message(
                f"Active model\n"
                f"  profile: {profile_name}\n"
                f"  backend: {profile.backend}\n"
                f"  model:   {profile.model_path}\n"
                f"  ctx:     {profile.context_window}",
                "stdout",
            )
        except Exception as exc:
            self._bot_message(f"Could not resolve model: {exc}", "error")

    def _rediscover_scope(self) -> None:
        def work() -> None:
            try:
                scope = discover_network_scope()
                self._scope = scope
                lines = "\n".join(f"  {line}" for line in scope.summary_lines())
                self.root.after(0, self._bot_message, f"Scope refreshed.\n{lines}", "info")
                self.root.after(0, self._set_footer, target=scope.gateway, scope=scope.cidr)
            except Exception as exc:
                self.root.after(0, self._bot_message, f"Scope discovery failed: {exc}", "error")
        threading.Thread(target=work, daemon=True).start()

    def _dispatch(self, raw: str) -> None:
        try:
            from app.agent.chatbot_loop import AgentChatLoop, AgentTurn, ChatMessage
            from app.api.main import get_runtime

            runtime = get_runtime()
            model = runtime.model_registry.get_adapter()
            loop = AgentChatLoop(model=model, tools=runtime.tool_executor)

            history = [
                ChatMessage(role=m["role"], content=m["content"])
                for m in self._history[-12:]
            ]
            turn = AgentTurn(
                prompt=raw,
                session_id=self.session_id,
                history=history,
                max_iterations=6,
                max_tokens=2048,
                temperature=0.5,
            )

            self.root.after(0, self._set_status, "thinking", MAGENTA)
            self._stream_text = ""

            def on_event(kind: str, payload: dict) -> None:
                if kind == "tool_call":
                    self.root.after(0, self._on_tool_call, payload)
                elif kind == "tool_result":
                    self.root.after(0, self._on_tool_result, payload)
                elif kind == "final_start":
                    self._stream_text = ""
                    self.root.after(0, self._begin_stream_bubble)
                elif kind == "final_token":
                    self._stream_text += payload.get("token", "")
                    snapshot = self._stream_text
                    self.root.after(0, self._update_stream_bubble, snapshot)
                elif kind == "final_done":
                    self.root.after(0, self._end_stream_bubble)
                elif kind == "error":
                    self.root.after(0, self._bot_message, payload.get("message", "error"), "error")
                elif kind == "iteration_limit":
                    self.root.after(0, self._bot_message, "[iteration limit reached]", "warn")

            final_text, _ = loop.run(turn, on_event)

            self._history.append({"role": "user", "content": raw})
            self._history.append({"role": "assistant", "content": final_text})
            self._history = self._history[-40:]

            self.root.after(0, self._end_stream_bubble)
            self.root.after(0, self._set_status, "armed", GREEN)
        except Exception as exc:
            self.root.after(0, self._set_status, "fault", RED)
            self.root.after(0, self._bot_message, f"Runtime fault: {exc}", "error")
        finally:
            self.root.after(0, self._finish_command)

    def _on_tool_call(self, payload: dict) -> None:
        tool = payload.get("tool", "?")
        op = payload.get("operation", "?")
        params = payload.get("params") or {}
        parts = []
        for k, v in params.items():
            preview = str(v)
            if len(preview) > 60:
                preview = preview[:57] + "…"
            parts.append(f"{k}={preview}")
        self._bot_message(f"⚙ {tool}.{op}({', '.join(parts)})", "accent")

    def _on_tool_result(self, payload: dict) -> None:
        tool = payload.get("tool", "?")
        op = payload.get("operation", "?")
        status = payload.get("status", "?")
        preview = payload.get("result_preview") or payload.get("error") or ""
        duration = payload.get("duration_ms", 0)
        tag = "stdout" if status == "ok" else "warn"
        header = f"↳ {tool}.{op} → {status} ({duration:.0f}ms)"
        if len(preview) > 1500:
            preview = preview[:1500] + "\n… [truncated]"
        self._bot_message(f"{header}\n{preview}" if preview else header, tag)

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

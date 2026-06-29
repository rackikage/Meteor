"""Meteor — Local-First AI Runtime
OLED Black · Neon Purple · Silver
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, font
import threading
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent
ICON_PATH = REPO / "assets" / "meteor_icon_64.png"
API_BASE = "http://localhost:8000"

# ── Palette ───────────────────────────────────────────────────────────
BLACK       = "#000000"
DARK        = "#0D0D0D"
CARD        = "#1A1A1A"
BORDER      = "#2D2D2D"
SILVER      = "#A0A0B0"
DIM_SILVER  = "#606070"
WHITE       = "#F0F0F0"
PURPLE      = "#B026FF"
DIM_PURPLE  = "#6A0DAD"
SOFT_PURPLE = "#8B5CF6"
CYAN        = "#00E5FF"
GREEN       = "#00E676"
AMBER       = "#FFD740"
RED         = "#FF5252"

MODEL_NAME  = "Meteor"
FONT_FAMILY = "Helvetica"
MSG_MAX_LEN = 80  # chars per line for word wrap

# ── Resolve font ───────────────────────────────────────────────────────
def _resolve_font(root: tk.Tk) -> str:
    try:
        avail = {f.name.lower() for f in font.families(root=root)}
        for name in ("Google Sans", "Product Sans", "Helvetica Neue", "Helvetica"):
            if name.lower() in avail:
                return name
    except Exception:
        pass
    return "Helvetica"


# ═══════════════════════════════════════════════════════════════════════
# Chat App
# ═══════════════════════════════════════════════════════════════════════
class MeteorChat:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Meteor")
        self.root.configure(bg=BLACK)
        self.root.geometry("820x620")
        self.root.minsize(600, 450)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.session_id = f"silk-{datetime.utcnow().timestamp():.0f}"
        self.chat_history: list[dict] = []
        self.tool_log: list[str] = []

        # App icon
        if ICON_PATH.exists():
            self._icon = tk.PhotoImage(file=str(ICON_PATH))
            self.root.iconphoto(True, self._icon)

        # Font
        global FONT_FAMILY
        FONT_FAMILY = _resolve_font(root)

        self._build_styles()
        self._build_header()
        self._build_chat()
        self._build_input()
        self._bind_keys()

        # Welcome message
        self._add_message("Meteor", (
            "Meteor runtime ready. I can scan networks, query the graph, "
            "and execute tools. What would you like to do?"
        ))

    # ── Styles ──────────────────────────────────────────────────────
    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BLACK, foreground=WHITE, font=(FONT_FAMILY, 11))
        style.configure("Card.TFrame", background=CARD)
        style.configure("Card.TLabel", background=CARD, foreground=SILVER, font=(FONT_FAMILY, 10))
        style.configure("Input.TEntry", fieldbackground=CARD, foreground=WHITE,
                        insertcolor=PURPLE, borderwidth=0, font=(FONT_FAMILY, 12))
        style.configure("Send.TButton", background=PURPLE, foreground=WHITE,
                        font=(FONT_FAMILY, 12, "bold"), borderwidth=0,
                        focuscolor="none", padding=(14, 6))
        style.map("Send.TButton", background=[("active", SOFT_PURPLE)])

    # ── Header ──────────────────────────────────────────────────────
    def _build_header(self) -> None:
        h = tk.Frame(self.root, bg=BLACK, height=52)
        h.pack(fill="x", side="top")
        h.pack_propagate(False)

        # Inner frame for padding
        inner = tk.Frame(h, bg=BLACK)
        inner.pack(fill="x", padx=18, pady=10)

        # Logo / icon
        if ICON_PATH.exists():
            img = tk.PhotoImage(file=str(ICON_PATH))
            lbl = tk.Label(inner, image=img, bg=BLACK)
            lbl.image = img
            lbl.pack(side="left", padx=(0, 10))

        # Model name
        name = tk.Label(inner, text=MODEL_NAME, bg=BLACK, fg=PURPLE,
                        font=(FONT_FAMILY, 15, "bold"))
        name.pack(side="left")

        # Dot indicator
        self._dot = tk.Canvas(inner, width=10, height=10, bg=BLACK, highlightthickness=0)
        self._dot.create_oval(1, 1, 9, 9, fill=GREEN, outline="")
        self._dot.pack(side="left", padx=6)

        # Subtitle
        tk.Label(inner, text="local-first · Meteor runtime", bg=BLACK, fg=DIM_SILVER,
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=4)

        # Status badge
        self._status = tk.Label(inner, text="idle", bg=BLACK, fg=DIM_SILVER,
                                font=(FONT_FAMILY, 9))
        self._status.pack(side="right")

        # Separator
        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill="x")

    # ── Chat area ───────────────────────────────────────────────────
    def _build_chat(self) -> None:
        outer = tk.Frame(self.root, bg=BLACK)
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        # Canvas for scrollable chat
        self._canvas = tk.Canvas(outer, bg=BLACK, highlightthickness=0,
                                 bd=0, relief="flat")
        self._scrollbar = tk.Scrollbar(outer, orient="vertical",
                                       command=self._canvas.yview,
                                       bg=BLACK, troughcolor=DARK,
                                       activebackground=PURPLE)
        self._msg_frame = tk.Frame(self._canvas, bg=BLACK)

        self._msg_frame.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))

        self._canvas.create_window((0, 0), window=self._msg_frame, anchor="nw",
                                   tags="msg_frame")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")

        # Mousewheel scroll
        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

        # Ensure inner frame matches canvas width
        self._canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfig("msg_frame", width=event.width)

    # ── Input bar ───────────────────────────────────────────────────
    def _build_input(self) -> None:
        bar = tk.Frame(self.root, bg=CARD, height=52)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill="x", side="bottom")

        self._input = tk.Entry(bar, bg=CARD, fg=WHITE, insertbackground=PURPLE,
                               font=(FONT_FAMILY, 12), bd=0, relief="flat",
                               highlightthickness=0)
        self._input.pack(side="left", fill="x", expand=True, padx=(14, 6), pady=10)
        self._input.insert(0, "")

        self._send_btn = tk.Button(bar, text="→", bg=PURPLE, fg=WHITE,
                                   font=(FONT_FAMILY, 14, "bold"), bd=0,
                                   activebackground=SOFT_PURPLE,
                                   activeforeground=WHITE,
                                   command=self._send,
                                   cursor="hand2", padx=16, pady=4)
        self._send_btn.pack(side="right", padx=(0, 10), pady=8)

    # ── Key bindings ────────────────────────────────────────────────
    def _bind_keys(self) -> None:
        self._input.bind("<Return>", lambda e: self._send())
        self.root.bind("<Escape>", lambda e: self._input.focus_set())

    # ── Messaging ───────────────────────────────────────────────────
    def _send(self) -> None:
        text = self._input.get().strip()
        if not text:
            return
        self._input.delete(0, "end")

        if text.lower() in ("/clear", "/reset"):
            self._clear_chat()
            return

        self._add_message("user", text)
        self.chat_history.append({"role": "user", "content": text})
        self._set_status("thinking", AMBER)
        self._dot.itemconfig(1, fill=AMBER)

        threading.Thread(target=self._call_api, args=(text,), daemon=True).start()

    def _add_message(self, sender: str, text: str) -> None:
        is_user = sender == "user"
        align = "e" if is_user else "w"
        bg = DIM_PURPLE if is_user else CARD
        fg = WHITE
        name = "you" if is_user else MODEL_NAME
        name_color = SOFT_PURPLE if is_user else PURPLE

        row = tk.Frame(self._msg_frame, bg=BLACK)
        row.pack(fill="x", padx=14, pady=(8, 0), anchor=align)

        # Sender label
        tk.Label(row, text=name, bg=BLACK, fg=name_color,
                 font=(FONT_FAMILY, 9, "bold")).pack(anchor=align, padx=4)

        # Bubble
        bubble = tk.Frame(row, bg=bg, padx=12, pady=8)
        bubble.pack(anchor=align, padx=2, pady=(2, 0))

        msg = tk.Label(bubble, text=text, bg=bg, fg=fg,
                       font=(FONT_FAMILY, 11), wraplength=680,
                       justify="left")
        msg.pack()

        self._canvas.yview_moveto(1.0)

    def _add_tool_entry(self, tool: str, status: str, detail: str = "") -> None:
        row = tk.Frame(self._msg_frame, bg=BLACK)
        row.pack(fill="x", padx=18, pady=(2, 0))

        icon = "✓" if status == "success" else "✗" if status == "error" else "○"
        color = GREEN if status == "success" else RED if status == "error" else CYAN

        tk.Label(row, text=f"{icon}  {tool}", bg=BLACK, fg=color,
                 font=(FONT_FAMILY, 9)).pack(side="left")
        if detail:
            tk.Label(row, text=f" — {detail[:60]}", bg=BLACK, fg=DIM_SILVER,
                     font=(FONT_FAMILY, 9)).pack(side="left")

        self._canvas.yview_moveto(1.0)

    def _set_status(self, text: str, color: str = DIM_SILVER) -> None:
        self._status.config(text=text, fg=color)

    def _clear_chat(self) -> None:
        for w in self._msg_frame.winfo_children():
            w.destroy()
        self.chat_history.clear()
        self._add_message("silk-o2", "Chat cleared. What's next?")

    # ── API call ────────────────────────────────────────────────────
    def _call_api(self, prompt: str) -> None:
        try:
            resp = requests.post(f"{API_BASE}/api/v1/chat", json={
                "prompt": prompt,
                "session_id": self.session_id,
                "max_tokens": 512,
                "temperature": 0.7,
                "stream": False,
                "metadata": {"source": "silk-o2-gui"},
            }, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("response_text", "")
                usage = data.get("token_usage", {})

                # Show tool calls if present in metadata
                tools = data.get("metadata", {}).get("tools_used", [])
                for t in tools:
                    self.root.after(0, self._add_tool_entry,
                                    t.get("name", "tool"),
                                    t.get("status", "ok"),
                                    t.get("detail", ""))

                self.chat_history.append({"role": "assistant", "content": reply})
                self.root.after(0, self._add_message, "silk-o2", reply)
                self.root.after(0, self._set_status,
                                f"{usage.get('total_tokens', 0)} tokens used", DIM_SILVER)
                self.root.after(0, lambda: self._dot.itemconfig(1, fill=GREEN))
            else:
                err = resp.json().get("detail", resp.text)
                self.root.after(0, self._add_message, "silk-o2", f"API error: {err}")
                self.root.after(0, self._set_status, "error", RED)
                self.root.after(0, lambda: self._dot.itemconfig(1, fill=RED))

        except requests.ConnectionError:
            self.root.after(0, self._add_message, "silk-o2",
                            "Cannot reach local API. Is the server running?")
            self.root.after(0, self._set_status, "offline", RED)
            self.root.after(0, lambda: self._dot.itemconfig(1, fill=RED))
        except Exception as e:
            self.root.after(0, self._add_message, "silk-o2", f"Error: {e}")
            self.root.after(0, self._set_status, "error", RED)
            self.root.after(0, lambda: self._dot.itemconfig(1, fill=RED))

    # ── Close ───────────────────────────────────────────────────────
    def _on_close(self) -> None:
        self.root.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Entry
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    root = tk.Tk()
    app = SilkChat(root)
    root.mainloop()


if __name__ == "__main__":
    main()

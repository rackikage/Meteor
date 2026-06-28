"""
Meteor GUI — Runtime Monitor
OLED Black · Neon Purple · Grey · White · Google Sans
Run: python3 meteor_gui.py
"""

import tkinter as tk
from tkinter import ttk, font
import subprocess
import threading
import time
import json
from pathlib import Path
import sys

# ── Paths ─────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent
CONFIG_PATH = REPO / "config" / "meteor.yaml"

# ── Colour Palette ────────────────────────────────────────────────────
BLACK      = "#000000"
DARK_GREY  = "#1A1A1A"
MID_GREY   = "#2D2D2D"
LIGHT_GREY = "#6B6B6B"
WHITE      = "#F0F0F0"
NEON_PURPLE = "#B026FF"
DIM_PURPLE  = "#6A0DAD"
SOFT_PURPLE = "#8B5CF6"

# ── Fonts ─────────────────────────────────────────────────────────────
FONT_FAMILY = "Google Sans"  # falls back to Segoe UI / Helvetica


def _find_google_sans() -> str:
    """Resolve Google Sans or best available fallback."""
    available = {f.name.lower() for f in font.families()}
    for name in ("Google Sans", "Product Sans", "Segoe UI", "Helvetica Neue", "Helvetica", "TkDefaultFont"):
        if name.lower() in available or name == "TkDefaultFont":
            return name
    return "TkDefaultFont"


GOOGLE_SANS = _find_google_sans()


# ── Styled Widget Builder ─────────────────────────────────────────────
class MeteorGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Meteor — Runtime Monitor")
        self.root.configure(bg=BLACK)
        self.root.geometry("780x560")
        self.root.minsize(640, 480)

        # ── Status data ───────────────────────────────────────────────
        self.status_data = {
            "app": "—",
            "version": "—",
            "local_first": "—",
            "model_profile": "—",
            "model_path": "—",
            "model_ok": "—",
            "runtime_wired": "False",
            "model_wired": "False",
            "ready": "—",
            "warnings": [],
        }

        # ── Build UI ──────────────────────────────────────────────────
        self._build_styles()
        self._build_header()
        self._build_status_cards()
        self._build_warnings_panel()
        self._build_footer()

        # ── Poll ──────────────────────────────────────────────────────
        self._poll_health()

    # ── Styles ────────────────────────────────────────────────────────
    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=BLACK, foreground=WHITE, font=(GOOGLE_SANS, 11))
        style.configure("Card.TFrame", background=DARK_GREY, relief="flat", borderwidth=1)
        style.configure("CardLabel.TLabel", background=DARK_GREY, foreground=LIGHT_GREY, font=(GOOGLE_SANS, 9))
        style.configure("CardValue.TLabel", background=DARK_GREY, foreground=WHITE, font=(GOOGLE_SANS, 13, "bold"))
        style.configure("StatusGreen.TLabel", background=DARK_GREY, foreground="#00E676", font=(GOOGLE_SANS, 13, "bold"))
        style.configure("StatusRed.TLabel", background=DARK_GREY, foreground="#FF5252", font=(GOOGLE_SANS, 13, "bold"))
        style.configure("StatusAmber.TLabel", background=DARK_GREY, foreground="#FFD740", font=(GOOGLE_SANS, 13, "bold"))
        style.configure("Header.TLabel", background=BLACK, foreground=NEON_PURPLE, font=(GOOGLE_SANS, 22, "bold"))
        style.configure("SubHeader.TLabel", background=BLACK, foreground=LIGHT_GREY, font=(GOOGLE_SANS, 10))
        style.configure("WarnFrame.TFrame", background="#1A0D20", relief="flat", borderwidth=1)
        style.configure("WarnText.TLabel", background="#1A0D20", foreground="#FFD740", font=(GOOGLE_SANS, 10))
        style.configure("Footer.TLabel", background=BLACK, foreground=MID_GREY, font=(GOOGLE_SANS, 8))
        style.configure("Refresh.TButton", background=MID_GREY, foreground=WHITE, font=(GOOGLE_SANS, 10),
                        borderwidth=0, focuscolor="none")
        style.map("Refresh.TButton",
                  background=[("active", NEON_PURPLE), ("pressed", DIM_PURPLE)],
                  foreground=[("active", WHITE)])

    # ── Header ────────────────────────────────────────────────────────
    def _build_header(self) -> None:
        header_frame = tk.Frame(self.root, bg=BLACK)
        header_frame.pack(fill="x", padx=24, pady=(20, 4))

        # Logo mark
        logo_canvas = tk.Canvas(header_frame, width=32, height=32, bg=BLACK, highlightthickness=0)
        logo_canvas.create_oval(4, 4, 28, 28, outline=NEON_PURPLE, width=2)
        logo_canvas.create_oval(10, 10, 22, 22, fill=NEON_PURPLE, outline="")
        logo_canvas.pack(side="left", padx=(0, 12))
        logo_canvas.create_text(16, 16, text="M", fill=BLACK, font=(GOOGLE_SANS, 14, "bold"))

        title_frame = tk.Frame(header_frame, bg=BLACK)
        title_frame.pack(side="left", fill="x", expand=True)

        ttk.Label(title_frame, text="Meteor", style="Header.TLabel").pack(anchor="w")
        ttk.Label(title_frame, text="Local-first AI runtime · Runtime monitor", style="SubHeader.TLabel").pack(anchor="w")

        # Status badge
        self.badge = tk.Canvas(header_frame, width=80, height=28, bg=BLACK, highlightthickness=0)
        self.badge.pack(side="right", padx=(0, 0))
        self._draw_badge("OFFLINE", MID_GREY)

        sep = tk.Frame(self.root, bg=MID_GREY, height=1)
        sep.pack(fill="x", padx=24, pady=(8, 12))

    def _draw_badge(self, text: str, colour: str) -> None:
        self.badge.delete("all")
        self.badge.create_oval(6, 7, 18, 19, fill=colour, outline="")
        self.badge.create_text(46, 13, text=text, fill=colour, font=(GOOGLE_SANS, 9, "bold"))

    # ── Status Cards ──────────────────────────────────────────────────
    def _build_status_cards(self) -> None:
        cards_frame = tk.Frame(self.root, bg=BLACK)
        cards_frame.pack(fill="x", padx=24, pady=(0, 12))

        self.cards: dict[str, dict] = {}

        card_specs: list[tuple[str, str]] = [
            ("App", "app"),
            ("Version", "version"),
            ("Model", "model_profile"),
            ("GGUF", "model_ok"),
            ("Runtime", "runtime_wired"),
            ("Inference", "model_wired"),
        ]

        for i, (label, key) in enumerate(card_specs):
            card = tk.Frame(cards_frame, bg=DARK_GREY, highlightbackground=MID_GREY, highlightthickness=1, padx=14, pady=10)
            card.grid(row=0, column=i, padx=4, pady=4, sticky="nsew")
            cards_frame.grid_columnconfigure(i, weight=2 if i in (0, 1) else 1, minsize=90)

            lbl = ttk.Label(card, text=label.upper(), style="CardLabel.TLabel")
            lbl.pack(anchor="w")

            val = ttk.Label(card, text="—", style="CardValue.TLabel")
            val.pack(anchor="w", pady=(2, 0))

            self.cards[key] = val

    # ── Warnings Panel ────────────────────────────────────────────────
    def _build_warnings_panel(self) -> None:
        warn_container = tk.Frame(self.root, bg=BLACK)
        warn_container.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        warn_header = tk.Frame(warn_container, bg=BLACK)
        warn_header.pack(fill="x", pady=(0, 6))

        ttk.Label(warn_header, text="WARNINGS", style="CardLabel.TLabel").pack(side="left")
        self.warn_count = ttk.Label(warn_header, text="0", style="CardLabel.TLabel")
        self.warn_count.pack(side="right")

        self.warn_frame = tk.Frame(warn_container, bg="#1A0D20", highlightbackground=DIM_PURPLE, highlightthickness=1)
        self.warn_frame.pack(fill="both", expand=True)

        self.warn_inner = tk.Frame(self.warn_frame, bg="#1A0D20", padx=12, pady=10)
        self.warn_inner.pack(fill="both", expand=True)

        self.warn_label = ttk.Label(
            self.warn_inner,
            text="No warnings. All systems nominal.",
            style="WarnText.TLabel",
            wraplength=680,
        )
        self.warn_label.pack(anchor="w")

    # ── Footer ────────────────────────────────────────────────────────
    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, bg=BLACK)
        footer.pack(fill="x", padx=24, pady=(4, 14))

        self.last_updated = ttk.Label(footer, text="Last update: —", style="Footer.TLabel")
        self.last_updated.pack(side="left")

        refresh_btn = ttk.Button(footer, text="⟳ Refresh", style="Refresh.TButton", command=self._force_refresh)
        refresh_btn.pack(side="right")

    # ── Health Poll ───────────────────────────────────────────────────
    def _poll_health(self) -> None:
        def _run() -> None:
            try:
                import yaml
                from app.bootstrap import bootstrap
                result = bootstrap(CONFIG_PATH)
                self.status_data = {
                    "app": result.config.app.name,
                    "version": result.config.app.version,
                    "local_first": str(result.config.app.local_first),
                    "model_profile": result.config.models.default_profile,
                    "model_path": str(result.default_model_path),
                    "model_ok": "FOUND" if result.default_model_path.exists() else "MISSING",
                    "runtime_wired": "False",
                    "model_wired": "False",
                    "ready": str(result.ready),
                    "warnings": result.warnings,
                }
            except Exception as e:
                self.status_data["warnings"] = [f"Health check failed: {e}"]

            self.root.after(0, self._update_ui)

        threading.Thread(target=_run, daemon=True).start()
        self.root.after(5000, self._poll_health)

    def _force_refresh(self) -> None:
        self._poll_health()

    # ── UI Update ─────────────────────────────────────────────────────
    def _update_ui(self) -> None:
        d = self.status_data

        self.cards["app"].configure(text=d["app"])
        self.cards["version"].configure(text=f"v{d['version']}")
        self.cards["model_profile"].configure(text=d["model_profile"])

        # Model status
        model_ok = d["model_ok"]
        model_label = self.cards["model_ok"]
        if model_ok == "FOUND":
            model_label.configure(text="✓ FOUND", style="StatusGreen.TLabel")
        else:
            model_label.configure(text="✗ MISSING", style="StatusRed.TLabel")

        # Runtime wired
        rw = self.cards["runtime_wired"]
        rw.configure(text="✗ DISABLED", style="StatusRed.TLabel")

        # Model wired
        mw = self.cards["model_wired"]
        mw.configure(text="✗ DISABLED", style="StatusRed.TLabel")

        # Badge
        ready = d["ready"] == "True" and model_ok == "FOUND"
        if ready:
            self._draw_badge("READY", "#00E676")
        elif d["ready"] == "True":
            self._draw_badge("DEGRADED", "#FFD740")
        else:
            self._draw_badge("OFFLINE", "#FF5252")

        # Warnings
        warnings = d["warnings"]
        self.warn_count.configure(text=str(len(warnings)))
        for w in self.warn_inner.winfo_children():
            w.destroy()
        if warnings:
            self.warn_frame.configure(highlightbackground="#FFD740")
            for w in warnings:
                ttk.Label(self.warn_inner, text=f"⚠  {w}", style="WarnText.TLabel",
                          wraplength=660).pack(anchor="w", pady=1)
        else:
            self.warn_frame.configure(highlightbackground=DIM_PURPLE)
            ttk.Label(self.warn_inner, text="No warnings. All systems nominal.",
                      style="WarnText.TLabel", foreground=SOFT_PURPLE).pack(anchor="w")

        # Timestamp
        self.last_updated.configure(text=f"Last update: {time.strftime('%H:%M:%S')}")


# ── Entry ─────────────────────────────────────────────────────────────
def main() -> None:
    root = tk.Tk()
    app = MeteorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

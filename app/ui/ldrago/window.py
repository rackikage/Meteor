"""Main application window."""
import os
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from . import theme as theme_mod
from . import settings as settings_mod
from . import meter as meter_mod
from . import chat as chat_mod
from . import ai as ai_mod
from . import APP_ID


class _MeterBar(Gtk.Box):
    def __init__(self, label: str, palette: dict, icon: str = "•"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(xalign=0)
        title.set_markup(
            f"<span foreground='{palette['ember']}'><b>{icon}</b></span>  "
            f"<span foreground='{palette['text']}'><b>{label}</b></span>"
        )
        self.val_lbl = Gtk.Label(label="—", xalign=1, hexpand=True)
        self.val_lbl.set_markup(f"<span foreground='{palette['muted']}'>—</span>")
        head.append(title)
        head.append(self.val_lbl)
        self.append(head)
        self.bar = Gtk.ProgressBar()
        self.bar.set_valign(Gtk.Align.START)
        self.bar.set_size_request(-1, 6)
        self.bar.add_css_class("meteor-bar")
        self.append(self.bar)

    def set(self, pct: float, color: str) -> None:
        self.bar.set_fraction(max(0.0, min(1.0, pct / 100.0)))
        self.val_lbl.set_markup(
            f"<span foreground='{color}'><b>{pct:5.1f}%</b></span>"
        )


class LDragoWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Meteor L·Drago",
                         default_width=1100, default_height=720)
        self.settings = settings_mod.load_settings()
        self.history = settings_mod.load_history()
        self.palette = theme_mod.get(self.settings["dark"])
        self._last_bubble = None
        self._build()
        self._apply_color_scheme()
        GLib.timeout_add(self.settings.get("refresh_ms", 1500), self._tick)
        GLib.idle_add(self._tick)

    def _apply_color_scheme(self):
        sm = Adw.StyleManager.get_default()
        sm.set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if self.settings["dark"]
            else Adw.ColorScheme.FORCE_LIGHT
        )

    def _install_css(self):
        p = self.palette
        css = (
            f"window {{ background: {p['bg']}; }}"
            f"headerbar {{ background: {p['surface']}; border-bottom: 1px solid {p['border']}; }}"
            f".meteor-side {{ background: {p['surface']}; border-right: 1px solid {p['border']}; }}"
            f".meteor-card {{ background: {p['surface']}; border: 1px solid {p['border']};"
            f" border-radius: 14px; padding: 14px; }}"
            f"progressbar.meteor-bar trough {{ background: {p['border']}; border-radius: 3px; min-height: 6px; }}"
            f"progressbar.meteor-bar progress {{ background: linear-gradient(90deg,"
            f" {p['ember']} 0%, {p['amber']} 50%, {p['violet']} 100%); border-radius: 3px;"
            f" min-height: 6px; }}"
            f"entry {{ background: {p['surface2']}; border: 1px solid {p['border']};"
            f" border-radius: 10px; padding: 10px 14px; color: {p['text']}; }}"
            f"entry:focus {{ border-color: {p['ember']}; }}"
            f"button.meteor-send {{ background: {p['ember']}; color: #fff; border-radius: 10px;"
            f" padding: 8px 18px; border: none; font-weight: bold; }}"
            f"button.meteor-send:hover {{ background: {p['amber']}; }}"
            f"scrolledwindow {{ background: {p['bg']}; }}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build(self):
        self._install_css()
        p = self.palette
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_hexpand(True)
        title_box.set_halign(Gtk.Align.CENTER)
        glow = Gtk.Label()
        glow.set_markup(f"<span foreground='{p['ember']}' size='x-large'>◉</span>")
        tt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        t1 = Gtk.Label()
        t1.set_markup(f"<span foreground='{p['text']}' size='large' weight='bold'>meteor</span>")
        t2 = Gtk.Label()
        t2.set_markup(f"<span foreground='{p['violet']}' size='small' weight='bold'>L·DRAGO</span>")
        tt.append(t1)
        tt.append(t2)
        title_box.append(glow)
        title_box.append(tt)
        header.set_title_widget(title_box)
        theme_btn = Gtk.Button(icon_name="display-brightness-symbolic",
                               tooltip_text="Toggle dark / light")
        theme_btn.connect("clicked", self._toggle_theme)
        header.pack_end(theme_btn)
        clear_btn = Gtk.Button(icon_name="edit-clear-all-symbolic",
                               tooltip_text="Clear chat")
        clear_btn.connect("clicked", self._clear_chat)
        header.pack_end(clear_btn)
        outer.append(header)
        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        outer.append(main)
        self.set_content(outer)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        side.set_size_request(340, -1)
        side.set_css_classes(["meteor-side"])
        side.set_margin_top(18)
        side.set_margin_bottom(18)
        side.set_margin_start(18)
        side.set_margin_end(14)
        self.cpu_bar = _MeterBar("CPU", p, "⚡")
        self.ram_bar = _MeterBar("Memory", p, "▣")
        self.disk_bar = _MeterBar("Disk /", p, "◐")
        for b in (self.cpu_bar, self.ram_bar, self.disk_bar):
            side.append(b)
        net_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        net_card.set_css_classes(["meteor-card"])
        net_title = Gtk.Label(xalign=0)
        net_title.set_markup(
            f"<span foreground='{p['ember']}'><b>⇅</b></span>  "
            f"<span foreground='{p['text']}'><b>Network</b></span>"
        )
        self.net_lbl = Gtk.Label(xalign=0)
        self.net_lbl.set_markup(
            f"<span foreground='{p['muted']}'>down — · up —</span>"
        )
        net_card.append(net_title)
        net_card.append(self.net_lbl)
        side.append(net_card)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_margin_top(20)
        info.set_valign(Gtk.Align.END)
        info.set_vexpand(True)
        l1 = Gtk.Label(xalign=0)
        l1.set_markup(
            f"<span foreground='{p['violet']}' size='small'><b>L·DRAGO</b></span>  "
            f"<span foreground='{p['muted']}' size='small'>v0.1.0</span>"
        )
        l2 = Gtk.Label(xalign=0)
        l2.set_markup(f"<span foreground='{p['muted']}' size='small'>on {os.uname().nodename}</span>")
        info.append(l1)
        info.append(l2)
        side.append(info)
        main.append(side)
        self.chat_panel = chat_mod.ChatPanel(p, self._on_send)
        main.append(self.chat_panel)
        for msg in self.history:
            self.chat_panel.render(msg)
        self.chat_panel.scroll_end()

    def _toggle_theme(self, *_):
        self.settings["dark"] = not self.settings["dark"]
        settings_mod.save_settings(self.settings)
        self.palette = theme_mod.get(self.settings["dark"])
        self._apply_color_scheme()
        old = self.get_content()
        self.set_content(Gtk.Box(orientation=Gtk.Orientation.VERTICAL))
        old.unparent()
        self._build()

    def _clear_chat(self, *_):
        self.history = [{
            "role": "assistant",
            "content": "Cleared. New thread — Meteor L·Drago listening.",
        }]
        settings_mod.save_history(self.history)
        self.chat_panel.clear()
        self.chat_panel.render(self.history[0])

    def _tick(self) -> bool:
        try:
            data = meter_mod.collect()
            p = self.palette
            self.cpu_bar.set(data["cpu"], self._meter_color(data["cpu"]))
            self.ram_bar.set(data["mem"], self._meter_color(data["mem"]))
            self.disk_bar.set(data["disk"], self._meter_color(data["disk"]))
            self.net_lbl.set_markup(
                f"<span foreground='{p['green']}'><b>↓ {meter_mod.fmt_bytes(data['net_rx_kbs'])}</b></span>  "
                f"<span foreground='{p['amber']}'><b>↑ {meter_mod.fmt_bytes(data['net_tx_kbs'])}</b></span>"
            )
        except Exception as e:
            print("tick err:", e)
        return True

    def _meter_color(self, pct):
        p = self.palette
        if pct < 75:
            return p["good"]
        if pct < 90:
            return p["amber"]
        return p["red"]

    def _on_send(self, text: str):
        self.history.append({"role": "user", "content": text})
        self.chat_panel.render(self.history[-1])
        self.history.append({"role": "assistant", "content": ""})
        self.chat_panel.render(self.history[-1])
        self._last_bubble = self.chat_panel.last_bubble
        settings_mod.save_history(self.history)
        self.chat_panel.scroll_end()
        if self.settings.get("ai_enabled", True):
            threading.Thread(target=self._ai_call, args=(text,), daemon=True).start()
        else:
            GLib.idle_add(self._last_bubble.append_text,
                          "AI disabled. Toggle in settings.", self.palette)
            settings_mod.save_history(self.history)

    def _ai_call(self, _prompt: str):
        try:
            def on_chunk(chunk):
                self.history[-1]["content"] += chunk
                GLib.idle_add(self._last_bubble.append_text, chunk, self.palette)
            ai_mod.stream_chat(
                self.history[:-1],
                self.settings.get("ollama_url", "http://127.0.0.1:11434"),
                self.settings.get("model", "llama3.2"),
                on_chunk,
            )
        except Exception as e:
            err = f"\n\n[ai error: {e}]"
            self.history[-1]["content"] += err
            GLib.idle_add(self._last_bubble.append_text, err, self.palette)
        settings_mod.save_history(self.history)


class LDragoApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window or LDragoWindow(self)
        win.present()


def main():
    app = LDragoApp()
    return app.run(None)

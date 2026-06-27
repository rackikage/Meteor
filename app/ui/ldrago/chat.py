"""Chat panel + markdown bubble renderer."""
import re
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib


class ChatBubble(Gtk.Box):
    def __init__(self, role: str, text: str, palette: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.role = role
        self.text = text
        bg = palette["surface2"] if role == "user" else palette["surface"]
        accent = palette["ember"] if role == "user" else palette["violet"]
        self.set_css_classes(["meteor-bubble"])
        self.set_halign(Gtk.Align.START if role == "assistant" else Gtk.Align.END)
        self.set_size_request(280, -1)
        name = Gtk.Label(xalign=0)
        name.set_markup(
            f"<span foreground='{accent}'><b>{'you' if role == 'user' else 'meteor'}</b></span>"
            f"  <span foreground='{palette['muted']}' size='small'>{role}</span>"
        )
        self.body = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.body.set_markup(self._md(text, palette))
        self.body.set_size_request(260, -1)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.append(name)
        inner.append(self.body)
        self.append(inner)

    @staticmethod
    def _md(text: str, palette: dict) -> str:
        out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        out = re.sub(r"```([\s\S]*?)```",
                     lambda m: f"<tt><span foreground='{palette['cyan']}'>{m.group(1).strip()}</span></tt>",
                     out)
        out = re.sub(r"`([^`]+)`",
                     lambda m: f"<tt><span foreground='{palette['cyan']}'>{m.group(1)}</span></tt>",
                     out)
        out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
        out = re.sub(r"(?m)^&gt; (.+)$",
                     lambda m: f"<span foreground='{palette['muted']}'>  │ {m.group(1)}</span>",
                     out)
        return out.replace("\n", "<br>")

    def append_text(self, chunk: str, palette: dict) -> None:
        self.text += chunk
        self.body.set_markup(self._md(self.text, palette))


class ChatPanel(Gtk.Box):
    def __init__(self, palette: dict, on_send):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.palette = palette
        self._on_send = on_send
        self.last_bubble = None
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_margin_top(18)
        self.set_margin_end(18)
        self.set_margin_bottom(18)
        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        scroll.set_vexpand(True)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.list_box.set_margin_start(8)
        self.list_box.set_margin_end(8)
        self.list_box.set_margin_top(4)
        self.list_box.set_margin_bottom(4)
        scroll.set_child(self.list_box)
        self.append(scroll)
        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_row.set_margin_top(10)
        self.entry = Gtk.Entry(placeholder_text="ask meteor anything…")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._handle_send)
        send = Gtk.Button(label="send")
        send.add_css_class("meteor-send")
        send.connect("clicked", self._handle_send)
        input_row.append(self.entry)
        input_row.append(send)
        self.append(input_row)
        self._scroll = scroll

    def _handle_send(self, *_):
        text = self.entry.get_text().strip()
        if not text:
            return
        self.entry.set_text("")
        self._on_send(text)

    def render(self, message: dict) -> ChatBubble:
        bubble = ChatBubble(message["role"], message["content"], self.palette)
        self.list_box.append(bubble)
        if message["role"] == "assistant":
            self.last_bubble = bubble
        return bubble

    def scroll_end(self):
        adj = self._scroll.get_vadjustment()
        GLib.idle_add(lambda: (adj.set_value(adj.get_upper()), False)[1])

    def clear(self):
        while True:
            c = self.list_box.get_first_child()
            if not c:
                break
            self.list_box.remove(c)

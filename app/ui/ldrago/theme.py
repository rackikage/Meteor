"""Dark / light palette. Low-contrast, high-vivid, easy on the eyes for long sessions."""
DARK = {
    "bg": "#0d0e12", "surface": "#161821", "surface2": "#1d2030",
    "border": "#262a3a", "text": "#e6e7ea", "muted": "#8b90a3",
    "ember": "#FF5E3A", "violet": "#7A5BFF",
    "cyan": "#3FD9E8", "green": "#4CD27A", "amber": "#FFB347",
    "red": "#FF4D6D", "good": "#4CD27A",
}
LIGHT = {
    "bg": "#f6f7fa", "surface": "#eef0f4", "surface2": "#e3e6ed",
    "border": "#d3d7e0", "text": "#1a1b1f", "muted": "#6b7080",
    "ember": "#D6361A", "violet": "#6A4DE0",
    "cyan": "#1AA8B8", "green": "#1F9A4F", "amber": "#C77800",
    "red": "#D6264A", "good": "#1F9A4F",
}


def get(dark: bool) -> dict:
    return DARK if dark else LIGHT

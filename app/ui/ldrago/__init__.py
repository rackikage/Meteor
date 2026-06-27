"""Meteor L·Drago — desktop front-end for the Meteor runtime.

Replaces nothing in the runtime itself. Per doctrine, the UI is a replaceable
adapter. This module ships a GTK4/libadwaita app that pairs a system meter
panel with a streaming chat panel. The chat adapter speaks to any
Ollama-compatible HTTP endpoint by default; swap `ai.py` for a real Meteor
runtime client when one exists.
"""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

__version__ = "0.1.0"
APP_ID = "io.github.emperor.meteorldrago"

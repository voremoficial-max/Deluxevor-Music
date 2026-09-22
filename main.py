#!/usr/bin/env python3
"""Deluxevor Music - Punto de entrada."""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")

from gi.repository import Gst

from app.application import VoremApplication


def main():
    Gst.init(None)
    app = VoremApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

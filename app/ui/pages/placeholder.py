"""Página simple usada como marcador de posición en la Fase 1."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class PlaceholderPage(Gtk.Box):
    """Contenido temporal para secciones que se implementan en fases futuras."""

    def __init__(self, title: str, message: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_spacing(8)

        status = Adw.StatusPage(
            title=title,
            description=message,
            icon_name="folder-music-symbolic",
        )
        self.append(status)

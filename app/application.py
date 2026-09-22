"""Clase principal de la aplicación Deluxevor Music."""
import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from app.ui.window import VoremWindow
from app.utils.logger import get_logger

logger = get_logger(__name__)

APP_ID = "com.vorem.Music"


class VoremApplication(Adw.Application):
    """Adw.Application que gestiona el ciclo de vida de Deluxevor Music."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None

    def do_activate(self):
        """Se llama cada vez que se activa la aplicación (arranque normal)."""
        if not self.window:
            self.window = VoremWindow(application=self)
            logger.info("Ventana principal creada")
        self.window.present()

    def do_startup(self):
        """Configuración que solo debe ocurrir una vez, al iniciar."""
        Adw.Application.do_startup(self)
        logger.info("Deluxevor Music iniciando...")

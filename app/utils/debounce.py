"""Pequeña utilidad para no ejecutar una función en cada pulsación de tecla.

Se usa en los buscadores de las páginas (Canciones, Álbumes, Artistas,
Géneros) para no reconstruir toda la lista de golpe en cada tecla escrita
cuando hay muchas canciones — solo se ejecuta cuando el usuario deja de
teclear por un instante.
"""
from gi.repository import GLib


class Debouncer:
    def __init__(self, delay_ms: int = 180):
        self.delay_ms = delay_ms
        self._source_id = None

    def call(self, func):
        self.cancel()

        def run():
            self._source_id = None
            func()
            return False

        self._source_id = GLib.timeout_add(self.delay_ms, run)

    def cancel(self):
        if self._source_id is not None:
            GLib.source_remove(self._source_id)
            self._source_id = None

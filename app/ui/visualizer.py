"""Visualizador de espectro real, reactivo y de bajo consumo."""
import math
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


class SpectrumWidget(Gtk.DrawingArea):
    """32 barras independientes: cada barra representa una banda de frecuencia."""

    BAND_COUNT = 29
    TICK_MS = 35
    DB_FLOOR = -78.0
    SENSITIVITY = 1.48

    def __init__(self):
        super().__init__()
        self.set_content_height(42)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)
        self._levels = [0.0] * self.BAND_COUNT
        self._targets = [0.0] * self.BAND_COUNT
        self._peaks = [0.0] * self.BAND_COUNT
        self._active = False
        self._enabled = True
        self._intensity = self.SENSITIVITY
        self._timer = None

    def set_spectrum(self, values):
        if not values:
            return

        source = list(values)
        for i in range(self.BAND_COUNT):
            # Cada barra toma una banda concreta del espectro recibido.
            # El reparto evita que las barras finales queden sin datos si
            # GStreamer devuelve un número de bandas diferente.
            index = min(len(source) - 1, int(i * len(source) / self.BAND_COUNT))
            try:
                db = float(source[index])
            except (TypeError, ValueError):
                db = self.DB_FLOOR

            normalized = (db - self.DB_FLOOR) / abs(self.DB_FLOOR)
            normalized = max(0.0, min(1.0, normalized))

            # La curva reduce los niveles medios para evitar que las barras
            # permanezcan altas todo el tiempo. Los picos fuertes conservan
            # suficiente respuesta para que los golpes de la música destaquen.
            level = min(1.0, (normalized ** 1.65) * self._intensity)
            self._targets[i] = level
            self._peaks[i] = max(self._peaks[i] * 0.94, level)

        self._active = True
        self._ensure_timer()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if not self._enabled:
            self.set_active(False)
        self.queue_draw()

    def set_intensity(self, intensity):
        self._intensity = max(0.8, min(2.0, float(intensity)))

    def set_active(self, active):
        self._active = bool(active) and self._enabled
        if self._active:
            self._ensure_timer()
        else:
            self._targets = [0.0] * self.BAND_COUNT
            self._peaks = [0.0] * self.BAND_COUNT
            if self._timer is not None:
                GLib.source_remove(self._timer)
                self._timer = None
            self.queue_draw()

    def reset(self):
        self._levels = [0.0] * self.BAND_COUNT
        self._targets = [0.0] * self.BAND_COUNT
        self._peaks = [0.0] * self.BAND_COUNT
        self.queue_draw()

    def _ensure_timer(self):
        if self._timer is None:
            self._timer = GLib.timeout_add(self.TICK_MS, self._animate)

    def _animate(self):
        changed = False
        for i in range(self.BAND_COUNT):
            target = self._targets[i] if self._active else 0.0
            current = self._levels[i]
            # Ataque rápido para que golpes de batería/bajo se noten; caída
            # algo más lenta para que el movimiento sea suave.
            factor = 0.48 if target > current else 0.20
            new_value = current + (target - current) * factor
            if abs(new_value - current) > 0.001:
                changed = True
            self._levels[i] = new_value

            if self._active:
                self._peaks[i] = max(0.0, self._peaks[i] - 0.018)

        if changed or self._active:
            self.queue_draw()

        if not self._active and not changed:
            self._timer = None
            return False
        return True

    def do_unroot(self):
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
        super().do_unroot()

    def _draw(self, _area, cr, width, height):
        count = self.BAND_COUNT
        gap = 1.7
        bar_width = max(1.0, (width - gap * (count - 1)) / count)
        usable_height = max(4.0, height - 3.0)

        for i, level in enumerate(self._levels):
            bar_height = max(2.0, level * usable_height)
            x = i * (bar_width + gap)
            y = height - bar_height

            # Las primeras barras son graves, las centrales medios y las últimas
            # agudos. Cada barra sigue siendo independiente y corresponde a una
            # banda concreta del espectro.
            if i < 10:
                cr.set_source_rgba(0.35, 0.78, 1.0, 0.92)
            elif i < 22:
                cr.set_source_rgba(0.48, 0.90, 0.70, 0.92)
            else:
                cr.set_source_rgba(0.82, 0.65, 1.0, 0.92)

            radius = min(1.8, bar_width / 2)
            self._rounded_rect(cr, x, y, bar_width, bar_height, radius)
            cr.fill()

            # Pequeño pico por barra para hacer más visibles los ataques.
            peak = self._peaks[i]
            if peak > level + 0.03:
                peak_y = height - peak * usable_height
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.65)
                cr.rectangle(x, max(0, peak_y), bar_width, 1.2)
                cr.fill()

    @staticmethod
    def _rounded_rect(cr, x, y, width, height, radius):
        cr.new_sub_path()
        cr.arc(x + radius, y + radius, radius, math.pi, 1.5 * math.pi)
        cr.arc(x + width - radius, y + radius, radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(x + width - radius, y + height - radius, radius, 0, 0.5 * math.pi)
        cr.arc(x + radius, y + height - radius, radius, 0.5 * math.pi, math.pi)
        cr.close_path()

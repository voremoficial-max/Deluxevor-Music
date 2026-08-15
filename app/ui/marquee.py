"""Etiqueta con desplazamiento horizontal suave para títulos largos."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GLib, Gtk, Pango, PangoCairo


class MarqueeLabel(Gtk.DrawingArea):
    """Texto desplazable dentro de un ancho fijo, reiniciando cada 5 segundos."""

    CYCLE_US = 5_000_000

    def __init__(self, text="", speed=28.0):
        super().__init__()
        self.set_content_height(22)
        self.set_content_width(150)
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)
        self.set_draw_func(self._draw)
        self._text = text or ""
        self._speed = float(speed)
        self._offset = 0.0
        self._text_width = 0
        self._last_us = GLib.get_monotonic_time()
        self._cycle_started_us = self._last_us
        self._timer = GLib.timeout_add(40, self._tick)

    def set_text(self, text):
        text = text or ""
        self._text = text
        self._offset = 0.0
        now = GLib.get_monotonic_time()
        self._last_us = now
        self._cycle_started_us = now
        self.queue_draw()

    def do_unroot(self):
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
        super().do_unroot()

    def _layout(self):
        layout = self.create_pango_layout(self._text)
        layout.set_single_paragraph_mode(True)
        layout.set_ellipsize(Pango.EllipsizeMode.NONE)
        self._text_width, _ = layout.get_pixel_size()
        return layout

    def _tick(self):
        if not self.get_mapped():
            return True
        width = self.get_width()
        if width <= 0 or not self._text:
            return True

        layout = self._layout()
        overflow = self._text_width - width
        now = GLib.get_monotonic_time()
        dt = max(0.0, min(0.12, (now - self._last_us) / 1_000_000.0))
        self._last_us = now

        # Cada 5 segundos el movimiento vuelve exactamente al inicio.
        if now - self._cycle_started_us >= self.CYCLE_US:
            self._offset = 0.0
            self._cycle_started_us = now

        if overflow > 8:
            # Los primeros ~0.5 s de cada ciclo dejan ver el título completo.
            elapsed = now - self._cycle_started_us
            if elapsed > 500_000:
                self._offset = min(float(overflow), self._offset + self._speed * dt)
            self.queue_draw()
        elif self._offset != 0:
            self._offset = 0.0
            self.queue_draw()
        return True

    def _draw(self, _area, cr, width, height):
        layout = self._layout()
        overflow = max(0, self._text_width - width)
        x = -self._offset if overflow > 8 else 0
        cr.save()
        cr.rectangle(0, 0, width, height)
        cr.clip()
        cr.set_source_rgba(1, 1, 1, 1)
        PangoCairo.update_layout(cr, layout)
        cr.move_to(x, max(0, (height - layout.get_pixel_size()[1]) / 2))
        PangoCairo.show_layout(cr, layout)
        cr.restore()

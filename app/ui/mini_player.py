"""Minireproductor flotante de Deluxevor Music (Control+J).

Es una ventana pequeña e independiente con la carátula, los controles de
reproducir/pausar/anterior/siguiente y la barra de progreso de la canción.
A propósito NO incluye el visualizador de barras del reproductor grande:
solo la barra de progreso, para mantenerla compacta y ligera.
"""
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from app.ui.marquee import MarqueeLabel


def format_time(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"


class MiniPlayerWindow(Gtk.Window):
    def __init__(self, engine, on_previous=None, on_next=None, parent=None, on_toggle_window=None):
        super().__init__(title="Deluxevor Music — Mini reproductor")
        self.engine = engine
        self.on_previous = on_previous
        self.on_next = on_next
        # Callback de la ventana principal para intercambiar mini/grande.
        # Se usa tanto para Control+J (con el foco en esta ventana) como
        # para el botón/gesto nativo de cerrar, de modo que cerrar el
        # minireproductor de cualquier forma siempre devuelva el reproductor
        # grande en vez de dejar la app sin ninguna ventana visible.
        self.on_toggle_window = on_toggle_window
        self._duration = 0.0
        self._seeking = False

        self.set_default_size(240, 300)
        self.set_size_request(220, 280)
        self.set_resizable(False)
        if parent is not None:
            self.set_transient_for(parent)
        # Cerrar con la X vuelve a mostrar el reproductor grande (igual que
        # Control+J), en vez de dejar la ventana simplemente oculta sin más.
        self.connect("close-request", self._on_close_request)

        key = Gtk.EventControllerKey()
        key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(16); outer.set_margin_bottom(14)
        outer.set_margin_start(16); outer.set_margin_end(16)
        self.set_child(outer)

        self.cover_image = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        self.cover_image.set_pixel_size(150)
        self.cover_image.set_size_request(150, 150)
        self.cover_image.set_halign(Gtk.Align.CENTER)
        self.cover_image.add_css_class("card")
        outer.append(self.cover_image)

        self.title_label = MarqueeLabel("Ninguna canción cargada", speed=22)
        self.title_label.set_halign(Gtk.Align.CENTER)
        outer.append(self.title_label)

        self.artist_label = Gtk.Label(label="Selecciona una canción", xalign=0.5)
        self.artist_label.add_css_class("dim-label")
        self.artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist_label.set_justify(Gtk.Justification.CENTER)
        self.artist_label.set_wrap(True)
        outer.append(self.artist_label)

        # Barra de progreso de la canción (sin animación de barras del
        # visualizador, tal como se pidió para esta ventana pequeña).
        progress = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.position_label = Gtk.Label(label="0:00"); self.position_label.add_css_class("caption")
        progress.append(self.position_label)
        self.seek_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.seek_scale.set_range(0, 1); self.seek_scale.set_draw_value(False); self.seek_scale.set_hexpand(True)
        self.seek_scale.connect("change-value", self._on_seek_change)
        progress.append(self.seek_scale)
        self.duration_label = Gtk.Label(label="0:00"); self.duration_label.add_css_class("caption")
        progress.append(self.duration_label)
        outer.append(progress)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16, halign=Gtk.Align.CENTER)
        self.prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self.prev_button.set_tooltip_text("Canción anterior")
        self.prev_button.connect("clicked", lambda *_: self.on_previous and self.on_previous())
        buttons.append(self.prev_button)
        self.play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self.play_button.add_css_class("circular"); self.play_button.add_css_class("suggested-action")
        self.play_button.set_tooltip_text("Reproducir / Pausar")
        self.play_button.connect("clicked", lambda *_: self.engine.toggle())
        buttons.append(self.play_button)
        self.next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self.next_button.set_tooltip_text("Siguiente canción")
        self.next_button.connect("clicked", lambda *_: self.on_next and self.on_next())
        buttons.append(self.next_button)
        outer.append(buttons)

        engine.connect("position-updated", self._on_position_updated)
        engine.connect("duration-changed", self._on_duration_changed)
        engine.connect("state-changed", self._on_state_changed)

    def set_song(self, row):
        if not row:
            return
        keys = row.keys() if hasattr(row, "keys") else []
        path = row["path"] if "path" in keys or isinstance(row, dict) else None
        title = row["title"] or (Path(path).stem if path else "Sin título")
        artist = row["artist"] or "Artista desconocido"
        album = row["album"] or "Álbum desconocido"
        self.title_label.set_text(title)
        self.artist_label.set_label(f"{artist} · {album}")
        self.cover_image.set_from_icon_name("audio-x-generic-symbolic")
        cover = row["cover_data"] if "cover_data" in keys else None
        if cover:
            try:
                self.cover_image.set_from_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes(cover)))
            except Exception:
                pass

    def toggle(self):
        if self.get_visible():
            self.hide()
        else:
            self.present()

    def _on_close_request(self, *_args):
        # Se intercepta el cierre nativo (la X de la ventana) para que se
        # comporte igual que Control+J: nunca debe quedar la app sin ninguna
        # ventana visible.
        self.hide()
        if self.on_toggle_window:
            self.on_toggle_window(force_show_main=True)
        return True

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        # Se replica aquí el mismo atajo Control+J de la ventana principal
        # (y espacio/flechas para reproducir/pausar/anterior/siguiente),
        # porque mientras el minireproductor está abierto es él quien tiene
        # el foco del teclado y la ventana principal no recibe eventos.
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval in (Gdk.KEY_j, Gdk.KEY_J):
            if self.on_toggle_window:
                self.on_toggle_window()
            return True
        # Si el foco está en la barra de progreso (un Gtk.Range), espacio y
        # flechas deben mover el slider, no cambiar de canción.
        try:
            focus = self.get_focus()
        except Exception:
            focus = None
        if isinstance(focus, Gtk.Range):
            return False
        if keyval == Gdk.KEY_space:
            self.engine.toggle();return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Left):
            self.on_previous and self.on_previous();return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_KP_Right):
            self.on_next and self.on_next();return True
        return False

    def set_navigation_enabled(self, enabled):
        self.prev_button.set_sensitive(enabled)
        self.next_button.set_sensitive(enabled)

    def _on_seek_change(self, _scale, _scroll, value):
        if self._duration > 0:
            self._seeking = True
            self.position_label.set_label(format_time(value))
            self.engine.seek(value)
            GLib.idle_add(self._clear_seeking)
        return False

    def _clear_seeking(self):
        self._seeking = False
        return False

    def _on_position_updated(self, _engine, pos):
        if not self._seeking:
            self.seek_scale.set_value(min(max(pos, 0), max(self._duration, 1)))
            self.position_label.set_label(format_time(pos))

    def _on_duration_changed(self, _engine, duration):
        self._duration = max(0.0, duration)
        self.seek_scale.set_range(0, max(self._duration, 1))
        self.duration_label.set_label(format_time(self._duration))

    def _on_state_changed(self, _engine, state):
        self.play_button.set_icon_name("media-playback-pause-symbolic" if state == "playing" else "media-playback-start-symbolic")

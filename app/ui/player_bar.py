"""Reproductor inferior compacto y resistente a títulos largos."""
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from app.ui.visualizer import SpectrumWidget
from app.ui.marquee import MarqueeLabel


def format_time(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"


class PlayerBar(Gtk.Box):
    def __init__(self, engine, on_previous=None, on_next=None, on_expand=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.engine = engine
        self.on_previous = on_previous
        self.on_next = on_next
        self.on_expand = on_expand
        self.add_css_class("toolbar")
        self.set_margin_top(6); self.set_margin_bottom(6); self.set_margin_start(10); self.set_margin_end(10)
        self._seeking = False
        self._duration = 0.0
        self.track_info = self._build_track_info()
        self.transport = self._build_transport_controls()
        self.volume_controls = self._build_volume_controls()
        self.track_info.set_size_request(210, -1)
        self.track_info.set_hexpand(False)
        self.transport.set_hexpand(True)
        self.transport.set_vexpand(False)
        self.volume_controls.set_size_request(125, -1)
        self.volume_controls.set_hexpand(False)
        self.append(self.track_info); self.append(self.transport); self.append(self.volume_controls)
        engine.connect("position-updated", self._on_position_updated)
        engine.connect("duration-changed", self._on_duration_changed)
        engine.connect("state-changed", self._on_state_changed)
        engine.connect("eos", self._on_eos)
        engine.connect("spectrum-updated", self._on_spectrum_updated)

    def _build_track_info(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_size_request(210, -1)
        self.cover_image = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        self.cover_image.set_pixel_size(46)
        self.cover_image.set_size_request(46, 46)
        box.append(self.cover_image)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        labels.set_hexpand(True); labels.set_vexpand(False); labels.set_valign(Gtk.Align.CENTER)
        self.title_label = MarqueeLabel("Ninguna canción cargada", speed=25)
        self.title_label.set_tooltip_text("Título de la canción")
        labels.append(self.title_label)
        self.artist_label = Gtk.Label(label="Selecciona una canción", xalign=0)
        self.artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist_label.set_max_width_chars(30)
        self.artist_label.set_hexpand(True)
        self.artist_label.add_css_class("dim-label")
        labels.append(self.artist_label)
        box.append(labels)
        return box

    def _build_transport_controls(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_hexpand(True); box.set_valign(Gtk.Align.CENTER)
        self.visualizer = SpectrumWidget()
        self.visualizer.set_margin_start(4); self.visualizer.set_margin_end(4)
        box.append(self.visualizer)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.CENTER)
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
        box.append(buttons)
        progress = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.position_label = Gtk.Label(label="0:00"); self.position_label.add_css_class("caption")
        progress.append(self.position_label)
        self.seek_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.seek_scale.set_range(0, 1); self.seek_scale.set_draw_value(False); self.seek_scale.set_hexpand(True)
        self.seek_scale.set_size_request(180, -1)
        self.seek_scale.connect("change-value", self._on_seek_change)
        # Gtk.Scale emite change-value directamente durante la interacción
        # del usuario. No añadimos un GestureClick encima porque puede
        # interceptar el puntero y dejar el slider sin recibir el arrastre.
        progress.append(self.seek_scale)
        self.duration_label = Gtk.Label(label="0:00"); self.duration_label.add_css_class("caption")
        progress.append(self.duration_label)
        box.append(progress)
        return box

    def _build_volume_controls(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_size_request(125, -1)
        self.mute_button = Gtk.ToggleButton()
        self.mute_button.set_icon_name("audio-volume-high-symbolic")
        self.mute_button.set_tooltip_text("Silenciar")
        self.mute_button.connect("toggled", self._on_mute_toggled)
        box.append(self.mute_button)
        self.volume_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.volume_scale.set_range(0, 100); self.volume_scale.set_value(100); self.volume_scale.set_draw_value(False)
        self.volume_scale.set_size_request(90, -1)
        self.volume_scale.connect("value-changed", lambda s: self.engine.set_volume(s.get_value() / 100))
        box.append(self.volume_scale)
        self.expand_button = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
        self.expand_button.set_tooltip_text("Abrir reproductor grande")
        self.expand_button.connect("clicked", lambda *_: self.on_expand and self.on_expand())
        box.append(self.expand_button)
        return box

    def set_visualizer_enabled(self, enabled):
        self.visualizer.set_enabled(enabled)

    def set_visualizer_intensity(self, intensity):
        self.visualizer.set_intensity(intensity)

    def load_row(self, row):
        self._duration = 0.0
        self.seek_scale.set_range(0, 1); self.seek_scale.set_value(0)
        self.position_label.set_label("0:00"); self.duration_label.set_label("0:00")
        title = row["title"] or Path(row["path"]).stem
        self.title_label.set_text(title)
        self.artist_label.set_label(f"{row['artist'] or 'Artista desconocido'} · {row['album'] or 'Álbum desconocido'}")
        self.cover_image.set_from_icon_name("audio-x-generic-symbolic")
        if row["cover_data"]:
            try:
                self.cover_image.set_from_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes(row["cover_data"])))
            except Exception:
                pass
        self.visualizer.reset()
        self.engine.load(row["path"])

    def load_file(self, path):
        self._duration = 0.0
        self.seek_scale.set_range(0, 1); self.seek_scale.set_value(0)
        self.position_label.set_label("0:00"); self.duration_label.set_label("0:00")
        self.title_label.set_text(Path(path).stem); self.artist_label.set_label("Archivo local")
        self.cover_image.set_from_icon_name("audio-x-generic-symbolic")
        self.visualizer.reset(); self.engine.load(path)

    def set_navigation_enabled(self, enabled):
        self.prev_button.set_sensitive(enabled); self.next_button.set_sensitive(enabled)

    def _on_seek_change(self, _scale, _scroll, value):
        # change-value es un evento de interacción del usuario, no una
        # actualización programática de la posición. Por eso podemos hacer
        # seek aquí sin que el polling de GStreamer pelee con el slider.
        if self._duration > 0:
            self._seeking = True
            self.position_label.set_label(format_time(value))
            self.engine.seek(value)
            GLib.idle_add(self._clear_seeking)
        return False

    def _clear_seeking(self):
        self._seeking = False
        return False

    def _on_mute_toggled(self, button):
        muted = button.get_active(); self.engine.set_muted(muted)
        button.set_icon_name("audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic")

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
        self.visualizer.set_active(state == "playing")

    def _on_eos(self, _engine):
        self.visualizer.set_active(False)
        self.seek_scale.set_value(self._duration)
        self.position_label.set_label(format_time(self._duration))

    def _on_spectrum_updated(self, _engine, values):
        self.visualizer.set_spectrum(values)

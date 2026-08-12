"""Vista grande de reproducción introducida en la Fase 6."""
from io import BytesIO
from pathlib import Path
import cairo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango

try:
    from PIL import Image
except ImportError:
    Image = None

from app.ui.marquee import MarqueeLabel
from app.ui.visualizer import SpectrumWidget


class PlayerView(Gtk.Overlay):
    """Vista de canción completa con fondo dinámico y controles."""

    def __init__(self, on_back, on_previous, on_next, on_toggle, on_fullscreen):
        super().__init__()
        self.on_back = on_back
        self.on_previous = on_previous
        self.on_next = on_next
        self.on_toggle = on_toggle
        self.on_fullscreen = on_fullscreen
        self._duration = 0.0
        self._seeking = False
        self._cover_data = None
        self._lyrics = ""
        self._song_title = ""

        self.background = Gtk.DrawingArea()
        self.background.set_draw_func(self._draw_background)
        self.set_child(self.background)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        panel.set_margin_top(8); panel.set_margin_bottom(8)
        panel.set_margin_start(18); panel.set_margin_end(18)
        panel.set_halign(Gtk.Align.CENTER); panel.set_valign(Gtk.Align.CENTER)
        panel.set_size_request(480, -1)
        panel.set_vexpand(False)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True); scroller.set_vexpand(True)
        scroller.set_child(panel)
        self.add_overlay(scroller)

        self.lyrics_overlay = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.lyrics_overlay.set_halign(Gtk.Align.CENTER); self.lyrics_overlay.set_valign(Gtk.Align.CENTER)
        self.lyrics_overlay.set_size_request(620, -1)
        self.lyrics_overlay.set_margin_top(28); self.lyrics_overlay.set_margin_bottom(28); self.lyrics_overlay.set_margin_start(28); self.lyrics_overlay.set_margin_end(28)
        self.lyrics_overlay.add_css_class("card")
        self.lyrics_overlay.set_visible(False)
        self.add_overlay(self.lyrics_overlay)
        lyrics_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lyrics_overlay_title = Gtk.Label(label="Letra", xalign=0); self.lyrics_overlay_title.add_css_class("title-3"); self.lyrics_overlay_title.set_hexpand(True); lyrics_top.append(self.lyrics_overlay_title)
        close_lyrics = Gtk.Button(label="Volver a reproducción"); close_lyrics.connect("clicked", lambda *_: self._hide_lyrics()); lyrics_top.append(close_lyrics)
        self.lyrics_overlay.append(lyrics_top)
        lyrics_scroll = Gtk.ScrolledWindow(); lyrics_scroll.set_vexpand(True); lyrics_scroll.set_min_content_height(420)
        self.lyrics_text = Gtk.Label(label="", xalign=0, yalign=0); self.lyrics_text.set_wrap(True); self.lyrics_text.set_selectable(True); self.lyrics_text.set_hexpand(True)
        self.lyrics_text.set_margin_top(12); self.lyrics_text.set_margin_bottom(12); self.lyrics_text.set_margin_start(16); self.lyrics_text.set_margin_end(16)
        lyrics_scroll.set_child(self.lyrics_text); self.lyrics_overlay.append(lyrics_scroll)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        back = Gtk.Button.new_from_icon_name("view-restore-symbolic")
        back.add_css_class("circular")
        back.set_tooltip_text("Minimizar reproductor")
        back.connect("clicked", lambda *_: self.on_back())
        top.append(back)
        label = Gtk.Label(label="Reproduciendo", xalign=0)
        label.add_css_class("title-3")
        label.set_hexpand(True)
        top.append(label)
        self.fullscreen_button = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
        self.fullscreen_button.set_tooltip_text("Pantalla completa")
        self.fullscreen_button.connect("clicked", lambda *_: self.on_fullscreen())
        top.append(self.fullscreen_button)
        panel.append(top)

        self.cover = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        self.cover.set_pixel_size(250)
        self.cover.set_size_request(250, 250)
        self.cover.set_halign(Gtk.Align.CENTER)
        self.cover.add_css_class("card")
        panel.append(self.cover)

        self.title = MarqueeLabel("Ninguna canción", speed=35)
        self.title.set_content_height(32)
        self.title.set_content_width(430)
        panel.append(self.title)
        self.artist = Gtk.Label(label="", xalign=0.5)
        self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist.set_max_width_chars(60)
        self.artist.add_css_class("dim-label")
        panel.append(self.artist)

        self.lyrics_button = Gtk.Button(label="Letra")
        self.lyrics_button.set_halign(Gtk.Align.CENTER)
        self.lyrics_button.set_visible(False)
        self.lyrics_button.connect("clicked", self._show_lyrics)
        panel.append(self.lyrics_button)

        self.visualizer = SpectrumWidget()
        self.visualizer.set_content_height(42)
        panel.append(self.visualizer)

        progress = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.position = Gtk.Label(label="0:00")
        self.scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.scale.set_range(0, 1); self.scale.set_draw_value(False); self.scale.set_hexpand(True)
        self.scale.connect("change-value", self._on_seek)
        self.duration = Gtk.Label(label="0:00")
        progress.append(self.position); progress.append(self.scale); progress.append(self.duration)
        panel.append(progress)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18, halign=Gtk.Align.CENTER)
        prev = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        prev.connect("clicked", lambda *_: self.on_previous())
        self.play = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self.play.add_css_class("circular"); self.play.add_css_class("suggested-action")
        self.play.connect("clicked", lambda *_: self.on_toggle())
        nxt = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        nxt.connect("clicked", lambda *_: self.on_next())
        controls.append(prev); controls.append(self.play); controls.append(nxt)
        panel.append(controls)

    def set_fullscreen_button_state(self, active):
        if active:
            self.fullscreen_button.set_icon_name("view-restore-symbolic")
            self.fullscreen_button.set_tooltip_text("Salir de pantalla completa")
        else:
            self.fullscreen_button.set_icon_name("view-fullscreen-symbolic")
            self.fullscreen_button.set_tooltip_text("Pantalla completa")

    def set_visualizer_enabled(self, enabled):
        self.visualizer.set_enabled(enabled)

    def set_visualizer_intensity(self, intensity):
        self.visualizer.set_intensity(intensity)

    def set_song(self, row):
        self._cover_data = row["cover_data"] if "cover_data" in row.keys() else None
        self._lyrics = str(row["lyrics"] or "") if "lyrics" in row.keys() else ""
        title = row["title"] or Path(row["path"]).stem
        self._song_title = title
        self.title.set_text(title)
        self.artist.set_label(f"{row['artist'] or 'Artista desconocido'} · {row['album'] or 'Álbum desconocido'}")
        self.lyrics_button.set_visible(bool(self._lyrics.strip()))
        self._hide_lyrics()
        self.cover.set_from_icon_name("audio-x-generic-symbolic")
        if self._cover_data:
            try:
                self.cover.set_from_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes(self._cover_data)))
            except Exception:
                pass
        self._update_background_color()
        self.scale.set_range(0, 1); self.scale.set_value(0)
        self.position.set_label("0:00"); self.duration.set_label("0:00")
        self._duration = 0.0
        self.visualizer.reset()

    def _show_lyrics(self, _button):
        if not self._lyrics.strip():
            return
        self.lyrics_overlay_title.set_label(f"Letra · {self._song_title}")
        self.lyrics_text.set_label(self._lyrics)
        self.lyrics_overlay.set_visible(True)

    def _hide_lyrics(self):
        self.lyrics_overlay.set_visible(False)

    def update_position(self, position):
        if not self._seeking:
            self.scale.set_value(min(max(position, 0), max(self._duration, 1)))
            self.position.set_label(self._format_time(position))

    def update_duration(self, duration):
        self._duration = max(0.0, duration)
        self.scale.set_range(0, max(self._duration, 1))
        self.duration.set_label(self._format_time(self._duration))

    def set_state(self, state):
        self.play.set_icon_name("media-playback-pause-symbolic" if state == "playing" else "media-playback-start-symbolic")
        self.visualizer.set_active(state == "playing")

    def set_spectrum(self, values):
        self.visualizer.set_spectrum(values)

    def _on_seek(self, _scale, _scroll, value):
        if self._duration > 0:
            self._seeking = True
            self.position.set_label(self._format_time(value))
            GLib.idle_add(self._release_seek, value)
        return False

    def _release_seek(self, value):
        self.on_seek(value) if hasattr(self, "on_seek") else None
        self._seeking = False
        return False

    def set_seek_callback(self, callback):
        self.on_seek = callback

    @staticmethod
    def _format_time(seconds):
        seconds = max(0, int(seconds or 0))
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _update_background_color(self):
        self.background.queue_draw()

    def _draw_background(self, _area, cr, width, height):
        r, g, b = self._dominant_color()
        grad = cairo.LinearGradient(0, 0, width, height)
        # Fondo un poco más visible sin llegar a competir con la carátula.
        grad.add_color_stop_rgba(0, min(1.0, r * 0.78), min(1.0, g * 0.78), min(1.0, b * 0.78), 1.0)
        grad.add_color_stop_rgba(0.55, r * 0.40, g * 0.40, b * 0.40, 1.0)
        grad.add_color_stop_rgba(1, 0.035, 0.035, 0.055, 1.0)
        cr.set_source(grad); cr.rectangle(0, 0, width, height); cr.fill()

    def _dominant_color(self):
        if not self._cover_data or Image is None:
            return (0.10, 0.12, 0.18)
        try:
            image = Image.open(BytesIO(self._cover_data)).convert("RGB")
            image.thumbnail((32, 32))
            pixels = list(image.getdata())
            if not pixels:
                return (0.10, 0.12, 0.18)
            rr = sum(p[0] for p in pixels) / len(pixels) / 255.0
            gg = sum(p[1] for p in pixels) / len(pixels) / 255.0
            bb = sum(p[2] for p in pixels) / len(pixels) / 255.0
            return rr, gg, bb
        except Exception:
            return (0.10, 0.12, 0.18)

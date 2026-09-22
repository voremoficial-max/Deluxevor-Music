import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from app.utils.debounce import Debouncer
from app.ui.pages.song_list import SongList


class SongsPage(Gtk.Box):
    def __init__(self, database, on_play, on_changed=None, on_playlist_add=None, on_play_all=None, on_shuffle=None, on_repeat=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._search_debounce = Debouncer(180)
        self.database = database; self.on_play = on_play; self.on_changed = on_changed
        self.on_play_all = on_play_all; self.on_shuffle = on_shuffle; self.on_repeat = on_repeat
        self.set_margin_top(24); self.set_margin_bottom(24); self.set_margin_start(28); self.set_margin_end(28)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Canciones", xalign=0); title.add_css_class("title-2"); header.append(title)
        self.search = Gtk.SearchEntry(placeholder_text="Buscar canción, artista, álbum o género…")
        self.search.set_hexpand(True); self.search.connect("search-changed", lambda *_: self._search_debounce.call(self.refresh)); header.append(self.search)

        self.play_all_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self.play_all_button.set_tooltip_text("Reproducir todo")
        self.play_all_button.connect("clicked", lambda *_: self.on_play_all and self.on_play_all(self.list.rows))
        header.append(self.play_all_button)
        self.shuffle_button = Gtk.ToggleButton()
        self.shuffle_button.set_icon_name("media-playlist-shuffle-symbolic")
        self.shuffle_button.set_tooltip_text("Aleatorio: desactivado")
        self.shuffle_button.add_css_class("vorem-mode-button")
        self.shuffle_button.add_css_class("vorem-shuffle")
        self.shuffle_button.connect("toggled", self._shuffle_toggled)
        header.append(self.shuffle_button)
        self.repeat_button = Gtk.Button.new_from_icon_name("media-playlist-repeat-symbolic")
        self.repeat_button.set_tooltip_text("Repetir: desactivado")
        self.repeat_button.add_css_class("vorem-mode-button")
        self.repeat_button.add_css_class("vorem-repeat-off")
        self.repeat_button.connect("clicked", self._repeat_clicked)
        header.append(self.repeat_button)
        self.append(header)
        self.status = Gtk.Label(xalign=0); self.status.add_css_class("dim-label"); self.append(self.status)
        self.list = SongList(database, on_play, self._favorite_changed, on_playlist_add, self.refresh); self.append(self.list); self.refresh()

    def set_shuffle_state(self, active):
        active = bool(active)
        self.shuffle_button.set_active(active)
        self.shuffle_button.set_tooltip_text(
            "Aleatorio: activado" if active else "Aleatorio: desactivado"
        )
        self.shuffle_button.remove_css_class("vorem-mode-off")
        self.shuffle_button.remove_css_class("vorem-mode-active")
        self.shuffle_button.add_css_class("vorem-mode-active" if active else "vorem-mode-off")

    def _shuffle_toggled(self, button):
        active = button.get_active()
        button.set_tooltip_text("Aleatorio: activado" if active else "Aleatorio: desactivado")
        if self.on_shuffle:
            self.on_shuffle(active)

    def set_repeat_mode(self, mode):
        names = {
            "off": "Repetir: desactivado",
            "all": "Repetir: lista completa",
            "one": "Repetir: canción actual",
        }
        self.repeat_button.set_tooltip_text(names.get(mode, names["off"]))
        for css_class in ("vorem-repeat-off", "vorem-repeat-all", "vorem-repeat-one"):
            self.repeat_button.remove_css_class(css_class)
        self.repeat_button.add_css_class({
            "off": "vorem-repeat-off",
            "all": "vorem-repeat-all",
            "one": "vorem-repeat-one",
        }.get(mode, "vorem-repeat-off"))
        self.repeat_button.set_icon_name("media-playlist-repeat-symbolic")

    def _repeat_clicked(self, _button):
        if self.on_repeat:
            mode = self.on_repeat()
            self.set_repeat_mode(mode)

    def refresh(self):
        query = self.search.get_text().strip() if hasattr(self, "search") else ""
        rows = self.database.list_songs(query); self.list.set_rows(rows); self.status.set_label(f"{len(rows)} canción(es)")

    def _favorite_changed(self):
        self.refresh(); self.on_changed and self.on_changed()

    def get_queue(self):
        return self.list.rows

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from app.ui.pages.song_list import SongList

class FavoritesPage(Gtk.Box):
    def __init__(self,database,on_play):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=10); self.database=database; self.on_play=on_play
        self.set_margin_top(24);self.set_margin_bottom(24);self.set_margin_start(28);self.set_margin_end(28)
        self.title=Gtk.Label(label="Favoritos",xalign=0);self.title.add_css_class("title-2");self.append(self.title)
        self.status=Gtk.Label(xalign=0);self.status.add_css_class("dim-label");self.append(self.status)
        self.list=SongList(database,on_play,self._changed,on_changed=self.refresh);self.append(self.list);self.refresh()
    def refresh(self):
        rows=self.database.list_favorites();self.list.set_rows(rows);self.status.set_label(f"{len(rows)} favorita(s)")

    def _changed(self):
        self.refresh()

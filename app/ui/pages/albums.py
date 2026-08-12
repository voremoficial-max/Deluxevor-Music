import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GLib
from app.ui.pages.song_list import SongList
from app.utils.debounce import Debouncer


class AlbumsPage(Gtk.Box):
    def __init__(self, database, on_play, on_changed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._search_debounce = Debouncer(180)
        self.database = database; self.on_play = on_play; self.on_changed = on_changed; self.current_album = None
        self.set_margin_top(24); self.set_margin_bottom(24); self.set_margin_start(28); self.set_margin_end(28)
        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.title = Gtk.Label(label="Álbumes", xalign=0); self.title.add_css_class("title-2"); h.append(self.title)
        self.search = Gtk.SearchEntry(placeholder_text="Buscar álbum o artista…"); self.search.set_hexpand(True); self.search.connect("search-changed", lambda *_: self._search_debounce.call(self.refresh)); h.append(self.search)
        self.create_btn = Gtk.Button(label="Crear álbum"); self.create_btn.connect("clicked", self._create); h.append(self.create_btn)
        self.edit_btn = Gtk.Button(label="Editar álbum"); self.edit_btn.set_visible(False); self.edit_btn.connect("clicked", self._edit_selected); h.append(self.edit_btn)
        self.delete_all_btn = Gtk.Button(label="Borrar todo")
        self.delete_all_btn.add_css_class("destructive-action")
        self.delete_all_btn.connect("clicked", self._delete_all)
        h.append(self.delete_all_btn)
        self.back = Gtk.Button(label="Volver"); self.back.set_visible(False); self.back.connect("clicked", lambda *_: self.show_albums()); h.append(self.back)
        self.append(h)
        self.stack = Gtk.Stack(); self.stack.set_vexpand(True); self.append(self.stack)
        self.cards = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroll = Gtk.ScrolledWindow(); scroll.set_child(self.cards); scroll.set_vexpand(True); self.stack.add_named(scroll, "albums")
        self.song_list = SongList(database, on_play, self._changed, on_changed=self._changed, allow_selection=True)
        self.song_list.on_selection_changed = self._selection_changed; self.stack.add_named(self.song_list, "songs")
        self.refresh()

    def refresh(self):
        if self.current_album: return
        while (c := self.cards.get_first_child()) is not None: self.cards.remove(c)
        rows = self.database.list_albums(self.search.get_text().strip())
        for row in rows:
            b = Gtk.Button(label=f"{row['album']}    ·    {row['artist']}    ·    {row['song_count']} canciones")
            b.set_halign(Gtk.Align.FILL); b.connect("clicked", self._open_album, row["album"], row["artist"]); self.cards.append(b)
        self.stack.set_visible_child_name("albums"); self.back.set_visible(False); self.title.set_label("Álbumes")

    def _open_album(self, _button, album, artist):
        self.current_album = (album, artist); self.stack.set_visible_child_name("songs"); self.back.set_visible(True); self.title.set_label(album); self._selection_changed([])
        GLib.idle_add(self._load_current)

    def _load_current(self):
        if self.current_album:
            self.song_list.set_rows(self.database.list_album_songs(*self.current_album))
        return False

    def show_albums(self): self.current_album = None; self.song_list.clear_selection(); self.refresh()

    def _selection_changed(self, ids):
        self.edit_btn.set_visible(bool(ids) and bool(self.current_album))

    def _edit_selected(self, _button):
        ids = [r["id"] for r in self.song_list.get_selected_rows()]
        if not ids: return
        d = Adw.MessageDialog(transient_for=self.get_root(), heading="Editar álbum", body=f"Se aplicará a {len(ids)} canción(es) seleccionada(s).")
        e = Gtk.Entry(); e.set_text(self.current_album[0]); e.set_placeholder_text("Nombre del álbum"); d.set_extra_child(e)
        d.add_response("cancel", "Cancelar"); d.add_response("save", "Guardar"); d.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        d.connect("response", lambda _d, r: self._finish_edit(ids, e, r)); d.present()

    def _finish_edit(self, ids, entry, response):
        if response == "save" and entry.get_text().strip(): self.database.update_songs_field(ids, "album", entry.get_text()); self._changed()

    def _create(self, _button):
        self._open_create_dialog("album", "álbum")

    def _open_create_dialog(self, field, label):
        dialog = Adw.MessageDialog(transient_for=self.get_root(), heading=f"Crear {label}", body=f"Escribe el nuevo {label} y selecciona las canciones a las que se aplicará.")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); entry = Gtk.Entry(placeholder_text=f"Nombre del {label}"); box.append(entry)
        info = Gtk.Label(label="La selección múltiple solo está disponible aquí, no en la página general de Canciones.", xalign=0); info.add_css_class("dim-label"); info.set_wrap(True); box.append(info)
        listbox = Gtk.ListBox(); listbox.set_selection_mode(Gtk.SelectionMode.NONE); scroll = Gtk.ScrolledWindow(); scroll.set_min_content_height(320); scroll.set_child(listbox); box.append(scroll)
        checks=[]
        for row in self.database.list_song_choices():
            check=Gtk.CheckButton(label=f"{row['title']} — {row['artist']}"); check.set_margin_top(3); check.set_margin_bottom(3); listbox.append(check); checks.append((check,int(row['id'])))
        dialog.set_extra_child(box); dialog.add_response("cancel","Cancelar"); dialog.add_response("create","Crear"); dialog.set_response_appearance("create",Adw.ResponseAppearance.SUGGESTED)
        def response(_d,r):
            if r=="create":
                ids=[sid for c,sid in checks if c.get_active()]; name=entry.get_text().strip()
                if name and ids: self.database.update_songs_field(ids,field,name); self._changed()
        dialog.connect("response",response); dialog.present()

    def _delete_all(self, _button):
        d=Adw.MessageDialog(transient_for=self.get_root(), heading="¿Borrar todos los álbumes?", body="Esto quitará el nombre de álbum de todas las canciones. Los archivos de música NO se eliminarán y esta acción no se puede deshacer automáticamente.")
        d.add_response("cancel","Cancelar"); d.add_response("clear","Borrar todo"); d.set_response_appearance("clear",Adw.ResponseAppearance.DESTRUCTIVE)
        d.connect("response",lambda _d,r: self._finish_delete_all(r)); d.present()
    def _finish_delete_all(self,r):
        if r=="clear": self.database.clear_all_field("album"); self.show_albums(); self._changed()

    def _changed(self):
        if self.current_album:
            rows=self.database.list_album_songs(*self.current_album); self.song_list.set_rows(rows)
            if not rows:self.show_albums()
        else:self.refresh()
        if self.on_changed:self.on_changed()

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GLib
from app.ui.pages.song_list import SongList
from app.utils.debounce import Debouncer

class ArtistsPage(Gtk.Box):
    def __init__(self, database, on_play, on_changed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._search_debounce = Debouncer(180)
        self.database=database; self.on_play=on_play; self.on_changed=on_changed; self.artist=None
        self.set_margin_top(24); self.set_margin_bottom(24); self.set_margin_start(28); self.set_margin_end(28)
        h=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=10); self.title=Gtk.Label(label="Artistas",xalign=0); self.title.add_css_class("title-2"); h.append(self.title)
        self.search=Gtk.SearchEntry(placeholder_text="Buscar artista…"); self.search.set_hexpand(True); self.search.connect("search-changed", lambda *_: self._search_debounce.call(self.refresh)); h.append(self.search)
        self.create_btn=Gtk.Button(label="Crear artista"); self.create_btn.connect("clicked",self._create); h.append(self.create_btn)
        self.edit_btn=Gtk.Button(label="Editar artista"); self.edit_btn.set_visible(False); self.edit_btn.connect("clicked",self._edit_selected); h.append(self.edit_btn)
        self.delete_all_btn=Gtk.Button(label="Borrar todo")
        # Borrar artista: acción de limpieza individual/conceptual del grupo.
        self.delete_all_btn.add_css_class("destructive-action"); self.delete_all_btn.connect("clicked",self._delete_all); h.append(self.delete_all_btn)
        self.back=Gtk.Button(label="Volver"); self.back.set_visible(False); self.back.connect("clicked",lambda *_:self.show_artists()); h.append(self.back); self.append(h)
        self.stack=Gtk.Stack(); self.stack.set_vexpand(True); self.append(self.stack)
        self.cards=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6); s=Gtk.ScrolledWindow(); s.set_child(self.cards); s.set_vexpand(True); self.stack.add_named(s,"artists")
        self.song_list=SongList(database,on_play,self._changed,on_changed=self._changed,allow_selection=True); self.song_list.on_selection_changed=self._selection_changed; self.stack.add_named(self.song_list,"songs"); self.refresh()
    def refresh(self):
        if self.artist:return
        while (c:=self.cards.get_first_child()) is not None:self.cards.remove(c)
        for row in self.database.list_artists(self.search.get_text().strip()):
            b=Gtk.Button(label=f"{row['artist']}    ·    {row['song_count']} canciones    ·    {row['album_count']} álbumes"); b.set_halign(Gtk.Align.FILL); b.connect("clicked",self._open,row["artist"]); self.cards.append(b)
        self.stack.set_visible_child_name("artists"); self.back.set_visible(False); self.title.set_label("Artistas")
    def _open(self,_b,artist):
        self.artist=artist; self.stack.set_visible_child_name("songs"); self.back.set_visible(True); self.title.set_label(artist); self._selection_changed([]); GLib.idle_add(self._load_current)
    def _load_current(self):
        if self.artist:self.song_list.set_rows(self.database.list_artist_songs(self.artist))
        return False
    def show_artists(self):self.artist=None;self.song_list.clear_selection();self.refresh()
    def _selection_changed(self,ids):self.edit_btn.set_visible(bool(ids) and bool(self.artist))
    def _edit_selected(self,_button):
        ids=[r["id"] for r in self.song_list.get_selected_rows()]
        if not ids:return
        d=Adw.MessageDialog(transient_for=self.get_root(),heading="Editar artista",body=f"Se aplicará a {len(ids)} canción(es) seleccionada(s).")
        e=Gtk.Entry();e.set_text(self.artist);e.set_placeholder_text("Nombre del artista");d.set_extra_child(e);d.add_response("cancel","Cancelar");d.add_response("save","Guardar");d.set_response_appearance("save",Adw.ResponseAppearance.SUGGESTED);d.connect("response",lambda _d,r:self._finish_edit(ids,e,r));d.present()
    def _finish_edit(self,ids,e,r):
        if r=="save" and e.get_text().strip():self.database.update_songs_field(ids,"artist",e.get_text());self._changed()
    def _create(self,_button):self._open_create_dialog("artist","artista")
    def _open_create_dialog(self,field,label):
        d=Adw.MessageDialog(transient_for=self.get_root(),heading=f"Crear {label}",body=f"Escribe el nuevo {label} y selecciona las canciones a las que se aplicará.")
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);e=Gtk.Entry(placeholder_text=f"Nombre del {label}");box.append(e);info=Gtk.Label(label="La selección múltiple solo está disponible en esta sección.",xalign=0);info.add_css_class("dim-label");box.append(info)
        lb=Gtk.ListBox();lb.set_selection_mode(Gtk.SelectionMode.NONE);sc=Gtk.ScrolledWindow();sc.set_min_content_height(320);sc.set_child(lb);box.append(sc);checks=[]
        for row in self.database.list_song_choices():
            c=Gtk.CheckButton(label=f"{row['title']} — {row['artist']}");lb.append(c);checks.append((c,int(row['id'])))
        d.set_extra_child(box);d.add_response("cancel","Cancelar");d.add_response("create","Crear");d.set_response_appearance("create",Adw.ResponseAppearance.SUGGESTED)
        def resp(_d,r):
            if r=="create":
                ids=[sid for c,sid in checks if c.get_active()];name=e.get_text().strip()
                if name and ids:self.database.update_songs_field(ids,field,name);self._changed()
        d.connect("response",resp);d.present()
    def _delete_all(self,_button):
        d=Adw.MessageDialog(transient_for=self.get_root(),heading="¿Borrar todos los artistas?",body="Esto quitará el artista de todas las canciones. Los archivos NO se eliminarán.");d.add_response("cancel","Cancelar");d.add_response("clear","Borrar todo");d.set_response_appearance("clear",Adw.ResponseAppearance.DESTRUCTIVE);d.connect("response",lambda _d,r:self._finish_delete_all(r));d.present()
    def _finish_delete_all(self,r):
        if r=="clear":self.database.clear_all_field("artist");self.show_artists();self._changed()
    def _changed(self):
        if self.artist:
            rows=self.database.list_artist_songs(self.artist);self.song_list.set_rows(rows)
            if not rows:self.show_artists()
        else:self.refresh()
        if self.on_changed:self.on_changed()

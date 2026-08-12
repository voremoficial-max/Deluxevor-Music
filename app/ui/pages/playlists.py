import gi

gi.require_version("Adw","1");gi.require_version("Gtk","4.0")
from gi.repository import Adw,Gtk
from app.ui.pages.song_list import SongList

class PlaylistsPage(Gtk.Box):
    def __init__(self,database,on_play,on_changed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=10);self.database=database;self.on_play=on_play;self.on_changed=on_changed;self.current=None
        self.set_margin_top(24);self.set_margin_bottom(24);self.set_margin_start(28);self.set_margin_end(28)
        h=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=10);self.title=Gtk.Label(label="Playlists",xalign=0);self.title.add_css_class("title-2");h.append(self.title)
        add=Gtk.Button(label="Nueva playlist");add.add_css_class("suggested-action");add.connect("clicked",self._new);h.append(add)
        self.back=Gtk.Button(label="Volver");self.back.set_visible(False);self.back.connect("clicked",lambda *_:self.show_all());h.append(self.back);self.append(h)
        self.stack=Gtk.Stack();self.stack.set_vexpand(True);self.append(self.stack)
        self.cards=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);s=Gtk.ScrolledWindow();s.set_child(self.cards);s.set_vexpand(True);self.stack.add_named(s,"playlists")
        self.songs=SongList(database,on_play,self._songs_changed,on_changed=self._songs_changed);self.stack.add_named(self.songs,"songs");self.refresh()
    def refresh(self):
        if self.current:return
        while(c:=self.cards.get_first_child()) is not None:self.cards.remove(c)
        for row in self.database.list_playlists():
            box=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=6)
            openb=Gtk.Button(label=f"{row['name']}  ·  {row['song_count']} canciones");openb.set_hexpand(True);openb.connect("clicked",self._open,row["id"],row["name"]);box.append(openb)
            ren=Gtk.Button(label="Renombrar");ren.connect("clicked",self._rename,row["id"],row["name"]);box.append(ren)
            dele=Gtk.Button.new_from_icon_name("user-trash-symbolic");dele.connect("clicked",self._delete,row["id"]);box.append(dele);self.cards.append(box)
        self.stack.set_visible_child_name("playlists");self.back.set_visible(False);self.title.set_label("Playlists")
    def _new(self,_b):
        d=Adw.MessageDialog(transient_for=self.get_root(),heading="Nueva playlist",body="Escribe el nombre de la playlist.");e=Gtk.Entry();e.set_placeholder_text("Mi playlist");d.set_extra_child(e);d.add_response("cancel","Cancelar");d.add_response("create","Crear");d.set_response_appearance("create",Adw.ResponseAppearance.SUGGESTED);d.connect("response",lambda _d,r:self._create_response(e,r));d.present()
    def _create_response(self,e,r):
        if r=="create":
            try:self.database.create_playlist(e.get_text());self.refresh()
            except Exception:pass
    def _rename(self,_b,pid,old):
        d=Adw.MessageDialog(transient_for=self.get_root(),heading="Renombrar playlist",body="Nuevo nombre.");e=Gtk.Entry(text=old);d.set_extra_child(e);d.add_response("cancel","Cancelar");d.add_response("save","Guardar");d.connect("response",lambda _d,r:self._rename_response(pid,e,r));d.present()
    def _rename_response(self,pid,e,r):
        if r=="save":
            try:self.database.rename_playlist(pid,e.get_text());self.refresh()
            except Exception:pass
    def _delete(self,_b,pid):self.database.delete_playlist(pid);self.refresh()
    def _open(self,_b,pid,name):
        self.current=pid;rows=self.database.list_playlist_songs(pid);self.songs.set_rows(rows);self.stack.set_visible_child_name("songs");self.back.set_visible(True);self.title.set_label(name)
    def show_all(self):self.current=None;self.refresh()

    def _songs_changed(self):
        if self.current:
            self.songs.set_rows(self.database.list_playlist_songs(self.current))
        if self.on_changed:
            self.on_changed()

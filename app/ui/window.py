from app.ui.pages.settings import SettingsPage
"""Ventana principal y coordinación de navegación/reproducción de Fase 4."""
import gi

gi.require_version("Adw","1");gi.require_version("Gtk","4.0")
from gi.repository import Adw,Gio,Gdk,Gtk,GLib
from app.database.db import MusicDatabase
from app.library.scanner import LibraryScanner
from app.player.engine import PlayerEngine
from app.ui.player_bar import PlayerBar
from app.ui.player_view import PlayerView
from app.ui.pages.library import LibraryPage
from app.ui.pages.songs import SongsPage
from app.ui.pages.albums import AlbumsPage
from app.ui.pages.artists import ArtistsPage
from app.ui.pages.genres import GenresPage
from app.ui.pages.favorites import FavoritesPage
from app.ui.pages.playlists import PlaylistsPage
from app.ui.pages.download import DownloadPage
from app.utils.logger import get_logger
import random
from pathlib import Path

logger=get_logger(__name__)
SIDEBAR_SECTIONS=[("songs","Canciones","audio-x-generic-symbolic"),("library","Biblioteca","folder-music-symbolic"),("albums","Álbumes","media-optical-symbolic"),("artists","Artistas","avatar-default-symbolic"),("genres","Géneros","view-grid-symbolic"),("favorites","Favoritos","starred-symbolic"),("playlists","Playlists","view-list-symbolic"),("download","Descargar música","folder-download-symbolic"),("settings","Ajustes","preferences-system-symbolic")]

class VoremWindow(Adw.ApplicationWindow):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.set_title("Deluxevor Music — Fase 7");self.set_default_size(1200,780)
        self.database=MusicDatabase();self.scanner=LibraryScanner(self.database);self.engine=PlayerEngine();self.engine.connect("error",self._on_engine_error);self.engine.connect("eos",self._on_eos)
        self.queue=[];self.queue_index=-1;self.current_song_id=None;self.shuffle_history=[]
        self.shuffle_enabled=self.database.get_setting("shuffle","0")=="1"
        self.repeat_mode=self.database.get_setting("repeat_mode","off")
        self.autoplay_enabled=self.database.get_setting("autoplay","1")=="1"
        self.current_page=self.database.get_setting("last_page","songs") if self.database.get_setting("startup_page","songs")=="last" else self.database.get_setting("startup_page","songs")
        self.visualizer_enabled=self.database.get_setting("visualizer_enabled","1")=="1"
        self.animations_enabled=self.database.get_setting("animations","1")=="1"
        self._visualizer_intensity=float(self.database.get_setting("visualizer_intensity","1.48"))
        self._theme=self.database.get_setting("theme","dark")
        tv=Adw.ToolbarView();self.set_content(tv);tv.add_top_bar(self._header());body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);body.add_css_class("vorem-theme-surface");self._theme_surface=body;tv.set_content(body)
        area=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL);area.set_vexpand(True);body.append(area);self.sidebar=self._sidebar();self.sidebar_separator=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL);area.append(self.sidebar);area.append(self.sidebar_separator)
        self.stack=Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,transition_duration=180);self.stack.set_hexpand(True);self.stack.set_vexpand(True)
        self.content_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=180)
        self.content_stack.add_css_class("vorem-pages-surface")
        self.content_stack.set_hexpand(True); self.content_stack.set_vexpand(True)
        self.content_stack.add_named(self.stack, "library-pages")
        area.append(self.content_stack)
        self.library_page=LibraryPage(self.database,self.scanner,self._library_changed)
        self.songs_page=SongsPage(self.database,self._play_song,self._library_changed,self._add_song_to_playlist,self._play_all,self._set_shuffle,self._cycle_repeat)
        self.albums_page=AlbumsPage(self.database,self._play_song,self._library_changed);self.artists_page=ArtistsPage(self.database,self._play_song,self._library_changed);self.genres_page=GenresPage(self.database,self._play_song,self._library_changed);self.favorites_page=FavoritesPage(self.database,self._play_song);self.playlists_page=PlaylistsPage(self.database,self._play_song,self._library_changed);self.download_page=DownloadPage(self.database,self._library_changed)
        for name,page in (("library",self.library_page),("songs",self.songs_page),("albums",self.albums_page),("artists",self.artists_page),("genres",self.genres_page),("favorites",self.favorites_page),("playlists",self.playlists_page),("download",self.download_page)):self.stack.add_named(page,name)
        self.settings_page=SettingsPage(self.database,self);self.stack.add_named(self.settings_page,"settings")
        # Las vistas contextuales también permiten añadir canciones a playlists.
        for page in (self.albums_page,self.artists_page,self.genres_page,self.favorites_page,self.playlists_page):
            if hasattr(page,"song_list"):page.song_list.on_playlist_add=self._add_song_to_playlist
            if hasattr(page,"songs"):page.songs.on_playlist_add=self._add_song_to_playlist
        self.player_view = PlayerView(self._show_library_pages, self._previous_song, self._next_song, self.engine.toggle, self._toggle_fullscreen)
        self.player_view.set_seek_callback(self.engine.seek)
        self.content_stack.add_named(self.player_view, "player-view")
        body.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL));self.player_bar=PlayerBar(self.engine,self._previous_song,self._next_song,self._show_player_view);self.player_bar.set_navigation_enabled(False);body.append(self.player_bar)
        self.engine.connect("position-updated", lambda _e, pos: self.player_view.update_position(pos))
        self.engine.connect("duration-changed", lambda _e, dur: self.player_view.update_duration(dur))
        self.engine.connect("state-changed", lambda _e, state: self.player_view.set_state(state))
        self.engine.connect("spectrum-updated", lambda _e, values: self.player_view.set_spectrum(values))
        key=Gtk.EventControllerKey();key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE);key.connect("key-pressed",self._on_global_key);self.add_controller(key)
        self.player_bar.visualizer.set_enabled(self.visualizer_enabled)
        self.player_view.visualizer.set_enabled(self.visualizer_enabled)
        self.set_visualizer_intensity(self._visualizer_intensity)
        self.engine.set_volume(float(self.database.get_setting("volume","100"))/100)
        self.apply_theme(self._theme)
        self._select_page(self.current_page if self.current_page in {x[0] for x in SIDEBAR_SECTIONS} else "songs")
        self._setup_actions()
        GLib.idle_add(self._maybe_show_welcome)

    def _maybe_show_welcome(self):
        """Muestra un saludo de bienvenida la primera vez que se abre la app."""
        if self.database.get_setting("welcome_shown", "0") == "1":
            return False
        body = (
            "¡Hola! Bienvenido a Deluxevor Music 🎶\n\n"
            "Soy Vorem, el creador de esta aplicación, y espero que tu experiencia "
            "sea muy buena. Recuerda que esto es totalmente gratuito, hecho con cariño "
            "para ti.\n\n"
            "Antes de descargar una canción o su letra, no olvides configurar tu API key "
            "y tus cookies: encontrarás las instrucciones en la sección Ajustes.\n\n"
            "Cuando descargues la letra de una canción, procura que el nombre quede "
            "legible y no demasiado largo, así será más fácil encontrarla después.\n\n"
            "No olvides seguirme en mis redes sociales, y muchas gracias por usar algo "
            "hecho por mí 💜\n\n"
            "Cualquier duda o recomendación, entra al grupo (lo encuentras en Ajustes) "
            "y escríbeme, ¡con gusto te ayudo!"
        )
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="¡Bienvenido a Deluxevor Music!",
            body=body,
        )
        check = Gtk.CheckButton(label="No volver a mostrar este mensaje")
        check.set_margin_top(10)
        check.set_margin_bottom(4)
        dialog.set_extra_child(check)
        dialog.add_response("ok", "Entendido, ¡vamos allá!")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")

        def on_response(_dialog, _response):
            if check.get_active():
                self.database.set_setting("welcome_shown", "1")

        dialog.connect("response", on_response)
        dialog.present()
        return False

    def _select_page(self, key):
        self.current_page = key
        self.database.set_setting("last_page", key)
        # Sincroniza la selección del menú lateral incluso cuando otra página
        # (por ejemplo Ajustes) abre Biblioteca mediante un botón interno.
        # Esto garantiza que volver a pulsar Ajustes siempre genere una nueva
        # navegación y no dependa de que la fila ya estuviera seleccionada.
        if hasattr(self, "sidebar_list"):
            for index, (row_key, _title, _icon) in enumerate(SIDEBAR_SECTIONS):
                if row_key == key:
                    row = self.sidebar_list.get_row_at_index(index)
                    if row is not None and self.sidebar_list.get_selected_row() is not row:
                        self.sidebar_list.select_row(row)
                    break
        self.content_stack.set_visible_child_name("library-pages")
        self.sidebar.set_visible(True)
        self.sidebar_separator.set_visible(True)
        self.player_bar.set_visible(True)
        self.stack.set_visible_child_name(key)

    def set_visualizer_enabled(self, enabled):
        self.visualizer_enabled = bool(enabled)
        self.player_bar.set_visualizer_enabled(self.visualizer_enabled)
        self.player_view.set_visualizer_enabled(self.visualizer_enabled)

    def set_visualizer_intensity(self, intensity):
        self._visualizer_intensity = max(0.8, min(2.0, float(intensity)))
        self.player_bar.set_visualizer_intensity(self._visualizer_intensity)
        self.player_view.set_visualizer_intensity(self._visualizer_intensity)

    def set_animations_enabled(self, enabled):
        self.animations_enabled = bool(enabled)
        duration = 180 if self.animations_enabled else 0
        self.stack.set_transition_duration(duration)
        self.content_stack.set_transition_duration(duration)

    def apply_theme(self, theme):
        manager = Adw.StyleManager.get_default()
        if theme in {"dark", "blue", "green", "violet"}:
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme == "light":
            manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        if hasattr(self, "_theme_surface"):
            for value in ("system", "dark", "blue", "green", "violet", "light"):
                self._theme_surface.remove_css_class(f"vorem-theme-{value}")
            self._theme_surface.add_css_class(f"vorem-theme-{theme if theme in {"system", "dark", "blue", "green", "violet", "light"} else "dark"}")
        self._apply_accent_theme(theme)

    def _apply_accent_theme(self, theme):
        # Acentos suaves para no saturar la interfaz, más estados muy visibles
        # para los controles de reproducción.
        colors = {
            "dark": ("#7f9bbd", "#b7c9df"),
            "blue": ("#4fa3d1", "#8bd0f5"),
            "green": ("#5fb38a", "#91dfb5"),
            "violet": ("#9d7bd6", "#c5a9f2"),
            "light": ("#416b8a", "#638eaa"),
            "system": ("#71869a", "#9db0c1"),
        }
        accent, accent_hover = colors.get(theme, colors["dark"])
        theme_backgrounds = {
            "dark": ("#101216", "#15181e", "#101216"),
            "blue": ("#0b1522", "#102238", "#0c1725"),
            "green": ("#0d1713", "#12251c", "#0d1814"),
            "violet": ("#15101c", "#21162b", "#17101f"),
            "light": ("#f4f6f8", "#e8edf2", "#f7f8fa"),
            "system": ("#101216", "#15181e", "#101216"),
        }
        bg, sidebar_bg, pages_bg = theme_backgrounds.get(theme, theme_backgrounds["dark"])
        css = f"""
        .vorem-theme-surface {{ background-color: {bg}; }}
        .vorem-theme-surface .vorem-sidebar-surface {{ background-color: {sidebar_bg}; }}
        .vorem-theme-surface .vorem-pages-surface {{ background-color: {pages_bg}; }}
        .vorem-theme-surface .card {{ background-color: alpha(@window_fg_color, 0.035); border-radius: 12px; }}
        .vorem-theme-surface .card:hover {{ background-color: alpha({accent}, 0.08); }}
        .vorem-mode-button {{
            min-width: 42px; min-height: 36px;
            border-radius: 10px;
            border: 1px solid alpha({accent_hover}, 0.28);
            background-color: alpha({accent}, 0.07);
            color: {accent_hover};
        }}
        .vorem-mode-button:hover {{
            background-color: alpha({accent}, 0.16);
            border-color: alpha({accent_hover}, 0.58);
        }}
        .vorem-mode-off {{
            color: @window_fg_color;
            background-color: alpha(@window_fg_color, 0.05);
            border-color: alpha(@window_fg_color, 0.18);
        }}
        .vorem-shuffle.vorem-mode-active {{
            color: #ffffff;
            background-color: #1f9d68;
            border-color: #55d49a;
        }}
        .vorem-repeat-off {{
            color: @window_fg_color;
            background-color: alpha(@window_fg_color, 0.05);
            border-color: alpha(@window_fg_color, 0.18);
        }}
        .vorem-repeat-all {{
            color: #ffffff;
            background-color: #2676d8;
            border-color: #63a8ff;
        }}
        .vorem-repeat-one {{
            color: #ffffff;
            background-color: #9a4fd0;
            border-color: #d08cff;
        }}
        .vorem-theme-button {{
            min-height: 52px;
            border-radius: 12px;
            border: 1px solid alpha({accent_hover}, 0.24);
            background-color: alpha({accent}, 0.07);
            font-weight: 600;
        }}
        .vorem-theme-button:hover {{
            background-color: alpha({accent}, 0.16);
            border-color: alpha({accent_hover}, 0.52);
        }}
        .vorem-theme-selected {{
            background-color: alpha({accent}, 0.22);
            border: 2px solid {accent_hover};
        }}
        .vorem-theme-blue {{ color: #79c9f2; }}
        .vorem-theme-green {{ color: #7bd8a5; }}
        .vorem-theme-violet {{ color: #c29cf3; }}
        .vorem-theme-light {{ color: #77a9c7; }}
        .vorem-theme-dark {{ color: #b7c9df; }}
        .vorem-theme-system {{ color: #a9bac9; }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        display = self.get_display()
        if hasattr(self, "_theme_provider") and self._theme_provider is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self._theme_provider)
        self._theme_provider = provider
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _header(self):
        h=Adw.HeaderBar();h.set_title_widget(Adw.WindowTitle(title="Deluxevor Music",subtitle=""));b=Gtk.Button.new_from_icon_name("document-open-symbolic");b.set_tooltip_text("Abrir archivo de audio");b.connect("clicked",self._on_open_file_clicked);h.pack_start(b);return h
    def _sidebar(self):
        lb=Gtk.ListBox();lb.set_selection_mode(Gtk.SelectionMode.SINGLE);lb.add_css_class("navigation-sidebar")
        self.sidebar_list = lb
        for key,title,icon in SIDEBAR_SECTIONS:
            row=Adw.ActionRow(title=title);row.add_prefix(Gtk.Image.new_from_icon_name(icon));row.set_activatable(True);row.vorem_key=key;lb.append(row)
        lb.select_row(lb.get_row_at_index(0));lb.connect("row-selected", self._on_sidebar_selected)
        s=Gtk.ScrolledWindow();s.add_css_class("vorem-sidebar-surface");s.set_child(lb);s.set_size_request(230,-1);return s
    def _on_sidebar_selected(self, _listbox, row):
        if not row:
            return
        key = row.vorem_key
        self.current_page = key
        self.database.set_setting("last_page", key)
        # La navegación lateral siempre devuelve la interfaz al contenedor de
        # páginas. Antes, al abrir el reproductor grande, content_stack se
        # quedaba apuntando a "player-view" y los clics del sidebar parecían
        # no funcionar.
        self.content_stack.set_visible_child_name("library-pages")
        self.sidebar.set_visible(True)
        self.sidebar_separator.set_visible(True)
        self.player_bar.set_visible(True)
        self.stack.set_visible_child_name(key)

    def _setup_actions(self):
        a=Gio.SimpleAction.new("open-file",None);a.connect("activate",lambda *_:self._on_open_file_clicked(None));self.add_action(a)
    def _library_changed(self):
        self.songs_page.refresh();self.albums_page.refresh();self.artists_page.refresh();self.genres_page.refresh();self.favorites_page.refresh();self.playlists_page.refresh()
    def _play_song(self, row, queue):
        if not row or not row["path"]:
            return
        incoming = list(queue or [row])
        # Una reproducción nueva desde una lista crea la cola; si la pista ya
        # pertenece a la cola actual, la conservamos para no romper shuffle.
        if self.queue and any(r["id"] == row["id"] for r in self.queue) and incoming == self.queue:
            self.queue = list(self.queue)
        else:
            self.queue = incoming
            self.shuffle_history.clear()
            if self.shuffle_enabled and len(self.queue) > 1:
                others = [r for r in self.queue if r["id"] != row["id"]]
                random.shuffle(others)
                self.queue = [row] + others
        self.queue_index = next((i for i, r in enumerate(self.queue) if r["id"] == row["id"]), 0)
        self._load_queue_index(self.queue_index, show_view=True)

    def _load_queue_index(self, index, show_view=False):
        if not (0 <= index < len(self.queue)):
            return
        row = self.queue[index]
        self.queue_index = index
        self.player_bar.load_row(row)
        self.player_view.set_song(row)
        self.player_bar.set_navigation_enabled(len(self.queue) > 1)
        if show_view:
            self._show_player_view()
        self.current_song_id = row["id"]
        try:
            notification = Gio.Notification.new("Deluxevor Music")
            notification.set_body(f"{row['title'] or Path(row['path']).stem} · {row['artist'] or 'Artista desconocido'}")
            if self.application:
                self.application.send_notification("now-playing", notification)
                GLib.timeout_add_seconds(3, lambda: self.application.withdraw_notification("now-playing") or False)
        except Exception:
            pass

    def _play_all(self, rows):
        rows = list(rows or [])
        if not rows:
            return
        self.queue = rows
        self.shuffle_history.clear()
        if self.shuffle_enabled and len(self.queue) > 1:
            random.shuffle(self.queue)
        self._load_queue_index(0, show_view=True)

    def _set_shuffle(self, enabled):
        self.shuffle_enabled = bool(enabled)
        self.database.set_setting("shuffle", "1" if self.shuffle_enabled else "0")
        if hasattr(self, "songs_page"):
            self.songs_page.set_shuffle_state(self.shuffle_enabled)

    def _cycle_repeat(self):
        self.repeat_mode = {"off": "all", "all": "one", "one": "off"}[self.repeat_mode]
        self.database.set_setting("repeat_mode", self.repeat_mode)
        if hasattr(self, "songs_page"):
            self.songs_page.set_repeat_mode(self.repeat_mode)
        return self.repeat_mode

    def _next_song(self):
        if not self.queue:
            return
        if self.shuffle_enabled and len(self.queue) > 1:
            self.shuffle_history.append(self.queue_index)
            candidates = [i for i in range(len(self.queue)) if i != self.queue_index]
            self._load_queue_index(random.choice(candidates), show_view=False)
            return
        if self.queue_index + 1 < len(self.queue):
            self._load_queue_index(self.queue_index + 1, show_view=False)
        elif self.repeat_mode == "all":
            self._load_queue_index(0, show_view=False)
        else:
            self.player_bar.set_navigation_enabled(len(self.queue) > 1)

    def _previous_song(self):
        if not self.queue:
            return
        if self.engine.get_position() > 3:
            self.engine.seek(0)
            return
        if self.shuffle_enabled and self.shuffle_history:
            previous_index = self.shuffle_history.pop()
            self._load_queue_index(previous_index, show_view=False)
            return
        if self.queue_index > 0:
            self._load_queue_index(self.queue_index - 1, show_view=False)
        elif self.repeat_mode == "all":
            self._load_queue_index(len(self.queue) - 1, show_view=False)
        else:
            self.engine.seek(0)

    def _on_eos(self, _engine):
        if self.repeat_mode == "one" and self.queue and 0 <= self.queue_index < len(self.queue):
            self._load_queue_index(self.queue_index, show_view=False)
            return
        if not self.autoplay_enabled:
            self.engine.pause()
            return
        self._next_song()

    def _show_library_pages(self):
        self.content_stack.set_visible_child_name("library-pages")
        self.sidebar.set_visible(True)
        self.sidebar_separator.set_visible(True)
        self.player_bar.set_visible(True)
        try:
            self.stack.set_visible_child_name(self.current_page)
        except Exception:
            pass

    def _show_player_view(self):
        # Abrir una canción muestra el reproductor grande, pero conserva
        # la navegación lateral. La ocultamos únicamente al entrar en
        # pantalla completa desde el botón del reproductor.
        self.content_stack.set_visible_child_name("player-view")
        self.sidebar.set_visible(True)
        self.sidebar_separator.set_visible(True)
        self.player_bar.set_visible(False)
        self._set_player_fullscreen_ui(False)

    def _set_player_fullscreen_ui(self, active):
        self.sidebar.set_visible(not active)
        self.sidebar_separator.set_visible(not active)
        self.player_view.set_fullscreen_button_state(active)

    def _toggle_fullscreen(self):
        active = self.is_fullscreen()
        if active:
            self.unfullscreen()
            self._set_player_fullscreen_ui(False)
        else:
            self._set_player_fullscreen_ui(True)
            self.fullscreen()

    def _on_global_key(self,_controller,keyval,_keycode,_state):
        try:focus=self.get_focus()
        except Exception:focus=None
        # En GTK4 el foco real al escribir cae en el widget interno (Gtk.Text
        # para Entry, que implementa Gtk.Editable), no en el Gtk.Entry en sí.
        # Por eso se compara contra Gtk.Editable/Gtk.TextView y no solo Gtk.Entry.
        if isinstance(focus,(Gtk.Editable,Gtk.TextView)):return False
        if keyval in (Gdk.KEY_Right, getattr(Gdk, "KEY_AudioNext", -999)):self._next_song();return True
        if keyval in (Gdk.KEY_Left, getattr(Gdk, "KEY_AudioPrev", -999)):self._previous_song();return True
        if keyval in (Gdk.KEY_space, getattr(Gdk, "KEY_AudioPlay", -999)):self.engine.toggle();return True
        if keyval == getattr(Gdk, "KEY_AudioStop", -998):self.engine.stop();return True
        return False

    def _add_song_to_playlist(self,_button,song_id):
        playlists=self.database.list_playlists()
        if not playlists:
            self._new_playlist_prompt();return
        dialog=Adw.MessageDialog(transient_for=self,heading="Añadir a playlist",body="Selecciona una playlist.")
        for p in playlists:dialog.add_response(str(p["id"]),p["name"])
        dialog.add_response("cancel","Cancelar")
        dialog.connect("response",lambda _d,r:self._playlist_response(r,song_id));dialog.present()
    def _playlist_response(self,response,song_id):
        if response!="cancel":
            try:self.database.add_to_playlist(int(response),song_id)
            except Exception as exc:logger.warning("No se pudo añadir a playlist: %s",exc)
        self.playlists_page.refresh()
    def _new_playlist_prompt(self):
        d=Adw.MessageDialog(transient_for=self,heading="No hay playlists",body="Crea una playlist primero desde la sección Playlists.");d.add_response("ok","Entendido");d.present()
    def _on_open_file_clicked(self,_button):
        dialog=Gtk.FileDialog(title="Abrir archivo de audio");f=Gtk.FileFilter();f.set_name("Archivos de audio");[f.add_pattern(x) for x in ("*.mp3","*.flac","*.wav","*.ogg","*.opus","*.m4a","*.aac")];ls=Gio.ListStore.new(Gtk.FileFilter);ls.append(f);dialog.set_filters(ls);dialog.open(self,None,self._on_file_chosen)
    def _on_file_chosen(self,dialog,result):
        try:gfile=dialog.open_finish(result)
        except Exception:return
        if gfile and gfile.get_path():
            self.queue=[];self.queue_index=-1;self.shuffle_history.clear();self.player_bar.load_file(gfile.get_path());self.player_bar.set_navigation_enabled(False)
            self.player_view.set_song({"title": Path(gfile.get_path()).stem, "path": gfile.get_path(), "artist": "Archivo local", "album": "", "cover_data": None})
            self._show_player_view()
    def _on_engine_error(self,_engine,message):
        logger.warning("Error del motor de audio: %s",message);d=Adw.AlertDialog(heading="No se pudo reproducir el archivo",body=message);d.add_response("ok","Entendido");d.present(self)

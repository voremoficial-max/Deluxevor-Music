"""Lista de canciones y edición manual de metadatos de Deluxevor Music."""
import gi
from pathlib import Path

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
import threading
from app.services.lyrics import search_lyrics


def format_time(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"


class SongList(Gtk.Box):
    """Lista de canciones con menú contextual de tres puntos por canción."""

    def __init__(self, database, on_play, on_favorite_changed=None, on_playlist_add=None, on_changed=None, allow_selection=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.database = database
        self.on_play = on_play
        self.on_favorite_changed = on_favorite_changed
        self.on_playlist_add = on_playlist_add
        self.on_changed = on_changed
        self.rows = []
        self.play_buttons = []
        self.current_index = -1
        self.selected_ids = set()
        self.allow_selection = allow_selection
        self._build_generation = 0

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_vexpand(True)
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.container.set_margin_top(6)
        self.container.set_margin_bottom(6)
        self.container.set_margin_start(6)
        self.container.set_margin_end(6)
        self.scroller.set_child(self.container)
        self.append(self.scroller)

        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        self.key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(self.key_controller)

    def set_rows(self, rows):
        self.rows = list(rows)
        self.current_index = -1
        self.selected_ids.clear()
        while (child := self.container.get_first_child()) is not None:
            self.container.remove(child)
        self.play_buttons.clear()

        # Generación: si llega un set_rows nuevo mientras aún se están
        # construyendo filas de uno anterior (por ejemplo, tecleando rápido
        # en el buscador), el lote viejo se cancela solo en vez de seguir
        # agregando filas obsoletas de fondo.
        self._build_generation = getattr(self, "_build_generation", 0) + 1

        if not self.rows:
            empty = Gtk.Label(label="No hay canciones para mostrar.", xalign=0.5)
            empty.add_css_class("dim-label")
            empty.set_margin_top(40)
            self.container.append(empty)
            return

        # Con bibliotecas grandes, construir todas las filas de un tirón
        # bloquea la interfaz por un momento notorio. Se arman en lotes
        # chicos entre ciclos del bucle principal para que la ventana no
        # se congele al entrar a una página o al buscar.
        self._build_rows_chunk(self._build_generation, 0, chunk_size=40)

    def _build_rows_chunk(self, generation, start, chunk_size):
        if generation != self._build_generation:
            return False
        end = min(start + chunk_size, len(self.rows))
        for index in range(start, end):
            self.container.append(self._make_row(self.rows[index], index))
        if end < len(self.rows):
            GLib.idle_add(self._build_rows_chunk, generation, end, chunk_size)
        return False

    def _make_row(self, row, index):
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        outer.set_hexpand(True)
        outer.add_css_class("card")

        if self.allow_selection:
            check = Gtk.CheckButton()
            check.set_active(int(row["id"]) in self.selected_ids)
            check.set_tooltip_text("Seleccionar canción")
            check.connect("toggled", self._selection_toggled, int(row["id"]))
            outer.append(check)

        play = Gtk.Button()
        play.set_hexpand(True)
        play.set_halign(Gtk.Align.FILL)
        play.set_has_frame(False)
        play.set_focusable(True)
        play.set_tooltip_text(f"Reproducir {row['title'] or 'Sin título'}")
        play.connect("clicked", self._on_play_clicked, index)
        self.play_buttons.append(play)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.set_margin_top(9)
        content.set_margin_bottom(9)
        content.set_margin_start(8)
        content.set_margin_end(8)

        image = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        image.set_pixel_size(48)
        data = row["cover_data"] if "cover_data" in row.keys() else None
        if data:
            try:
                image.set_from_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes(data)))
            except Exception:
                pass
        content.append(image)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label=row["title"] or "Sin título", xalign=0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.add_css_class("heading")
        labels.append(title)
        subtitle = Gtk.Label(
            label=f"{row['artist'] or 'Artista desconocido'} · {row['album'] or 'Álbum desconocido'}",
            xalign=0,
        )
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle.add_css_class("dim-label")
        labels.append(subtitle)
        content.append(labels)

        duration = Gtk.Label(label=format_time(row["duration"]), xalign=1)
        duration.add_css_class("dim-label")
        duration.set_width_chars(5)
        content.append(duration)
        play.set_child(content)
        outer.append(play)

        is_favorite = bool(row["is_favorite"]) if "is_favorite" in row.keys() else self.database.is_favorite(row["id"])
        fav = Gtk.Button.new_from_icon_name(
            "starred-symbolic" if is_favorite else "non-starred-symbolic"
        )
        fav.set_has_frame(False)
        fav.set_tooltip_text("Quitar de favoritos" if is_favorite else "Añadir a favoritos")
        fav.connect("clicked", self._on_favorite_clicked, row["id"])
        outer.append(fav)

        if self.on_playlist_add is not None:
            add = Gtk.Button.new_from_icon_name("list-add-symbolic")
            add.set_has_frame(False)
            add.set_tooltip_text("Añadir a playlist")
            add.connect("clicked", self.on_playlist_add, row["id"])
            outer.append(add)

        # Menú de tres puntos: edición y letras sin saturar visualmente cada fila.
        more = Gtk.MenuButton()
        more.set_icon_name("view-more-symbolic")
        more.set_tooltip_text("Más opciones")
        more.set_has_frame(False)
        more.set_popover(self._build_more_popover(row))
        outer.append(more)
        return outer

    def _build_more_popover(self, row):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6); box.set_margin_bottom(6); box.set_margin_start(6); box.set_margin_end(6)

        edit_title = Gtk.Button(label="Editar nombre")
        edit_title.set_has_frame(False)
        edit_title.connect("clicked", lambda *_: (popover.popdown(), self._open_editor(row, focus_lyrics=False, title_only=True)))
        box.append(edit_title)

        edit_cover = Gtk.Button(label="Cambiar carátula")
        edit_cover.set_has_frame(False)
        edit_cover.connect("clicked", lambda *_: (popover.popdown(), self._open_editor(row, focus_lyrics=False, cover_only=True)))
        box.append(edit_cover)

        lyrics = Gtk.Button(label="Editar letra")
        lyrics.set_has_frame(False)
        lyrics.connect("clicked", lambda *_: (popover.popdown(), self._open_editor(row, focus_lyrics=True, lyrics_only=True)))
        box.append(lyrics)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        delete = Gtk.Button(label="Eliminar")
        delete.set_has_frame(False)
        delete.add_css_class("destructive-action")
        delete.connect("clicked", lambda *_: (popover.popdown(), self._confirm_delete(row)))
        box.append(delete)

        popover.set_child(box)
        return popover

    def _confirm_delete(self, row):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="¿Eliminar esta canción?",
            body=f'Se borrará “{row["title"]}” del disco. Esta acción no se puede deshacer.',
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("delete", "Eliminar")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response, row["id"])
        dialog.present()

    def _on_delete_response(self, _dialog, response, song_id):
        if response != "delete":
            return
        self.database.delete_song(song_id)
        if self.on_changed:
            self.on_changed()

    def _open_editor(self, row, focus_lyrics=False, title_only=False, cover_only=False, lyrics_only=False):
        root = self.get_root()
        dialog = Gtk.Window(title="Editar canción")
        dialog.set_default_size(620, 700)
        dialog.set_modal(True)
        if root:
            dialog.set_transient_for(root)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(20)
        outer.set_margin_bottom(20)
        outer.set_margin_start(20)
        outer.set_margin_end(20)
        dialog.set_child(outer)

        title = Gtk.Label(label="Editar información", xalign=0)
        title.add_css_class("title-2")
        outer.append(title)
        hint = Gtk.Label(label="Los cambios se guardan en la biblioteca de Deluxevor Music y sobreviven a nuevos escaneos.", xalign=0)
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        outer.append(hint)

        form = Gtk.Grid(column_spacing=10, row_spacing=10)
        form.set_hexpand(True)
        outer.append(form)
        fields = {}
        if not cover_only and not lyrics_only:
            lab = Gtk.Label(label="Nombre", xalign=0)
            entry = Gtk.Entry(); entry.set_hexpand(True); entry.set_text(str(row["title"] or ""))
            form.attach(lab, 0, 0, 1, 1); form.attach(entry, 1, 0, 1, 1); fields["title"] = entry

        cover_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        cover_preview = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        cover_preview.set_pixel_size(96)
        cover_box.append(cover_preview)
        cover_actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        choose = Gtk.Button(label="Cambiar carátula…")
        clear = Gtk.Button(label="Quitar carátula")
        choose.set_halign(Gtk.Align.START)
        clear.set_halign(Gtk.Align.START)
        cover_actions.append(choose)
        cover_actions.append(clear)
        cover_box.append(cover_actions)
        outer.append(cover_box)
        cover_box.set_visible(not title_only and not lyrics_only)

        cover_data = row["cover_data"] if "cover_data" in row.keys() else None
        self._set_cover_preview(cover_preview, cover_data)

        def choose_cover(_button):
            file_dialog = Gtk.FileDialog(title="Seleccionar carátula")
            file_filter = Gtk.FileFilter()
            file_filter.set_name("Imágenes")
            for mime in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                file_filter.add_mime_type(mime)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(file_filter)
            file_dialog.set_filters(filters)
            file_dialog.open(dialog, None, cover_selected)

        def cover_selected(file_dialog, result):
            nonlocal cover_data
            try:
                gfile = file_dialog.open_finish(result)
                if not gfile or not gfile.get_path():
                    return
                data = Path(gfile.get_path()).read_bytes()
                if len(data) > 12 * 1024 * 1024:
                    self._show_info(dialog, "Carátula demasiado grande", "Elige una imagen de menos de 12 MB.")
                    return
                cover_data = data
                self._set_cover_preview(cover_preview, cover_data)
            except Exception as exc:
                self._show_info(dialog, "No se pudo abrir la imagen", str(exc))

        def clear_cover(_button):
            nonlocal cover_data
            cover_data = None
            self._set_cover_preview(cover_preview, None)

        choose.connect("clicked", choose_cover)
        clear.connect("clicked", clear_cover)

        lyrics_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lyrics_label = Gtk.Label(label="Letra", xalign=0)
        lyrics_label.add_css_class("heading")
        lyrics_label.set_hexpand(True)
        lyrics_header.append(lyrics_label)
        search_lyrics_button = Gtk.Button(label="Buscar letra")
        search_lyrics_button.set_tooltip_text("Buscar automáticamente en Internet usando canción y artista")
        lyrics_header.append(search_lyrics_button)
        outer.append(lyrics_header)
        lyrics_header.set_visible(not title_only and not cover_only)
        lyrics_scroll = Gtk.ScrolledWindow()
        lyrics_scroll.set_min_content_height(210)
        lyrics_scroll.set_vexpand(True)
        lyrics_view = Gtk.TextView()
        lyrics_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        lyrics_view.set_vexpand(True)
        lyrics_view.get_buffer().set_text(str(row["lyrics"] or "") if "lyrics" in row.keys() else "")
        lyrics_scroll.set_child(lyrics_view)

        def run_lyrics_search(_button):
            title_query = str(row["title"] or "").strip()
            artist_query = str(row["artist"] or "").strip()
            if not title_query or not artist_query:
                self._show_info(dialog, "No se puede buscar", "La canción necesita tener nombre y artista.")
                return
            search_lyrics_button.set_sensitive(False)
            search_lyrics_button.set_label("Buscando…")
            def worker():
                try:
                    result = search_lyrics(
                        title_query,
                        artist_query,
                        genius_token=self.database.get_setting("genius_token", "") or "",
                    )
                    error = None
                except Exception as exc:
                    result = ""
                    error = str(exc)
                def finish():
                    search_lyrics_button.set_sensitive(True)
                    search_lyrics_button.set_label("Buscar letra")
                    if result:
                        lyrics_view.get_buffer().set_text(result)
                    else:
                        self._show_info(dialog, "Letra no encontrada", error or "No se encontró una letra para esta canción.")
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker, daemon=True).start()

        search_lyrics_button.connect("clicked", run_lyrics_search)
        outer.append(lyrics_scroll)
        lyrics_scroll.set_visible(not title_only and not cover_only)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        save = Gtk.Button(label="Guardar cambios")
        save.add_css_class("suggested-action")
        actions.append(cancel)
        actions.append(save)
        outer.append(actions)

        cancel.connect("clicked", lambda *_: dialog.close())

        def save_changes(_button):
            buffer = lyrics_view.get_buffer()
            start, end = buffer.get_bounds()
            lyrics_text = buffer.get_text(start, end, True)
            try:
                current_title = fields["title"].get_text() if "title" in fields else str(row["title"] or "")
                current_cover = cover_data if not title_only and not lyrics_only else (row["cover_data"] if "cover_data" in row.keys() else None)
                current_lyrics = lyrics_text if not title_only and not cover_only else str(row["lyrics"] or "")
                self.database.update_song_metadata(
                    int(row["id"]),
                    title=current_title,
                    artist=str(row["artist"] or ""),
                    album=str(row["album"] or ""),
                    genre=str(row["genre"] or ""),
                    cover_data=current_cover,
                    lyrics=current_lyrics,
                )
                dialog.close()
                if self.on_changed:
                    self.on_changed()
                else:
                    self.set_rows(self.database.list_songs())
            except Exception as exc:
                self._show_info(dialog, "No se pudieron guardar los cambios", str(exc))

        save.connect("clicked", save_changes)
        dialog.present()
        if focus_lyrics:
            GLib.idle_add(lambda: (lyrics_view.grab_focus(), False)[1])

    @staticmethod
    def _set_cover_preview(image, data):
        if data:
            try:
                image.set_from_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes(data)))
                return
            except Exception:
                pass
        image.set_from_icon_name("audio-x-generic-symbolic")
        image.set_pixel_size(96)

    @staticmethod
    def _show_info(parent, heading, body):
        dialog = Gtk.AlertDialog(message=heading, detail=body)
        dialog.show(parent)

    def _selection_toggled(self, _button, song_id):
        if song_id in self.selected_ids:
            self.selected_ids.remove(song_id)
        else:
            self.selected_ids.add(song_id)
        self._notify_selection_changed()

    def _notify_selection_changed(self):
        callback = getattr(self, "on_selection_changed", None)
        if callback:
            callback(list(self.selected_ids))

    def get_selected_rows(self):
        return [row for row in self.rows if int(row["id"]) in self.selected_ids]

    def clear_selection(self):
        self.selected_ids.clear()
        self.set_rows(self.rows)

    def _on_play_clicked(self, _button, index):
        if not (0 <= index < len(self.rows)):
            return
        self.current_index = index
        self.on_play(self.rows[index], self.rows)

    def play_index(self, index):
        self._on_play_clicked(None, index)

    def _on_favorite_clicked(self, _button, song_id):
        self.database.toggle_favorite(song_id)
        if self.on_favorite_changed:
            self.on_favorite_changed()
        else:
            self.set_rows(self.rows)

    def _on_key_pressed(self, _controller, keyval, _keycode, _state):
        if not self.rows:
            return False
        if keyval == Gdk.KEY_Down:
            self.current_index = min(len(self.rows) - 1, self.current_index + 1)
            if self.current_index < len(self.play_buttons):
                self.play_buttons[self.current_index].grab_focus()
            return True
        if keyval == Gdk.KEY_Up:
            self.current_index = max(0, self.current_index - 1)
            if self.current_index < len(self.play_buttons):
                self.play_buttons[self.current_index].grab_focus()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self.play_index(self.current_index if self.current_index >= 0 else 0)
            return True
        return False

"""Página de descarga de audio desde YouTube."""
import threading
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk

from app.services.downloader import search_youtube, download_youtube, apply_user_metadata
from app.metadata.reader import read_song


class DownloadPage(Gtk.Box):
    def __init__(self, database, on_downloaded=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.database = database
        self.on_downloaded = on_downloaded
        self.results = []
        self._title_query = ""
        self._artist_query = ""
        self.set_margin_top(24); self.set_margin_bottom(24)
        self.set_margin_start(28); self.set_margin_end(28)

        title = Gtk.Label(label="Descargar música", xalign=0)
        title.add_css_class("title-2")
        self.append(title)
        subtitle = Gtk.Label(
            label="Busca por nombre de canción y artista. Se requiere conexión a Internet.",
            xalign=0
        )
        subtitle.add_css_class("dim-label"); subtitle.set_wrap(True)
        self.append(subtitle)

        form = Gtk.Grid(column_spacing=10, row_spacing=10)
        song_label = Gtk.Label(label="Nombre de la canción", xalign=0)
        artist_label = Gtk.Label(label="Artista", xalign=0)
        self.song_entry = Gtk.Entry(placeholder_text="Ej. Urusei Blue Bleesd")
        self.artist_entry = Gtk.Entry(placeholder_text="Ej. nombre del artista")
        self.song_entry.set_hexpand(True); self.artist_entry.set_hexpand(True)
        form.attach(song_label, 0, 0, 1, 1); form.attach(self.song_entry, 1, 0, 1, 1)
        form.attach(artist_label, 0, 1, 1, 1); form.attach(self.artist_entry, 1, 1, 1, 1)
        self.search_button = Gtk.Button(label="Buscar en YouTube")
        self.search_button.add_css_class("suggested-action")
        self.search_button.connect("clicked", self._search)
        form.attach(self.search_button, 1, 2, 1, 1)
        self.append(form)

        self.status = Gtk.Label(label="", xalign=0)
        self.status.add_css_class("dim-label")
        self.append(self.status)

        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True); scroll.set_child(self.results_box)
        self.append(scroll)

    def _search(self, _button):
        title = self.song_entry.get_text().strip()
        artist = self.artist_entry.get_text().strip()
        if not title or not artist:
            self._info("Datos incompletos", "Escribe el nombre de la canción y el artista por separado.")
            return
        self._title_query, self._artist_query = title, artist
        self.search_button.set_sensitive(False); self.status.set_label("Buscando resultados…")
        self._clear_results()
        def worker():
            try:
                results = search_youtube(title, artist)
                error = None
            except Exception as exc:
                results = []; error = str(exc)
            GLib.idle_add(self._show_results, results, error)
        threading.Thread(target=worker, daemon=True).start()

    def _show_results(self, results, error):
        self.search_button.set_sensitive(True)
        self.results = results or []
        if error:
            self.status.set_label("No se pudo buscar.")
            self._info("Error de búsqueda", error)
            return False
        self.status.set_label(f"{len(self.results)} resultado(s). Selecciona el que quieras descargar.")
        for result in self.results:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class("card")
            row.set_margin_top(4); row.set_margin_bottom(4)
            row.set_margin_start(4); row.set_margin_end(4)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            text.set_hexpand(True)
            lab = Gtk.Label(label=result["title"], xalign=0); lab.add_css_class("heading"); lab.set_wrap(True)
            meta = Gtk.Label(label=f'{result["channel"]} · {self._format_duration(result["duration"])}', xalign=0)
            meta.add_css_class("dim-label")
            text.append(lab); text.append(meta)
            row.append(text)
            button = Gtk.Button(label="Descargar")
            button.set_valign(Gtk.Align.CENTER)
            button.add_css_class("suggested-action")
            button.connect("clicked", self._download_clicked, result, row)
            row.append(button)
            self.results_box.append(row)
        return False

    def _download_clicked(self, button, result, row):
        folders = self.database.get_folders()
        destination = folders[0] if folders else str(__import__("pathlib").Path.home() / "Music")
        button.set_sensitive(False)
        self.status.set_label("Descargando y preparando MP3…")
        def progress(data):
            status = data.get("status")
            if status == "downloading":
                percent = data.get("_percent_str", "").strip()
                GLib.idle_add(self.status.set_label, f"Descargando… {percent}")
            elif status == "finished":
                GLib.idle_add(self.status.set_label, "Procesando audio, carátula y metadatos…")
        def worker():
            try:
                path = download_youtube(result, destination, progress)
                # Usa el título y el canal reales del video de YouTube elegido,
                # no lo que se escribió en el buscador.
                apply_user_metadata(path, result.get("title", ""), result.get("channel", ""))
                # Se agrega directo a la biblioteca leyendo solo este archivo,
                # en vez de forzar un reescaneo completo de la carpeta.
                song = read_song(path)
                if song is not None:
                    self.database.upsert_song(song)
                error = None
            except Exception as exc:
                path = None; error = str(exc)
            GLib.idle_add(self._download_finished, button, path, error)
        threading.Thread(target=worker, daemon=True).start()

    def _download_finished(self, button, path, error):
        button.set_sensitive(True)
        if error:
            self.status.set_label("La descarga falló.")
            self._info("No se pudo descargar", error)
        else:
            self.status.set_label(f"Descarga completada: {path.name}")
            self._info("Descarga completada", f"Se guardó en:\n{path}")
            if self.on_downloaded:
                self.on_downloaded()
        return False

    def _clear_results(self):
        while (child := self.results_box.get_first_child()) is not None:
            self.results_box.remove(child)

    @staticmethod
    def _format_duration(seconds):
        seconds = int(seconds or 0)
        return f"{seconds // 60}:{seconds % 60:02d}" if seconds else "Duración desconocida"

    def _info(self, heading, body):
        dialog = Adw.MessageDialog(transient_for=self.get_root(), heading=heading, body=body)
        dialog.add_response("ok", "Aceptar")
        dialog.present()

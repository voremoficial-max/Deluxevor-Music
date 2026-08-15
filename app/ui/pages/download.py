"""Página de descargas con cola, progreso, reintento y multi-descarga.

Cada descarga se ejecuta en su propio hilo, así que se pueden lanzar varias
al mismo tiempo (multi-descarga). Los widgets de cada descarga en curso se
crean una sola vez y se actualizan en el sitio (no se reconstruye toda la
lista en cada evento de progreso), y las actualizaciones de porcentaje se
limitan en el tiempo: esto evita que la interfaz se quede "en blanco" o sin
refrescar cuando yt-dlp reporta progreso muy seguido.
"""
import re
import threading
import time
from pathlib import Path
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk

from app.services.downloader import search_youtube, download_youtube, apply_user_metadata
from app.metadata.reader import read_song

# yt-dlp puede incluir secuencias de color ANSI dentro de "_percent_str"
# cuando su formateador de progreso decide colorear el texto. Si no se
# limpian, el porcentaje calculado a partir de ese texto puede salir vacío
# o corrupto y la descarga en curso parece no mostrar nada.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# Umbral mínimo entre refrescos de la interfaz por descarga, en segundos.
_PROGRESS_THROTTLE = 0.25


def _parse_percent(data: dict) -> str:
    """Calcula un porcentaje legible y confiable a partir del hook de yt-dlp."""
    raw = _ANSI_RE.sub("", (data.get("_percent_str") or "")).strip()
    if raw:
        return raw
    downloaded = data.get("downloaded_bytes") or 0
    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
    if total:
        return f"{(downloaded / total) * 100:.1f}%"
    return "0%"


class DownloadPage(Gtk.Box):
    def __init__(self, database, on_downloaded=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.database = database; self.on_downloaded = on_downloaded
        self.results = []; self.jobs = {}; self._job_counter = 0; self._job_widgets = {}
        self.set_margin_top(24); self.set_margin_bottom(24); self.set_margin_start(28); self.set_margin_end(28)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Descargar música", xalign=0); title.add_css_class("title-2"); title.set_hexpand(True); head.append(title)
        self.search_view_btn = Gtk.Button(label="Buscar"); self.search_view_btn.connect("clicked", lambda *_: self._show_view("search")); head.append(self.search_view_btn)
        self.active_btn = Gtk.Button(label="Descargas en curso (0)"); self.active_btn.connect("clicked", lambda *_: self._show_view("downloads")); head.append(self.active_btn)
        self.append(head)

        self.stack = Gtk.Stack(); self.stack.set_vexpand(True); self.append(self.stack)
        self.search_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); self.stack.add_named(self.search_page, "search")
        self.downloads_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        subtitle = Gtk.Label(label="Busca por nombre de canción y artista. Se requiere conexión a Internet.", xalign=0); subtitle.add_css_class("dim-label"); subtitle.set_wrap(True); self.search_page.append(subtitle)
        form = Gtk.Grid(column_spacing=10, row_spacing=10)
        song_label = Gtk.Label(label="Nombre de la canción", xalign=0); artist_label = Gtk.Label(label="Artista", xalign=0)
        self.song_entry = Gtk.Entry(placeholder_text="Ej. Urusei Blue Bleesd"); self.artist_entry = Gtk.Entry(placeholder_text="Ej. nombre del artista")
        self.song_entry.set_hexpand(True); self.artist_entry.set_hexpand(True)
        form.attach(song_label, 0, 0, 1, 1); form.attach(self.song_entry, 1, 0, 1, 1); form.attach(artist_label, 0, 1, 1, 1); form.attach(self.artist_entry, 1, 1, 1, 1)
        self.search_button = Gtk.Button(label="Buscar"); self.search_button.add_css_class("suggested-action"); self.search_button.connect("clicked", self._search); form.attach(self.search_button, 1, 2, 1, 1)
        self.search_page.append(form)

        results_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status = Gtk.Label(label="", xalign=0); self.status.add_css_class("dim-label"); self.status.set_hexpand(True); results_head.append(self.status)
        # Botón de multi-descarga: lanza todas las descargas de los
        # resultados visibles a la vez, cada una en su propio hilo.
        self.download_all_button = Gtk.Button(label="Descargar todo")
        self.download_all_button.set_visible(False)
        self.download_all_button.connect("clicked", self._download_all)
        results_head.append(self.download_all_button)
        self.search_page.append(results_head)

        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True); scroll.set_child(self.results_box); self.search_page.append(scroll)
        self.downloads_scroll = Gtk.ScrolledWindow(); self.downloads_scroll.set_vexpand(True); self.downloads_scroll.set_child(self.downloads_page)
        self.stack.add_named(self.downloads_scroll, "downloads")
        self._refresh_downloads()

    def _show_view(self, name):
        self.stack.set_visible_child_name(name)

    def _search(self, _button):
        title = self.song_entry.get_text().strip(); artist = self.artist_entry.get_text().strip()
        if not title or not artist: self._info("Datos incompletos", "Escribe el nombre de la canción y el artista por separado."); return
        self.search_button.set_sensitive(False); self.status.set_label("Buscando resultados…"); self._clear_results()
        self.download_all_button.set_visible(False)
        def worker():
            try: results = search_youtube(title, artist); error = None
            except Exception as exc: results = []; error = str(exc)
            GLib.idle_add(self._show_results, results, error)
        threading.Thread(target=worker, daemon=True).start()

    def _show_results(self, results, error):
        self.search_button.set_sensitive(True); self.results = results or []
        if error: self.status.set_label("No se pudo buscar."); self._info("Error de búsqueda", error); return False
        self.status.set_label(f"{len(self.results)} resultado(s). Selecciona el que quieras descargar, o descárgalos todos.")
        self.download_all_button.set_visible(bool(self.results))
        self._result_buttons = []
        for result in self.results:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12); row.add_css_class("card")
            row.set_margin_top(4); row.set_margin_bottom(4); row.set_margin_start(4); row.set_margin_end(4)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3); text.set_hexpand(True)
            lab = Gtk.Label(label=result["title"], xalign=0); lab.add_css_class("heading"); lab.set_wrap(True)
            meta = Gtk.Label(label=f'{result["channel"]} · {self._format_duration(result["duration"])}', xalign=0); meta.add_css_class("dim-label")
            text.append(lab); text.append(meta); row.append(text)
            button = Gtk.Button(label="Descargar"); button.set_valign(Gtk.Align.CENTER); button.add_css_class("suggested-action")
            button.connect("clicked", self._download_clicked, result, row); row.append(button); self.results_box.append(row)
            self._result_buttons.append((result, button))
        return False

    def _download_all(self, _button):
        # Multi-descarga: inicia todos los resultados pendientes a la vez,
        # cada uno como una tarea independiente (mismo mecanismo que un
        # clic individual en "Descargar").
        for result, button in getattr(self, "_result_buttons", []):
            if button.get_sensitive():
                self._download_clicked(button, result, None)
        self._show_view("downloads")

    def _download_clicked(self, button, result, row, retry_job=None):
        folders = self.database.get_folders(); destination = folders[0] if folders else str(Path.home() / "Music")
        button.set_sensitive(False)
        if retry_job is None:
            self._job_counter += 1; job_id = self._job_counter
            job = {"id": job_id, "result": result, "destination": destination, "status": "downloading",
                   "percent": "0%", "error": "", "button": button, "last_update": 0.0}
            self.jobs[job_id] = job
        else:
            job_id = retry_job; job = self.jobs[job_id]; job.update(status="downloading", percent="0%", error="", button=button, last_update=0.0)
        self._refresh_downloads(); self._update_active_count()
        # Al empezar una descarga, saltamos directamente a "Descargas en
        # curso" para que se vea de inmediato el nombre y el porcentaje,
        # sin depender de que el usuario recuerde cambiar de pestaña.
        self._show_view("downloads")

        def progress(data):
            status = data.get("status")
            if status == "downloading":
                now = time.monotonic()
                # Se limita la frecuencia de refresco: yt-dlp puede llamar a
                # este hook muchas veces por segundo, y reconstruir/actualizar
                # la interfaz en cada llamada puede saturar el bucle principal
                # de GTK e impedir que se vea a tiempo el progreso real.
                if now - job.get("last_update", 0.0) < _PROGRESS_THROTTLE:
                    return
                job["last_update"] = now
                job["percent"] = _parse_percent(data)
                GLib.idle_add(self._job_progress, job_id, job["percent"])

        def worker():
            try:
                path = download_youtube(result, destination, progress)
                apply_user_metadata(path, result.get("title", ""), result.get("channel", ""))
                song = read_song(path)
                if song is not None: self.database.upsert_song(song)
                error = None
            except Exception as exc: path = None; error = str(exc)
            GLib.idle_add(self._download_finished, job_id, path, error)
        threading.Thread(target=worker, daemon=True).start()

    def _job_progress(self, job_id, percent):
        job = self.jobs.get(job_id)
        if job:
            job["percent"] = percent
            self._update_job_widget(job_id, job)
        return False

    def _download_finished(self, job_id, path, error):
        job = self.jobs.get(job_id)
        if not job: return False
        job["status"] = "failed" if error else "completed"; job["error"] = error or ""; job["path"] = path
        if job.get("button"): job["button"].set_sensitive(True)
        self._refresh_downloads(); self._update_active_count()
        if error: self.status.set_label("La descarga falló. Puedes reintentar desde Descargas en curso.")
        else:
            self.status.set_label(f"Descarga completada: {path.name}")
            if self.on_downloaded: self.on_downloaded()
        return False

    def _refresh_downloads(self):
        """Reconstruye la lista completa de tarjetas de descarga.

        Se usa al entrar/salir de trabajos (nuevo, terminado, fallido) y al
        mostrar la página por primera vez. Las actualizaciones de porcentaje
        mientras una descarga está en curso NO pasan por aquí: usan
        _update_job_widget, que solo toca la etiqueta de esa tarjeta.
        """
        while (child := self.downloads_page.get_first_child()) is not None: self.downloads_page.remove(child)
        self._job_widgets.clear()
        if not self.jobs:
            lab = Gtk.Label(label="No hay descargas todavía.", xalign=0); lab.add_css_class("dim-label"); self.downloads_page.append(lab); return
        for job_id, job in self.jobs.items():
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); box.add_css_class("card"); box.set_margin_top(3); box.set_margin_bottom(3)
            box.set_margin_start(6); box.set_margin_end(6)
            name = job["result"].get("title", "Canción")
            channel = job["result"].get("channel", "")
            title_label = Gtk.Label(label=f"{name} · {channel}" if channel else name, xalign=0)
            title_label.add_css_class("heading"); title_label.set_wrap(True); box.append(title_label)
            state_label = Gtk.Label(xalign=0); state_label.set_wrap(True); box.append(state_label)
            progress_bar = Gtk.ProgressBar(); progress_bar.set_show_text(False)
            widgets = {"title": title_label, "state": state_label, "progress": progress_bar, "retry": None, "box": box}
            if job["status"] == "downloading":
                box.append(progress_bar)
            elif job["status"] == "failed":
                retry = Gtk.Button(label="Reintentar"); retry.connect("clicked", self._retry, job_id); box.append(retry)
                widgets["retry"] = retry
            self.downloads_page.append(box)
            self._job_widgets[job_id] = widgets
            self._update_job_widget(job_id, job)

    def _update_job_widget(self, job_id, job):
        """Actualiza en el sitio el porcentaje/estado de una tarjeta de descarga
        ya construida, sin reconstruir el resto de la lista."""
        widgets = self._job_widgets.get(job_id)
        if not widgets:
            self._refresh_downloads(); return
        if job["status"] == "downloading":
            widgets["state"].set_label(f"Descargando… {job['percent']}")
            widgets["state"].remove_css_class("dim-label")
            fraction = self._percent_to_fraction(job["percent"])
            if fraction is not None:
                widgets["progress"].set_fraction(fraction)
            else:
                widgets["progress"].pulse()
        elif job["status"] == "failed":
            widgets["state"].set_label(f"Falló: {job['error']}")
        else:
            widgets["state"].set_label("Completada ✓")
            widgets["state"].add_css_class("dim-label")

    @staticmethod
    def _percent_to_fraction(percent_text):
        try:
            return max(0.0, min(1.0, float(percent_text.strip().rstrip("%")) / 100))
        except (TypeError, ValueError):
            return None

    def _retry(self, button, job_id):
        job = self.jobs.get(job_id)
        if not job: return
        self._download_clicked(button, job["result"], None, job_id)

    def _update_active_count(self):
        active = sum(1 for j in self.jobs.values() if j["status"] == "downloading")
        self.active_btn.set_label(f"Descargas en curso ({active})")

    def _clear_results(self):
        while (child := self.results_box.get_first_child()) is not None: self.results_box.remove(child)

    @staticmethod
    def _format_duration(seconds):
        seconds = int(seconds or 0); return f"{seconds // 60}:{seconds % 60:02d}" if seconds else "Duración desconocida"

    def _info(self, heading, body):
        dialog = Adw.MessageDialog(transient_for=self.get_root(), heading=heading, body=body); dialog.add_response("ok", "Aceptar"); dialog.present()

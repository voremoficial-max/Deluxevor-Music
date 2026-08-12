"""Escáner incremental de biblioteca ejecutado fuera del hilo de GTK."""
from pathlib import Path
from threading import Event, Thread

from app.database.db import MusicDatabase
from app.metadata.reader import SUPPORTED_EXTENSIONS, read_song
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LibraryScanner:
    def __init__(self, database: MusicDatabase):
        self.database = database
        self._thread = None
        self._cancel = Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        self._cancel.set()

    def start(self, on_progress=None, on_finished=None):
        if self.running:
            return False
        self._cancel.clear()
        self._thread = Thread(
            target=self._run,
            args=(on_progress, on_finished),
            name="vorem-library-scan",
            daemon=True,
        )
        self._thread.start()
        return True

    def _run(self, on_progress, on_finished):
        added = updated = skipped = removed = 0
        errors = 0
        try:
            folders = self.database.get_folders()
            discovered: dict[str, tuple[int, float]] = {}
            total = 0

            for folder in folders:
                root = Path(folder).expanduser()
                if not root.is_dir():
                    logger.warning("Carpeta de música inexistente: %s", root)
                    continue
                try:
                    for path in root.rglob("*"):
                        if self._cancel.is_set():
                            return self._finish(on_finished, False, added, updated, skipped, removed, errors)
                        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                            try:
                                stat = path.stat()
                                discovered[str(path.resolve())] = (stat.st_size, stat.st_mtime)
                            except OSError:
                                errors += 1
                            total += 1
                            if on_progress:
                                on_progress(total, total, path.name)
                except OSError as exc:
                    logger.warning("No se pudo recorrer %s: %s", root, exc)
                    errors += 1

            processed = 0
            for path_str, (size, mtime) in discovered.items():
                if self._cancel.is_set():
                    return self._finish(on_finished, False, added, updated, skipped, removed, errors)
                if not self.database.needs_update(path_str, size, mtime):
                    skipped += 1
                else:
                    song = read_song(Path(path_str))
                    if song is None:
                        errors += 1
                    else:
                        existed = self.database.get_song_by_path(path_str) is not None
                        self.database.upsert_song(song)
                        updated += int(existed)
                        added += int(not existed)
                processed += 1
                if on_progress:
                    on_progress(processed, len(discovered), Path(path_str).name)

            # Solo elimina canciones de las carpetas administradas. Las rutas fuera de ellas no se tocan.
            if folders:
                current = set(discovered)
                existing = {row[0] for row in self._all_paths()}
                stale = existing - current
                if stale:
                    self.database.remove_paths(stale)
                    removed = len(stale)

            return self._finish(on_finished, True, added, updated, skipped, removed, errors)
        except Exception as exc:
            logger.exception("Error inesperado durante el escaneo: %s", exc)
            errors += 1
            return self._finish(on_finished, False, added, updated, skipped, removed, errors, str(exc))

    def _all_paths(self):
        with self.database.connect() as conn:
            return conn.execute("SELECT path FROM songs").fetchall()

    @staticmethod
    def _finish(callback, success, added, updated, skipped, removed, errors, error=None):
        result = {
            "success": success,
            "added": added,
            "updated": updated,
            "skipped": skipped,
            "removed": removed,
            "errors": errors,
            "error": error,
        }
        if callback:
            callback(result)
        return result

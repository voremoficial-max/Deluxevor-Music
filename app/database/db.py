"""Persistencia SQLite de la biblioteca musical y funciones de Fase 4."""
import sqlite3
from pathlib import Path
from typing import Iterable

from app.models.song import Song
from app.utils.logger import get_logger

logger = get_logger(__name__)
DB_DIR = Path.home() / ".local" / "share" / "vorem-music"
DB_PATH = DB_DIR / "library.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT NOT NULL,
    genre TEXT NOT NULL,
    year TEXT NOT NULL DEFAULT '',
    duration REAL NOT NULL DEFAULT 0,
    track_number INTEGER NOT NULL DEFAULT 0,
    file_size INTEGER NOT NULL DEFAULT 0,
    modified_time REAL NOT NULL DEFAULT 0,
    cover_data BLOB,
    lyrics TEXT NOT NULL DEFAULT '',
    metadata_edited INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_songs_album ON songs(album COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_songs_genre ON songs(genre COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_songs_modified ON songs(modified_time);
CREATE INDEX IF NOT EXISTS idx_songs_album_artist ON songs(album COLLATE NOCASE, artist COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_songs_artist_album ON songs(artist COLLATE NOCASE, album COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_songs_genre_artist ON songs(genre COLLATE NOCASE, artist COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS music_folders (
    path TEXT PRIMARY KEY,
    added_at REAL NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    song_id INTEGER PRIMARY KEY,
    created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
    FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id INTEGER NOT NULL,
    song_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    added_at REAL NOT NULL DEFAULT (strftime('%s','now')),
    PRIMARY KEY(playlist_id, song_id),
    FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_playlist_songs_position ON playlist_songs(playlist_id, position);

"""


class MusicDatabase:
    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache = {}
        self.initialize()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10, cached_statements=128)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -16000")
        return conn

    def initialize(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            # Historial eliminado en Fase 7: conservar la biblioteca pero retirar la tabla antigua.
            conn.execute("DROP TABLE IF EXISTS history")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
            if "lyrics" not in columns:
                conn.execute("ALTER TABLE songs ADD COLUMN lyrics TEXT NOT NULL DEFAULT ''")
            if "metadata_edited" not in columns:
                conn.execute("ALTER TABLE songs ADD COLUMN metadata_edited INTEGER NOT NULL DEFAULT 0")
            # Limpieza de columnas/tablas de la antigua integración remota:
            # ya no se guardan enlaces ni elementos externos de playlists,
            # solo playlists locales con canciones de la biblioteca.
            conn.execute("DROP TABLE IF EXISTS spotify_playlist_items")



    def _invalidate_cache(self):
        self._cache.clear()

    # ------------------------------ Ajustes Fase 7 -----------------------
    def get_setting(self, key: str, default=None):
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return default if row is None else row["value"]

    def set_setting(self, key: str, value):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def get_folders(self) -> list[str]:
        with self.connect() as conn:
            return [row[0] for row in conn.execute("SELECT path FROM music_folders ORDER BY path")]

    def add_folder(self, path: str):
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO music_folders(path) VALUES (?)", (str(Path(path).resolve()),))

    def remove_folder(self, path: str):
        with self.connect() as conn:
            conn.execute("DELETE FROM music_folders WHERE path = ?", (str(Path(path).resolve()),))

    def upsert_song(self, song: Song):
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO songs(path,title,artist,album,genre,year,duration,track_number,file_size,modified_time,cover_data,lyrics,metadata_edited)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)
                   ON CONFLICT(path) DO UPDATE SET
                     title=CASE WHEN songs.metadata_edited=1 THEN songs.title ELSE excluded.title END,
                     artist=CASE WHEN songs.metadata_edited=1 THEN songs.artist ELSE excluded.artist END,
                     album=CASE WHEN songs.metadata_edited=1 THEN songs.album ELSE excluded.album END,
                     genre=CASE WHEN songs.metadata_edited=1 THEN songs.genre ELSE excluded.genre END,
                     year=CASE WHEN songs.metadata_edited=1 THEN songs.year ELSE excluded.year END,
                     duration=excluded.duration, track_number=excluded.track_number,
                     file_size=excluded.file_size, modified_time=excluded.modified_time,
                     cover_data=CASE WHEN songs.metadata_edited=1 THEN songs.cover_data ELSE excluded.cover_data END,
                     lyrics=CASE WHEN songs.metadata_edited=1 THEN songs.lyrics ELSE excluded.lyrics END,
                     metadata_edited=songs.metadata_edited""",
                (song.path, song.title, song.artist, song.album, song.genre, song.year,
                 song.duration, song.track_number, song.file_size, song.modified_time, song.cover_data, song.lyrics),
            )
        self._invalidate_cache()

    def update_song_metadata(self, song_id: int, *, title: str, artist: str, album: str, genre: str,
                             cover_data: bytes | None, lyrics: str):
        values = {
            "title": title.strip() or "Sin título",
            "artist": artist.strip() or "Artista desconocido",
            "album": album.strip() or "Álbum desconocido",
            "genre": genre.strip() or "Sin género",
            "cover_data": cover_data,
            "lyrics": lyrics.strip(),
        }
        with self.connect() as conn:
            conn.execute(
                """UPDATE songs
                   SET title=?, artist=?, album=?, genre=?, cover_data=?, lyrics=?, metadata_edited=1
                   WHERE id=?""",
                (values["title"], values["artist"], values["album"], values["genre"],
                 values["cover_data"], values["lyrics"], song_id),
            )
        self._invalidate_cache()

    def update_songs_field(self, song_ids, field: str, value: str):
        """Actualiza un único campo de metadatos en varias canciones."""
        allowed = {"artist", "album", "genre"}
        if field not in allowed:
            raise ValueError("Campo no permitido")
        ids = [int(x) for x in song_ids]
        if not ids:
            return
        clean = value.strip() or ({"artist": "Artista desconocido", "album": "Álbum desconocido", "genre": "Sin género"}[field])
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as conn:
            conn.execute(f"UPDATE songs SET {field}=?, metadata_edited=1 WHERE id IN ({placeholders})", [clean, *ids])
        self._invalidate_cache()

    def clear_songs_field(self, song_ids, field: str):
        """Limpia un campo de metadatos de varias canciones."""
        allowed = {"artist", "album", "genre"}
        if field not in allowed:
            raise ValueError("Campo no permitido")
        ids = [int(x) for x in song_ids]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        defaults = {"artist": "Artista desconocido", "album": "Álbum desconocido", "genre": "Sin género"}
        with self.connect() as conn:
            conn.execute(f"UPDATE songs SET {field}=?, metadata_edited=1 WHERE id IN ({placeholders})", [defaults[field], *ids])
        self._invalidate_cache()

    def clear_all_field(self, field: str):
        """Quita por completo un campo de agrupación de toda la biblioteca."""
        allowed = {"artist", "album", "genre"}
        if field not in allowed:
            raise ValueError("Campo no permitido")
        defaults = {"artist": "", "album": "", "genre": ""}
        with self.connect() as conn:
            conn.execute(f"UPDATE songs SET {field}=?, metadata_edited=1", (defaults[field],))
        self._invalidate_cache()

    def update_all_in_group(self, field: str, current_value: str, new_value: str):
        allowed = {"artist", "album", "genre"}
        if field not in allowed:
            raise ValueError("Campo no permitido")
        with self.connect() as conn:
            conn.execute(f"UPDATE songs SET {field}=?, metadata_edited=1 WHERE {field}=?", (new_value.strip(), current_value))
        self._invalidate_cache()

    def clear_all_in_group(self, field: str, current_value: str):
        allowed = {"artist", "album", "genre"}
        if field not in allowed:
            raise ValueError("Campo no permitido")
        defaults = {"artist": "", "album": "", "genre": ""}
        with self.connect() as conn:
            conn.execute(f"UPDATE songs SET {field}=?, metadata_edited=1 WHERE {field}=?", (defaults[field], current_value))
        self._invalidate_cache()

    def clear_song_metadata_override(self, song_id: int):
        with self.connect() as conn:
            conn.execute("UPDATE songs SET metadata_edited=0 WHERE id=?", (song_id,))

    def needs_update(self, path: str, size: int, mtime: float) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT file_size, modified_time FROM songs WHERE path=?", (path,)).fetchone()
            return row is None or row["file_size"] != size or abs(row["modified_time"] - mtime) > 0.0001

    def remove_paths(self, paths: Iterable[str]):
        paths = list(paths)
        if not paths:
            return
        with self.connect() as conn:
            placeholders = ",".join("?" for _ in paths)
            conn.execute(f"DELETE FROM songs WHERE path IN ({placeholders})", paths)
        self._invalidate_cache()

    def delete_song(self, song_id: int) -> str | None:
        """Borra la canción de la base de datos y su archivo del disco.
        Devuelve el path que tenía, o None si no existía."""
        with self.connect() as conn:
            row = conn.execute("SELECT path FROM songs WHERE id=?", (song_id,)).fetchone()
            if row is None:
                return None
            path = row["path"]
            conn.execute("DELETE FROM songs WHERE id=?", (song_id,))
        self._invalidate_cache()
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
        return path

    def list_songs(self, query: str = "") -> list[sqlite3.Row]:
        with self.connect() as conn:
            if query:
                like = f"%{query}%"
                return conn.execute(
                    """SELECT s.*, EXISTS(SELECT 1 FROM favorites f WHERE f.song_id=s.id) AS is_favorite
                       FROM songs s
                       WHERE s.title LIKE ? OR s.artist LIKE ? OR s.album LIKE ? OR s.genre LIKE ?
                       ORDER BY s.artist COLLATE NOCASE, s.album COLLATE NOCASE, s.track_number, s.title COLLATE NOCASE""",
                    (like, like, like, like),
                ).fetchall()
            return conn.execute(
                """SELECT s.*, EXISTS(SELECT 1 FROM favorites f WHERE f.song_id=s.id) AS is_favorite
                   FROM songs s ORDER BY s.artist COLLATE NOCASE, s.album COLLATE NOCASE, s.track_number, s.title COLLATE NOCASE"""
            ).fetchall()

    def get_song_by_path(self, path: str):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM songs WHERE path=?", (str(Path(path).resolve()),)).fetchone()

    def get_song(self, song_id: int):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()

    def list_song_choices(self, query: str = "") -> list[sqlite3.Row]:
        """Lista ligera para selectores de canciones: no carga carátulas ni blobs."""
        with self.connect() as conn:
            if query:
                like=f"%{query}%"
                return conn.execute("SELECT id,title,artist,album,genre FROM songs WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? OR genre LIKE ? ORDER BY artist COLLATE NOCASE, title COLLATE NOCASE", (like,like,like,like)).fetchall()
            return conn.execute("SELECT id,title,artist,album,genre FROM songs ORDER BY artist COLLATE NOCASE, title COLLATE NOCASE").fetchall()

    def count_songs(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]

    # ------------------------------ Fase 4: agrupaciones -----------------
    def list_albums(self, query: str = "") -> list[sqlite3.Row]:
        key = ("albums", query)
        if key in self._cache: return self._cache[key]
        sql = """SELECT album, artist, COUNT(*) AS song_count,
                         MAX(cover_data) AS cover_data,
                         MIN(id) AS first_song_id
                  FROM songs"""
        params = []
        if query:
            sql += " WHERE album LIKE ? OR artist LIKE ?"
            like = f"%{query}%"
            params = [like, like]
        sql += " GROUP BY album, artist ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        self._cache[key] = rows
        return rows

    def list_album_songs(self, album: str, artist: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT s.*, EXISTS(SELECT 1 FROM favorites f WHERE f.song_id=s.id) AS is_favorite
                   FROM songs s WHERE s.album=? AND s.artist=?
                   ORDER BY s.track_number, s.title COLLATE NOCASE""", (album, artist)
            ).fetchall()

    def list_artists(self, query: str = "") -> list[sqlite3.Row]:
        key = ("artists", query)
        if key in self._cache: return self._cache[key]
        sql = "SELECT artist, COUNT(*) AS song_count, COUNT(DISTINCT album) AS album_count FROM songs"
        params = []
        if query:
            sql += " WHERE artist LIKE ?"
            params = [f"%{query}%"]
        sql += " GROUP BY artist ORDER BY artist COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        self._cache[key] = rows
        return rows

    def list_artist_songs(self, artist: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT s.*, EXISTS(SELECT 1 FROM favorites f WHERE f.song_id=s.id) AS is_favorite
                   FROM songs s WHERE s.artist=?
                   ORDER BY s.album COLLATE NOCASE, s.track_number, s.title COLLATE NOCASE""", (artist,)
            ).fetchall()

    def list_genres(self, query: str = "") -> list[sqlite3.Row]:
        key = ("genres", query)
        if key in self._cache: return self._cache[key]
        sql = "SELECT genre, COUNT(*) AS song_count FROM songs WHERE TRIM(genre) <> ''"
        params = []
        if query:
            sql += " AND genre LIKE ?"
            params = [f"%{query}%"]
        sql += " GROUP BY genre ORDER BY genre COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        self._cache[key] = rows
        return rows

    def list_genre_songs(self, genre: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT s.*, EXISTS(SELECT 1 FROM favorites f WHERE f.song_id=s.id) AS is_favorite
                   FROM songs s WHERE s.genre=?
                   ORDER BY s.artist COLLATE NOCASE, s.album COLLATE NOCASE, s.track_number""", (genre,)
            ).fetchall()

    # ------------------------------ Favoritos ----------------------------
    def is_favorite(self, song_id: int) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM favorites WHERE song_id=?", (song_id,)).fetchone() is not None

    def toggle_favorite(self, song_id: int) -> bool:
        with self.connect() as conn:
            if conn.execute("SELECT 1 FROM favorites WHERE song_id=?", (song_id,)).fetchone():
                conn.execute("DELETE FROM favorites WHERE song_id=?", (song_id,))
                return False
            conn.execute("INSERT OR IGNORE INTO favorites(song_id) VALUES (?)", (song_id,))
            return True

    def list_favorites(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT s.* FROM songs s JOIN favorites f ON f.song_id=s.id
                   ORDER BY f.created_at DESC, s.title COLLATE NOCASE"""
            ).fetchall()

    # ------------------------------ Playlists ----------------------------
    def create_playlist(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("El nombre de la playlist no puede estar vacío")
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO playlists(name) VALUES (?)", (name,))
            return int(cur.lastrowid)

    def rename_playlist(self, playlist_id: int, name: str):
        name = name.strip()
        if not name:
            raise ValueError("El nombre de la playlist no puede estar vacío")
        with self.connect() as conn:
            conn.execute("UPDATE playlists SET name=? WHERE id=?", (name, playlist_id))

    def delete_playlist(self, playlist_id: int):
        with self.connect() as conn:
            conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))

    def list_playlists(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT p.id, p.name, COUNT(ps.song_id) AS song_count
                   FROM playlists p LEFT JOIN playlist_songs ps ON ps.playlist_id=p.id
                   GROUP BY p.id ORDER BY p.name COLLATE NOCASE"""
            ).fetchall()

    def add_to_playlist(self, playlist_id: int, song_id: int):
        with self.connect() as conn:
            pos = conn.execute("SELECT COALESCE(MAX(position), -1)+1 FROM playlist_songs WHERE playlist_id=?", (playlist_id,)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO playlist_songs(playlist_id,song_id,position) VALUES (?,?,?)", (playlist_id, song_id, pos))

    def remove_from_playlist(self, playlist_id: int, song_id: int):
        with self.connect() as conn:
            conn.execute("DELETE FROM playlist_songs WHERE playlist_id=? AND song_id=?", (playlist_id, song_id))

    def list_playlist_songs(self, playlist_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT s.* FROM playlist_songs ps JOIN songs s ON s.id=ps.song_id
                   WHERE ps.playlist_id=? ORDER BY ps.position""", (playlist_id,)
            ).fetchall()

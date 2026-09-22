"""Lectura segura de metadatos y carátulas con Mutagen."""
from pathlib import Path

from mutagen import File

from app.models.song import Song
from app.utils.logger import get_logger

logger = get_logger(__name__)
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".opus", ".m4a", ".aac"}


def _first(tags, *keys, default=""):
    if not tags:
        return default
    for key in keys:
        try:
            value = tags.get(key)
        except Exception:
            value = None
        if value is not None:
            if isinstance(value, (list, tuple)):
                value = value[0] if value else default
            text = str(value).strip()
            if text:
                return text
    return default


def _track_number(tags) -> int:
    raw = _first(tags, "tracknumber", "trkn", default="0")
    try:
        return int(str(raw).split("/")[0])
    except (ValueError, TypeError):
        return 0


def _year(tags) -> str:
    return _first(tags, "date", "year", "originaldate", "TDRC", "©day")[:10]


def _lyrics(tags) -> str:
    if not tags:
        return ""
    for key in ("USLT::eng", "USLT", "SYLT::eng", "SYLT", "lyrics", "LYRICS", "©lyr"):
        try:
            value = tags.get(key)
            if value is None:
                continue
            if hasattr(value, "text"):
                value = value.text
            if isinstance(value, (list, tuple)):
                value = value[0] if value else ""
            text = str(value).strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def _cover_data(audio) -> bytes | None:
    if audio is None:
        return None
    try:
        # ID3 / MP3
        for apic in getattr(audio, "tags", {}).values():
            if hasattr(apic, "data") and hasattr(apic, "mime"):
                return bytes(apic.data)
    except Exception:
        pass

    # FLAC / OGG / Opus and formats exposing pictures directly.
    try:
        pictures = getattr(audio, "pictures", None)
        if pictures:
            return bytes(pictures[0].data)
    except Exception:
        pass

    # MP4/M4A cover: covr entries are byte-like objects.
    try:
        covr = audio.tags.get("covr") if audio.tags else None
        if covr:
            return bytes(covr[0])
    except Exception:
        pass
    return None


def read_song(path: Path) -> Song | None:
    """Lee un archivo de audio. Un archivo inválido se omite sin tumbar el escaneo."""
    try:
        stat = path.stat()
        audio = File(path, easy=False)
        if audio is None:
            logger.warning("Mutagen no pudo leer: %s", path)
            return None

        tags = audio.tags
        info = audio.info
        title = _first(tags, "title", "TIT2", "©nam", default=path.stem)
        artist = _first(tags, "artist", "TPE1", "©ART", default="Artista desconocido")
        album = _first(tags, "album", "TALB", "©alb", default="Álbum desconocido")
        genre = _first(tags, "genre", "TCON", "©gen", default="Sin género")
        return Song(
            path=str(path.resolve()),
            title=title,
            artist=artist,
            album=album,
            genre=genre,
            year=_year(tags),
            duration=float(getattr(info, "length", 0.0) or 0.0),
            track_number=_track_number(tags),
            file_size=stat.st_size,
            modified_time=stat.st_mtime,
            cover_data=_cover_data(audio),
            lyrics=_lyrics(tags),
        )
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("No se pudo leer %s: %s", path, exc)
        return None
    except Exception as exc:  # Mutagen puede lanzar errores específicos por codec.
        logger.warning("Archivo omitido %s: %s", path, exc)
        return None

"""Búsqueda y descarga de audio de YouTube mediante yt-dlp.

La interfaz llama estas funciones desde un hilo secundario. El módulo no
ejecuta comandos construidos a partir de nombres de archivos: yt-dlp recibe
las opciones como argumentos Python.
"""
from pathlib import Path
import re
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1

from app.database.db import DB_DIR

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# El archivo de cookies se guarda desde Ajustes → Fuentes externas (formato
# Netscape, exportado con una extensión del navegador). Vive en la misma
# carpeta de datos que la base de datos de la biblioteca, no en el código.
_COOKIES_FILE = DB_DIR / "cookies.txt"


def _base_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        # Reintentos y timeouts razonables: YouTube y las redes caseras
        # cortan conexiones ocasionalmente, sin esto un solo fallo de red
        # tumbaba toda la descarga.
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        # "android_sdkless" es el cliente por defecto en algunas versiones
        # de yt-dlp y desde 2026 YouTube le exige un PO Token que yt-dlp no
        # puede generar solo, causando HTTP 403 en el audio. Se excluye a
        # propósito y se usa la selección de clientes por defecto de
        # yt-dlp (que ya evita los que requieren PO Token) como respaldo.
        "extractor_args": {"youtube": {"player_client": ["default", "-android_sdkless"]}},
    }
    if _COOKIES_FILE.is_file():
        opts["cookiefile"] = str(_COOKIES_FILE)
    return opts


_PO_TOKEN_HINT = (
    "YouTube está pidiendo una verificación extra (PO Token) para este video. "
    "Prueba: 1) actualizar las cookies de YouTube en Ajustes, exportándolas de "
    "nuevo desde el navegador con sesión iniciada, o 2) intentar con otra "
    "canción/video, ya que no todos lo piden."
)


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    lower = text.lower()
    if "po token" in lower or "po_token" in lower:
        return _PO_TOKEN_HINT
    if "403" in text:
        return (
            "YouTube rechazó la descarga (403 Forbidden). Suele arreglarse "
            "solo al actualizar yt-dlp a la última versión, o probando de "
            "nuevo en unos minutos. " + _PO_TOKEN_HINT
        )
    if "sign in to confirm" in lower or "not a bot" in lower:
        return (
            "YouTube está pidiendo confirmar que no eres un robot. Exporta "
            "tus cookies de YouTube (con sesión iniciada) desde Ajustes y "
            "vuelve a intentarlo."
        )
    return text


def save_youtube_cookies(cookies_text: str) -> None:
    """Guarda el contenido pegado en Ajustes como cookies.txt (formato Netscape)."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    cookies_text = (cookies_text or "").strip()
    if not cookies_text:
        _COOKIES_FILE.unlink(missing_ok=True)
        return
    _COOKIES_FILE.write_text(cookies_text + "\n", encoding="utf-8")


def has_youtube_cookies() -> bool:
    return _COOKIES_FILE.is_file()


def _safe_name(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", value or "")
    value = re.sub(r"\s+", " ", value).strip().strip(".")
    return value or "Sin título"

def search_youtube(title: str, artist: str, limit: int = 6) -> list[dict]:
    if yt_dlp is None:
        raise RuntimeError("Falta yt-dlp. Instálalo con pip o desde requirements.txt.")
    query = " ".join(x.strip() for x in (title, artist) if x.strip())
    if not query:
        return []
    opts = {
        **_base_opts(),
        "skip_download": True,
        "extract_flat": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        except Exception as exc:
            raise RuntimeError(_friendly_error(exc)) from exc
    entries = (info or {}).get("entries") or []
    results = []
    for entry in entries:
        if not entry:
            continue
        results.append({
            "id": entry.get("id"),
            "title": entry.get("title") or title,
            "channel": entry.get("channel") or entry.get("uploader") or artist,
            "duration": entry.get("duration") or 0,
            "url": entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get("id") else ""),
            "thumbnail": entry.get("thumbnail") or "",
        })
    return results

def download_youtube(result: dict, destination: str | Path, progress=None) -> Path:
    if yt_dlp is None:
        raise RuntimeError("Falta yt-dlp. Instálalo con pip o desde requirements.txt.")
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    title = _safe_name(result.get("title") or "Sin título")
    artist = _safe_name(result.get("channel") or "Artista desconocido")
    output_template = str(destination / f"{title} - {artist}.%(ext)s")

    def hook(data):
        if progress:
            try:
                progress(data)
            except Exception:
                pass

    opts = {
        **_base_opts(),
        # A propósito en False: _base_opts() trae ignoreerrors=True pensado
        # para búsquedas con varios resultados (uno roto no debe tumbar los
        # demás). Para descargar UN video puntual, si algo falla debe
        # avisar con una excepción real, no "saltárselo" en silencio y
        # dejar la carpeta sin el MP3 sin que el usuario se entere por qué.
        "ignoreerrors": False,
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "writethumbnail": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            code = ydl.download([result["url"]])
        except Exception as exc:
            raise RuntimeError(_friendly_error(exc)) from exc
        if code:
            # download() devuelve distinto de 0 si algo salió mal aunque no
            # haya lanzado excepción (puede pasar con ciertos post-procesos).
            raise RuntimeError(
                "La descarga de YouTube no terminó correctamente (código "
                f"{code}). Prueba de nuevo o con otro resultado de búsqueda."
            )
    expected = destination / f"{title} - {artist}.mp3"
    if expected.exists():
        return expected
    # Buscar el MP3 generado cuando yt-dlp/ffmpeg haya normalizado el nombre.
    matches = sorted(destination.glob(f"{title} - *.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise RuntimeError(
            "La descarga terminó pero no se encontró el MP3 resultante. "
            "Esto casi siempre pasa cuando falta ffmpeg en el sistema "
            "(necesario para convertir el audio a MP3): instálalo con el "
            "gestor de paquetes de tu distro (ej. sudo apt install ffmpeg) "
            "y vuelve a intentarlo."
        )
    return matches[0]


def apply_user_metadata(path: str | Path, title: str, artist: str) -> None:
    """Hace que nombre y artista coincidan con lo que pidió el usuario."""
    path = Path(path)
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.setall("TIT2", [TIT2(encoding=3, text=[title.strip() or path.stem])])
    tags.setall("TPE1", [TPE1(encoding=3, text=[artist.strip() or "Artista desconocido"])])
    tags.save(path)

"""Búsqueda de letras en Internet, sin bloquear la interfaz GTK.

Fuente 1: lyrics.ovh (gratis, sin key, pero catálogo limitado).
Fuente 2: LRCLIB, con búsqueda difusa (más tolerante a variaciones del título).
Fuente 3: Genius (catálogo mucho más completo, incluida música urbana/latina),
          como último respaldo. El token se configura desde Ajustes →
          Fuentes externas (no requiere editar ningún archivo).
"""
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import html as html_lib
import json
import re

UA_NAVEGADOR = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

GENIUS_SEARCH_API = "https://api.genius.com/search"

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_DIV_ANY_RE = re.compile(r"<div\b|</div\s*>", re.IGNORECASE)
_LYRICS_CONTAINER_RE = re.compile(r'<div[^>]*data-lyrics-container="true"[^>]*>')


def _get_json(url, headers=None):
    req = Request(url, headers={"User-Agent": UA_NAVEGADOR, "Accept": "application/json", **(headers or {})})
    with urlopen(req, timeout=8) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _get_html(url):
    req = Request(url, headers={
        "User-Agent": UA_NAVEGADOR,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })
    with urlopen(req, timeout=8) as response:
        return response.read().decode("utf-8", errors="replace")


def _html_a_texto(fragmento: str) -> str:
    fragmento = _BR_RE.sub("\n", fragmento)
    fragmento = _TAG_RE.sub("", fragmento)
    return html_lib.unescape(fragmento)


def _extraer_letra_genius(pagina_html: str) -> str:
    """Extrae el texto de los <div data-lyrics-container="true">...</div>,
    respetando el anidamiento de <div> (equivalente a lo que hace cheerio
    en la versión de WhatsApp, pero sin depender de una librería HTML)."""
    partes = []
    for match in _LYRICS_CONTAINER_RE.finditer(pagina_html):
        inicio = match.end()
        profundidad = 1
        fin = len(pagina_html)
        for tag in _DIV_ANY_RE.finditer(pagina_html, inicio):
            if tag.group(0).lower().startswith("<div"):
                profundidad += 1
            else:
                profundidad -= 1
                if profundidad == 0:
                    fin = tag.start()
                    break
        partes.append(_html_a_texto(pagina_html[inicio:fin]).strip())
    return "\n\n".join(p for p in partes if p).strip()


def _buscar_en_genius(title: str, artist: str, token: str) -> str:
    if not token:
        raise RuntimeError(
            "genius: no hay token configurado (Ajustes → Fuentes externas)"
        )
    query = f"{artist} {title}".strip()
    try:
        data = _get_json(
            f"{GENIUS_SEARCH_API}?q={quote(query, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
        )
    except HTTPError as exc:
        raise RuntimeError(f"genius: token inválido o revocado (HTTP {exc.code})") from exc
    except URLError as exc:
        raise RuntimeError(f"genius: red — {exc.reason}") from exc

    hits = ((data or {}).get("response") or {}).get("hits") or []
    hit = next((h for h in hits if h.get("type") == "song"), None)
    if not hit:
        raise RuntimeError("genius: sin resultados para esa búsqueda")

    url = (hit.get("result") or {}).get("url")
    if not url:
        raise RuntimeError("genius: resultado sin URL de letra")

    try:
        pagina = _get_html(url)
    except HTTPError as exc:
        raise RuntimeError(f"genius: bloqueo anti-bot al abrir la página (HTTP {exc.code})") from exc
    except URLError as exc:
        raise RuntimeError(f"genius: red al abrir la página — {exc.reason}") from exc

    letra = _extraer_letra_genius(pagina)
    if not letra:
        raise RuntimeError("genius: no se pudo extraer la letra de la página")
    return letra


def search_lyrics(title: str, artist: str, genius_token: str = "") -> str:
    title = title.strip()
    artist = artist.strip()
    if not title or not artist:
        return ""

    errores = []

    # Fuente 1: lyrics.ovh
    try:
        data = _get_json(f"https://api.lyrics.ovh/v1/{quote(artist, safe='')}/{quote(title, safe='')}")
        lyrics = str(data.get("lyrics") or "").strip()
        if lyrics:
            return lyrics
        errores.append("lyrics.ovh: sin letra en la respuesta")
    except HTTPError as exc:
        errores.append(f"lyrics.ovh: HTTP {exc.code}")
    except URLError as exc:
        errores.append(f"lyrics.ovh: red — {exc.reason}")
    except Exception as exc:
        errores.append(f"lyrics.ovh: {exc}")

    # Fuente 2: LRCLIB (búsqueda difusa)
    try:
        resultados = _get_json(f"https://lrclib.net/api/search?q={quote(f'{artist} {title}', safe='')}")
        if isinstance(resultados, list) and resultados:
            mejor = resultados[0]
            lyrics = str(mejor.get("plainLyrics") or mejor.get("syncedLyrics") or "").strip()
            if lyrics:
                return lyrics
            errores.append("lrclib: resultado sin letra")
        else:
            errores.append("lrclib: sin resultados")
    except HTTPError as exc:
        errores.append(f"lrclib: HTTP {exc.code}")
    except URLError as exc:
        errores.append(f"lrclib: red — {exc.reason}")
    except Exception as exc:
        errores.append(f"lrclib: {exc}")

    # Fuente 3: Genius (respaldo, catálogo más amplio)
    try:
        return _buscar_en_genius(title, artist, genius_token)
    except Exception as exc:
        errores.append(str(exc))

    raise RuntimeError("; ".join(errores) if errores else "Sin resultados")

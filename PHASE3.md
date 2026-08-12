# Vorem Music — Fase 3

Esta versión integra la biblioteca musical real sobre la base de la Fase 1/2.

## Incluye

- SQLite persistente en `~/.local/share/vorem-music/library.db`.
- Carpetas de música persistentes.
- Escaneo recursivo de MP3, FLAC, WAV, OGG, Opus, M4A y AAC.
- Escaneo incremental por tamaño y fecha de modificación.
- Detección de archivos eliminados.
- Mutagen para título, artista, álbum, género, año, duración y número de pista.
- Extracción de carátulas embebidas y almacenamiento en SQLite.
- Archivos corruptos o incompatibles se omiten y quedan registrados en el log.
- Escaneo fuera del hilo de GTK para no congelar la interfaz.
- Página Biblioteca para añadir/quitar carpetas y lanzar escaneos.
- Página Canciones conectada a SQLite.
- Reproducción de una canción de la biblioteca con el motor GStreamer existente.
- La mini barra muestra metadatos y carátula cuando están disponibles.

## Instalación en Fedora

```bash
chmod +x install.sh
./install.sh
source venv/bin/activate
python3 main.py
```

## Base de datos

La base se crea automáticamente. No hace falta crear tablas manualmente.

## Comprobación rápida

```bash
python3 -m compileall -q .
pytest -q
```

Si ya tienes una instalación anterior de Vorem Music, no hace falta borrar la base de datos: el esquema de esta fase se crea de forma compatible con una base nueva.

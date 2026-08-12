<p align="center">
  <img src="data/icons/vorem-music.png" width="140" alt="Logo de Deluxevor Music">
</p>

<h1 align="center">Deluxevor Music</h1>

<p align="center">
  Reproductor de música local moderno y ligero para Linux, hecho con GTK4 + libadwaita.<br>
  Totalmente gratuito. By <b>vorem</b>.
</p>

---

## ✨ Características

- Reproducción de tu biblioteca local (mp3, flac, wav, ogg, opus, m4a, aac).
- Álbumes, artistas, géneros, favoritos y playlists.
- Descarga de canciones y letras (usa tu propia API key de Genius y cookies de YouTube, configurables desde Ajustes).
- Visualizador de espectro, temas de color, animaciones configurables.
- Interfaz nativa GTK4/libadwaita, ligera y rápida.

## 📦 Requisitos

- Linux (Ubuntu/Debian, Fedora, Arch/Manjaro u openSUSE — el instalador detecta tu distro automáticamente).
- Python 3.10 o superior.
- Conexión a internet solo la primera vez, para instalar dependencias.

## 🚀 Instalación

```bash
git clone https://github.com/<voremoficial-max>/deluxevor-music.git
cd deluxevor-music
chmod +x install.sh
./install.sh
```

El script `install.sh`:

1. Detecta tu distribución (apt, dnf, pacman o zypper) e instala GTK4, libadwaita, GStreamer y ffmpeg.
2. Crea un entorno virtual de Python (`venv/`) e instala las dependencias (`yt-dlp`, `Pillow`, `mutagen`).
3. Instala el icono de la app en tu sistema.
4. Crea un acceso directo en tu menú de aplicaciones — busca **"Deluxevor Music"** y ábrelo como cualquier otro programa.

Te pedirá tu contraseña de administrador (`sudo`) solo para instalar los paquetes del sistema.

### Ejecutar manualmente (sin acceso directo)

```bash
cd deluxevor-music
source venv/bin/activate
python3 main.py
```

## ⚙️ Configuración (API key y cookies)

Para descargar canciones y letras necesitas configurar tu propia API key de Genius y, opcionalmente, cookies de YouTube. Las instrucciones detalladas están dentro de la app, en **Ajustes**. Estos datos se guardan localmente en `~/.local/share/vorem-music/` en tu equipo — nunca se suben a este repositorio ni se comparten con nadie.

## 🗑️ Desinstalar

```bash
rm -rf ~/.local/share/icons/hicolor/*/apps/vorem-music.png
rm -f ~/.local/share/applications/vorem.desktop
rm -rf ~/.local/share/vorem-music   # borra también tu biblioteca, cookies y ajustes guardados
rm -rf deluxevor-music              # la carpeta donde clonaste el repo
```

## 💜 Apoya el proyecto

Sígueme en [TikTok @vorem_of](https://www.tiktok.com/@vorem_of) y únete al [grupo de WhatsApp](https://chat.whatsapp.com/LISZACfu4Xo0irilkwofmN?s=cl&p=a&mlu=4) para dudas, sugerencias o reportar errores.

## 📄 Licencia

Todos los derechos reservados — ver [LICENSE](./LICENSE). El código es visible con fines de portafolio y transparencia, pero no está autorizado su reuso, copia o redistribución sin permiso del autor.

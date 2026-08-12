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

- Linux (Ubuntu/Debian, Fedora Workstation o Atomic/Silverblue/Kinoite, Arch/Manjaro, openSUSE — el instalador detecta tu sistema automáticamente, incluyendo distros atómicas/inmutables).
- Python 3.10 o superior.
- Conexión a internet solo la primera vez, para instalar dependencias.

## 🚀 Instalación

```bash
git clone https://github.com/voremoficial-max/deluxevor-music.git
cd deluxevor-music
chmod +x install.sh
./install.sh
```

El script `install.sh`:

1. Detecta automáticamente tu tipo de sistema:
   - **Distro tradicional** (Ubuntu/Debian, Fedora Workstation, Arch/Manjaro, openSUSE): instala GTK4, libadwaita, GStreamer y ffmpeg con tu gestor de paquetes (apt/dnf/pacman/zypper).
   - **Distro atómica/inmutable** (Fedora Silverblue, Fedora Kinoite, uBlue, openSUSE Aeon/Kalpa): como estos sistemas no permiten instalar paquetes directamente, el script usa [Distrobox](https://distrobox.it/) para crear un pequeño contenedor Fedora (sin tocar tu sistema base ni requerir reinicio) e instala todo ahí dentro.
2. Crea un entorno virtual de Python e instala las dependencias (`yt-dlp`, `Pillow`, `mutagen`).
3. Instala el icono de la app en tu sistema.
4. Crea un acceso directo en tu menú de aplicaciones — busca **"Deluxevor Music"** y ábrelo como cualquier otro programa (en sistemas atómicos, se abre automáticamente a través del contenedor, sin que notes la diferencia).

Te pedirá tu contraseña de administrador (`sudo`) solo para instalar los paquetes del sistema (o, en sistemas atómicos, dentro del contenedor).

### Ejecutar manualmente (sin acceso directo)

```bash
cd deluxevor-music
source venv/bin/activate
python3 main.py
```

## ⚙️ Configuración (API key y cookies)

Para descargar canciones y letras necesitas configurar tu propia API key de Genius y, opcionalmente, cookies de YouTube. Las instrucciones detalladas están dentro de la app, en **Ajustes**. Estos datos se guardan localmente en `~/.local/share/vorem-music/` en tu equipo.

## 🗑️ Desinstalar

```bash
rm -rf ~/.local/share/icons/hicolor/*/apps/vorem-music.png
rm -f ~/.local/share/applications/vorem.desktop
rm -rf ~/.local/share/vorem-music   # borra también tu biblioteca, cookies y ajustes guardados
rm -rf deluxevor-music              # la carpeta donde clonaste el repo
```

Si instalaste en un sistema atómico/inmutable (Fedora Silverblue/Kinoite, etc.), también puedes borrar el contenedor de Distrobox:

```bash
distrobox rm deluxevor-music-box
```

## 💜 Apoya el proyecto

Sígueme en [TikTok @vorem_of](https://www.tiktok.com/@vorem_of) y únete al [grupo de WhatsApp](https://chat.whatsapp.com/GDtzosa0fEIIBrSDchQruB) para dudas, sugerencias o reportar errores.

## 📄 Licencia

Todos los derechos reservados — ver [LICENSE](./LICENSE). El código es visible con fines de portafolio y transparencia, pero no está autorizado su reuso, copia o redistribución sin permiso del autor.

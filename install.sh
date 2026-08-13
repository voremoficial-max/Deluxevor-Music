#!/usr/bin/env bash
set -euo pipefail

# Se ubica a sí mismo para poder ejecutarse desde cualquier carpeta
# (doble clic, acceso directo del menú, o "bash install.sh" desde otro sitio).
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "== Instalando Deluxevor Music =="
echo "Carpeta de la app: $APP_DIR"

BOX_NAME="deluxevor-music-box"

# ---------------------------------------------------------------------------
# Paquetes por gestor de paquetes (se usan tanto en instalación normal
# como dentro del contenedor Distrobox en sistemas atómicos/inmutables).
# ---------------------------------------------------------------------------
install_debian() {
    sudo apt-get update
    sudo apt-get install -y \
        python3 python3-pip python3-venv python3-gi python3-gi-cairo \
        gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gstreamer-1.0 \
        libgtk-4-1 libadwaita-1-0 \
        gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav \
        ffmpeg
}

install_fedora() {
    sudo dnf install -y \
        python3 python3-pip python3-gobject \
        gtk4 libadwaita \
        gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good \
        gstreamer1-plugins-bad-free gstreamer1-plugins-ugly-free \
        gstreamer1-plugin-openh264 python3-gstreamer1 \
        ffmpeg
}

install_arch() {
    sudo pacman -Sy --needed --noconfirm \
        python python-pip python-gobject \
        gtk4 libadwaita \
        gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad \
        gst-plugins-ugly gst-libav \
        ffmpeg
}

install_opensuse() {
    sudo zypper install -y \
        python3 python3-pip python3-gobject \
        typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 libadwaita-1-0 \
        gstreamer gstreamer-plugins-base gstreamer-plugins-good \
        gstreamer-plugins-bad gstreamer-plugins-ugly \
        ffmpeg
}

# ---------------------------------------------------------------------------
# Instala el icono y crea el acceso directo del menú. "$1" es el comando
# a usar como Exec= (distinto si se corre nativo o dentro de Distrobox).
# ---------------------------------------------------------------------------
install_icon_and_shortcut() {
    exec_command="$1"

    echo ""
    echo "Instalando el icono de la app (todos los tamaños)..."
    ICON_BASE="$APP_DIR/data/icons/hicolor"
    for size_dir in "$ICON_BASE"/*/apps; do
        size_name="$(basename "$(dirname "$size_dir")")"
        dest="$HOME/.local/share/icons/hicolor/$size_name/apps"
        mkdir -p "$dest"
        cp "$size_dir/vorem-music.png" "$dest/vorem-music.png"
    done

    if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
        gtk4-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true
    elif command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true
    fi

    echo "Creando acceso directo en el menú de aplicaciones..."
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"

    cat > "$DESKTOP_DIR/vorem.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Deluxevor Music
Comment=Reproductor de música local moderno y ligero
Exec=$exec_command
Icon=vorem-music
Path=$APP_DIR
Terminal=false
Categories=Audio;Music;Player;GTK;
StartupNotify=true
EOF

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" || true
    fi
}

# ---------------------------------------------------------------------------
# Ruta A: sistema Linux tradicional (Ubuntu, Debian, Fedora Workstation,
# Arch, openSUSE...) donde dnf/apt/pacman/zypper pueden instalar al sistema.
# ---------------------------------------------------------------------------
install_native() {
    echo ""
    echo "[1/3] Detectando tu distribución e instalando paquetes del sistema..."

    if command -v apt-get >/dev/null 2>&1; then
        echo "Detectado: Debian/Ubuntu/Mint (apt)"
        install_debian
    elif command -v dnf >/dev/null 2>&1; then
        echo "Detectado: Fedora/RHEL/CentOS (dnf)"
        install_fedora
    elif command -v pacman >/dev/null 2>&1; then
        echo "Detectado: Arch/Manjaro/EndeavourOS (pacman)"
        install_arch
    elif command -v zypper >/dev/null 2>&1; then
        echo "Detectado: openSUSE (zypper)"
        install_opensuse
    else
        echo "⚠️  No reconocí tu gestor de paquetes automáticamente."
        echo "Instala manualmente estos componentes y vuelve a correr este script:"
        echo "  - Python 3 + pip + venv"
        echo "  - Bindings de GObject Introspection para Python (python3-gi / python-gobject)"
        echo "  - GTK4 y libadwaita (con sus typelibs/GIR)"
        echo "  - GStreamer 1.0 (base, good, bad, ugly) + bindings de Python"
        echo "  - ffmpeg"
        exit 1
    fi

    echo ""
    echo "[2/3] Creando entorno virtual en ./venv (con acceso a paquetes del sistema)..."
    python3 -m venv --system-site-packages venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt

    echo ""
    echo "[3/3] Instalando icono y acceso directo..."
    install_icon_and_shortcut "$APP_DIR/venv/bin/python3 $APP_DIR/main.py"

    echo ""
    echo "✅ Instalación completa."
    echo "Busca 'Deluxevor Music' en tu menú de aplicaciones."
    echo "También puedes ejecutarlo manualmente con:"
    echo "  cd \"$APP_DIR\" && source venv/bin/activate && python3 main.py"
}

# ---------------------------------------------------------------------------
# Ruta B: sistemas atómicos/inmutables (Fedora Silverblue/Kinoite/uBlue,
# openSUSE Aeon/Kalpa, etc). Aquí NO existe dnf/zypper de sistema (o no se
# debe usar), así que se crea un contenedor Distrobox con Fedora, se instala
# todo ahí dentro (sin tocar el sistema base) y se exporta la app al menú
# como si fuera nativa.
# ---------------------------------------------------------------------------
install_atomic() {
    echo ""
    echo "Detecté un sistema Linux atómico/inmutable (ej. Fedora Silverblue/Kinoite,"
    echo "openSUSE Aeon/Kalpa). El instalador tradicional (dnf/rpm-ostree) no es"
    echo "apto aquí, así que usaré Distrobox para crear un pequeño contenedor Fedora"
    echo "sin modificar tu sistema base ni requerir reinicio."

    if ! command -v podman >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
        echo ""
        echo "⚠️  No encontré podman ni docker, que Distrobox necesita para funcionar."
        echo "En Fedora Silverblue/Kinoite viene instalado por defecto; si no está,"
        echo "instálalo con: rpm-ostree install podman   (y reinicia), y luego vuelve"
        echo "a correr este script."
        exit 1
    fi

    if ! command -v distrobox >/dev/null 2>&1; then
        echo ""
        echo "[1/4] Instalando Distrobox en tu carpeta de usuario (no requiere root ni reinicio)..."
        curl -fsSL https://raw.githubusercontent.com/89luca89/distrobox/main/install | sh -s -- --prefix "$HOME/.local"
        export PATH="$HOME/.local/bin:$PATH"
        if ! command -v distrobox >/dev/null 2>&1; then
            echo "⚠️  Distrobox se instaló en $HOME/.local/bin pero esa ruta no está en tu PATH."
            echo "Agrega esta línea a tu ~/.bashrc (o ~/.zshrc) y abre una terminal nueva:"
            echo '  export PATH="$HOME/.local/bin:$PATH"'
            echo "Luego vuelve a correr ./install.sh"
            exit 1
        fi
    else
        echo ""
        echo "[1/4] Distrobox ya está instalado, continuando..."
    fi

    echo ""
    echo "[2/4] Creando el contenedor '$BOX_NAME' (la primera vez descarga la imagen de Fedora, puede tardar)..."
    if ! distrobox list 2>/dev/null | grep -q "$BOX_NAME"; then
        distrobox create --yes --name "$BOX_NAME" --image fedora:latest
    fi

    echo ""
    echo "[3/4] Instalando dependencias dentro del contenedor..."
    distrobox enter "$BOX_NAME" -- sudo dnf install -y \
        python3 python3-pip python3-gobject \
        gtk4 libadwaita \
        gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good \
        gstreamer1-plugins-bad-free gstreamer1-plugins-ugly-free \
        gstreamer1-plugin-openh264 python3-gstreamer1 \
        ffmpeg

    echo "Creando entorno virtual e instalando dependencias Python dentro del contenedor..."
    distrobox enter "$BOX_NAME" -- bash -c "cd '$APP_DIR' && python3 -m venv --system-site-packages venv && ./venv/bin/pip install --upgrade pip && ./venv/bin/pip install -r requirements.txt"

    DISTROBOX_ENTER_BIN="$(command -v distrobox-enter)"

    echo ""
    echo "[4/4] Instalando icono y acceso directo (se abrirá a través del contenedor)..."
    install_icon_and_shortcut "$DISTROBOX_ENTER_BIN -n $BOX_NAME -- $APP_DIR/venv/bin/python3 $APP_DIR/main.py"

    echo ""
    echo "✅ Instalación completa."
    echo "Busca 'Deluxevor Music' en tu menú de aplicaciones (se ejecuta dentro"
    echo "del contenedor '$BOX_NAME' automáticamente, tú no notarás la diferencia)."
    echo ""
    echo "También puedes ejecutarlo manualmente con:"
    echo "  distrobox enter $BOX_NAME -- bash -c 'cd \"$APP_DIR\" && ./venv/bin/python3 main.py'"
}

# ---------------------------------------------------------------------------
# Punto de entrada: decide qué ruta usar.
# Se comprueban dos señales porque no todas las imágenes atómicas (Bazzite,
# uBlue, Silverblue, Kinoite...) exponen /run/ostree-booted de la misma forma;
# la presencia del binario rpm-ostree es igual de confiable.
# ---------------------------------------------------------------------------
if [ -f /run/ostree-booted ] || command -v rpm-ostree >/dev/null 2>&1; then
    install_atomic
else
    install_native
fi

#!/usr/bin/env bash
set -euo pipefail

# Se ubica a sí mismo para poder ejecutarse desde cualquier carpeta
# (doble clic, acceso directo del menú, o "bash install.sh" desde otro sitio).
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "== Instalando Deluxevor Music =="
echo "Carpeta de la app: $APP_DIR"

echo ""
echo "[1/4] Detectando tu distribución e instalando paquetes del sistema..."

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
echo "[2/4] Creando entorno virtual en ./venv (con acceso a paquetes del sistema)..."
python3 -m venv --system-site-packages venv

echo "Instalando dependencias Python puras dentro del entorno virtual..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo ""
echo "[3/4] Instalando el icono de la app (todos los tamaños)..."
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

echo ""
echo "[4/4] Creando acceso directo en el menú de aplicaciones..."
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/vorem.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Deluxevor Music
Comment=Reproductor de música local moderno y ligero
Exec=$APP_DIR/venv/bin/python3 $APP_DIR/main.py
Icon=vorem-music
Path=$APP_DIR
Terminal=false
Categories=Audio;Music;Player;GTK;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" || true
fi

echo ""
echo "✅ Instalación completa."
echo "Busca 'Deluxevor Music' en tu menú de aplicaciones (puede tardar unos"
echo "segundos en aparecer el icono nuevo)."
echo ""
echo "También puedes ejecutarlo manualmente con:"
echo "  cd \"$APP_DIR\" && source venv/bin/activate && python3 main.py"

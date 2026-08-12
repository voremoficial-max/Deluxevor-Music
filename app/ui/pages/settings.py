"""Ajustes funcionales de Deluxevor Music, Fase 7."""
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk

from app.services.downloader import save_youtube_cookies, has_youtube_cookies


class SettingsPage(Gtk.Box):
    def __init__(self, database, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.database = database
        self.window = window
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(28)
        self.set_margin_end(28)

        title = Gtk.Label(label="Ajustes", xalign=0)
        title.add_css_class("title-2")
        self.append(title)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scroll.set_child(content)
        self.append(scroll)

        content.append(self._section("Biblioteca"))
        folders = Adw.ActionRow(title="Carpetas de música")
        folders.set_subtitle("Administra las carpetas desde Biblioteca")
        b = Gtk.Button(label="Abrir Biblioteca")
        b.set_valign(Gtk.Align.CENTER)
        b.connect("clicked", lambda *_: self.window._select_page("library"))
        folders.add_suffix(b)
        content.append(folders)

        content.append(self._section("Reproducción"))
        self.autoplay = self._switch("Reproducción continua", "Pasar a la siguiente canción al terminar", "autoplay", True)
        content.append(self.autoplay)
        # Shuffle y repetición se controlan directamente desde la pantalla
        # de Canciones. Se eliminan de Ajustes para evitar dos controles que
        # puedan quedar desincronizados.

        content.append(self._section("Audio"))
        volume = Adw.ActionRow(title="Volumen", subtitle="Volumen inicial")
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        scale.set_range(0, 100)
        scale.set_value(float(self.database.get_setting("volume", "100")))
        scale.set_draw_value(True)
        scale.set_size_request(220, -1)
        scale.connect("value-changed", self._volume_changed)
        volume.add_suffix(scale)
        content.append(volume)
        self.volume_scale = scale

        content.append(self._section("Visualizador"))
        self.visualizer = self._switch("Visualizador activo", "Analiza el espectro real durante la reproducción", "visualizer_enabled", True)
        content.append(self.visualizer)
        intensity = Adw.ActionRow(title="Intensidad", subtitle="Respuesta de las barras")
        intensity_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        intensity_scale.set_range(0.8, 2.0)
        intensity_scale.set_value(float(self.database.get_setting("visualizer_intensity", "1.48")))
        intensity_scale.set_digits(2)
        intensity_scale.set_draw_value(True)
        intensity_scale.set_size_request(220, -1)
        intensity_scale.connect("value-changed", self._intensity_changed)
        intensity.add_suffix(intensity_scale)
        content.append(intensity)
        self.intensity_scale = intensity_scale

        content.append(self._section("Interfaz"))
        self.animations = self._switch("Animaciones", "Activa transiciones suaves de la interfaz", "animations", True)
        content.append(self.animations)

        # Selector visual de temas: botones grandes y claramente visibles.
        # Se usa Gtk.FlowBox en lugar de ComboRow para que las paletas sean
        # evidentes en Ajustes incluso en ventanas pequeñas.
        theme_title = Gtk.Label(label="Tema visual", xalign=0)
        theme_title.add_css_class("heading")
        theme_title.set_margin_top(8)
        content.append(theme_title)
        theme_subtitle = Gtk.Label(
            label="Elige una paleta suave para Deluxevor Music", xalign=0
        )
        theme_subtitle.add_css_class("dim-label")
        content.append(theme_subtitle)

        theme_values = [
            ("system", "Sistema", "◐"),
            ("dark", "Deluxevor oscuro", "●"),
            ("blue", "Azul noche", "●"),
            ("green", "Verde bosque", "●"),
            ("violet", "Violeta humo", "●"),
            ("light", "Claro", "○"),
        ]
        self._theme_values = [value for value, _label, _symbol in theme_values]
        current_theme = self.database.get_setting("theme", "dark")
        self.theme_buttons = {}
        theme_box = Gtk.FlowBox()
        theme_box.set_selection_mode(Gtk.SelectionMode.NONE)
        theme_box.set_row_spacing(8)
        theme_box.set_column_spacing(8)
        theme_box.set_max_children_per_line(3)
        theme_box.set_min_children_per_line(2)
        theme_box.set_homogeneous(True)
        for value, label, symbol in theme_values:
            button = Gtk.Button(label=f"{symbol}  {label}")
            button.set_tooltip_text(f"Usar tema: {label}")
            button.add_css_class("vorem-theme-button")
            button.add_css_class(f"vorem-theme-{value}")
            button.set_size_request(150, 52)
            button.connect("clicked", self._theme_button_clicked, value)
            theme_box.insert(button, -1)
            self.theme_buttons[value] = button
        content.append(theme_box)
        self._update_theme_buttons(current_theme)

        content.append(self._section("Inicio"))
        startup = Adw.ComboRow(title="Al iniciar", subtitle="Página mostrada al abrir Deluxevor Music")
        startup.set_model(Gtk.StringList.new(["Canciones", "Biblioteca", "Última página"]))
        startup.set_selected({"songs": 0, "library": 1, "last": 2}.get(self.database.get_setting("startup_page", "songs"), 0))
        startup.connect("notify::selected", self._startup_changed)
        content.append(startup)
        self.startup_row = startup

        content.append(self._section("Fuentes externas (letras y descargas)"))
        content.append(self._genius_block())
        content.append(self._cookies_block())

        content.append(self._section("Apoya el proyecto"))
        content.append(self._support_block())

        content.append(self._section("Acerca de"))
        content.append(self._about_block())

    def _instructions(self, pasos):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("dim-label")
        box.set_margin_top(2)
        box.set_margin_bottom(6)
        for paso in pasos:
            label = Gtk.Label(label=paso, xalign=0)
            label.set_wrap(True)
            label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            box.append(label)
        return box

    def _genius_block(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        heading = Gtk.Label(label="Token de Genius (más letras, incluida música latina/urbana)", xalign=0)
        heading.add_css_class("heading")
        box.append(heading)

        box.append(self._instructions([
            "1. Entra a genius.com/api-clients e inicia sesión (o crea una cuenta gratis).",
            "2. Pulsa “New API Client”.",
            "3. En “App Name” pon cualquier nombre, ej. Deluxevor Music; en “App Website URL” pon cualquier dirección, ej. http://localhost.",
            "4. Genera el cliente y copia el “Client Access Token”.",
            "5. Pégalo abajo y presiona Guardar.",
        ]))

        row = Adw.PasswordEntryRow(title="Client Access Token de Genius")
        current = self.database.get_setting("genius_token", "") or ""
        row.set_text(current)
        box.append(row)

        save_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save_row.set_halign(Gtk.Align.END)
        status = Gtk.Label(label="", xalign=1)
        status.add_css_class("dim-label")
        save_btn = Gtk.Button(label="Guardar")
        save_btn.add_css_class("suggested-action")

        def guardar(_btn):
            self.database.set_setting("genius_token", row.get_text().strip())
            self._flash(status, "Guardado ✓")

        save_btn.connect("clicked", guardar)
        save_row.append(status)
        save_row.append(save_btn)
        box.append(save_row)
        return box

    def _cookies_block(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(14)

        heading = Gtk.Label(label="Cookies de YouTube (evita “Sign in to confirm you’re not a bot”)", xalign=0)
        heading.add_css_class("heading")
        box.append(heading)

        box.append(self._instructions([
            "1. Instala la extensión “Get cookies.txt LOCALLY” en Chrome, Firefox o similar.",
            "2. Abre una ventana normal (no privada) e inicia sesión en youtube.com con tu cuenta.",
            "3. Con la extensión abierta en una pestaña de YouTube, exporta/copia las cookies del sitio (empiezan con “# Netscape HTTP Cookie File”).",
            "4. Pega el contenido completo abajo y presiona Guardar.",
            "Nota: si luego cierras sesión en YouTube en ese navegador, estas cookies dejan de servir; solo cerrar la pestaña no las invalida.",
        ]))

        text_frame = Gtk.Frame()
        cookies_scroll = Gtk.ScrolledWindow()
        cookies_scroll.set_min_content_height(140)
        cookies_scroll.set_vexpand(False)
        cookies_view = Gtk.TextView()
        cookies_view.set_monospace(True)
        cookies_view.set_wrap_mode(Gtk.WrapMode.NONE)
        cookies_view.set_top_margin(6); cookies_view.set_bottom_margin(6)
        cookies_view.set_left_margin(8); cookies_view.set_right_margin(8)
        current_cookies = self.database.get_setting("youtube_cookies", "") or ""
        cookies_view.get_buffer().set_text(current_cookies)
        cookies_scroll.set_child(cookies_view)
        text_frame.set_child(cookies_scroll)
        box.append(text_frame)

        state_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        state_label = Gtk.Label(
            label="Cookies activas" if has_youtube_cookies() else "Sin cookies configuradas",
            xalign=0,
        )
        state_label.add_css_class("dim-label")
        state_row.append(state_label)
        box.append(state_row)

        save_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save_row.set_halign(Gtk.Align.END)
        status = Gtk.Label(label="", xalign=1)
        status.add_css_class("dim-label")
        save_btn = Gtk.Button(label="Guardar")
        save_btn.add_css_class("suggested-action")

        def guardar(_btn):
            buf = cookies_view.get_buffer()
            texto = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
            self.database.set_setting("youtube_cookies", texto.strip())
            save_youtube_cookies(texto)
            state_label.set_label("Cookies activas" if has_youtube_cookies() else "Sin cookies configuradas")
            self._flash(status, "Guardado ✓")

        save_btn.connect("clicked", guardar)
        save_row.append(status)
        save_row.append(save_btn)
        box.append(save_row)
        return box

    def _support_block(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        invite = Gtk.Label(label="Te invito a apoyarme 💜", xalign=0)
        invite.add_css_class("heading")
        box.append(invite)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        whatsapp = Gtk.LinkButton(
            uri="https://chat.whatsapp.com/LISZACfu4Xo0irilkwofmN?s=cl&p=a&mlu=4",
            label="Grupo de WhatsApp",
        )
        whatsapp.add_css_class("suggested-action")
        buttons.append(whatsapp)

        tiktok = Gtk.LinkButton(
            uri="https://www.tiktok.com/@vorem_of?_r=1&_t=ZS-98o3DdNGzHo",
            label="@vorem_of en TikTok",
        )
        buttons.append(tiktok)

        box.append(buttons)
        return box

    def _about_block(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        version = Gtk.Label(label="Versión 1.1", xalign=0)
        version.add_css_class("dim-label")
        box.append(version)
        creator = Gtk.Label(label="By vorem", xalign=0)
        creator.add_css_class("dim-label")
        box.append(creator)
        return box

    def _flash(self, label, text, seconds=2.5):
        label.set_label(text)
        GLib.timeout_add(int(seconds * 1000), lambda: (label.set_label(""), False)[1])

    def _section(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("heading")
        label.set_margin_top(10)
        return label

    def _switch(self, title, subtitle, key, default):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        sw.set_active(self.database.get_setting(key, "1" if default else "0") == "1")
        sw.connect("notify::active", self._switch_changed, key)
        row.add_suffix(sw)
        row.set_activatable_widget(sw)
        return row

    def _find_switch(self, row):
        child = row.get_first_child()
        while child:
            if isinstance(child, Gtk.Switch):
                return child
            child = child.get_next_sibling()
        return None

    def _switch_changed(self, switch, _pspec, key):
        self.database.set_setting(key, "1" if switch.get_active() else "0")
        if key == "autoplay":
            self.window.autoplay_enabled = switch.get_active()
        elif key == "visualizer_enabled":
            self.window.set_visualizer_enabled(switch.get_active())
        elif key == "animations":
            self.window.set_animations_enabled(switch.get_active())

    def _volume_changed(self, scale):
        value = scale.get_value()
        self.database.set_setting("volume", value)
        self.window.engine.set_volume(value / 100)

    def _intensity_changed(self, scale):
        value = scale.get_value()
        self.database.set_setting("visualizer_intensity", value)
        self.window.set_visualizer_intensity(value)

    def _theme_button_clicked(self, _button, value):
        self.database.set_setting("theme", value)
        self.window.apply_theme(value)
        self._update_theme_buttons(value)

    def _update_theme_buttons(self, active):
        for value, button in self.theme_buttons.items():
            button.remove_css_class("vorem-theme-selected")
            if value == active:
                button.add_css_class("vorem-theme-selected")


    def _startup_changed(self, row, _pspec):
        values = ["songs", "library", "last"]
        self.database.set_setting("startup_page", values[row.get_selected()])

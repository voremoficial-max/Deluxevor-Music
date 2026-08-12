"""Página de biblioteca: carpetas y escaneo incremental."""
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk


class LibraryPage(Gtk.Box):
    def __init__(self, database, scanner, on_library_changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.database = database
        self.scanner = scanner
        self.on_library_changed = on_library_changed

        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(28)
        self.set_margin_end(28)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        title = Gtk.Label(label="Biblioteca")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-2")
        title_box.append(title)
        self.status = Gtk.Label(label="Añade una carpeta para comenzar")
        self.status.set_halign(Gtk.Align.START)
        self.status.add_css_class("dim-label")
        title_box.append(self.status)
        header.append(title_box)

        scan = Gtk.Button(label="Escanear ahora")
        scan.add_css_class("suggested-action")
        scan.connect("clicked", self._on_scan)
        self.scan_button = scan
        header.append(scan)
        self.append(header)

        frame = Gtk.Frame(label="Carpetas de música")
        self.folder_list = Gtk.ListBox()
        self.folder_list.set_selection_mode(Gtk.SelectionMode.NONE)
        frame.set_child(self.folder_list)
        self.append(frame)

        add = Gtk.Button(label="Añadir carpeta…")
        add.set_halign(Gtk.Align.START)
        add.connect("clicked", self._on_add_folder)
        self.append(add)
        self._refresh()

    def _refresh(self):
        while (row := self.folder_list.get_first_child()) is not None:
            self.folder_list.remove(row)
        folders = self.database.get_folders()
        for folder in folders:
            row = Adw.ActionRow(title=folder)
            row.add_suffix(Gtk.Image.new_from_icon_name("folder-music-symbolic"))
            remove = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            remove.set_tooltip_text("Quitar carpeta")
            remove.add_css_class("flat")
            remove.connect("clicked", self._on_remove_folder, folder)
            row.add_suffix(remove)
            self.folder_list.append(row)
        self.status.set_label(f"{len(folders)} carpeta(s) configurada(s) · {self.database.count_songs()} canciones")

    def _on_add_folder(self, _button):
        dialog = Gtk.FileDialog(title="Seleccionar carpeta de música")
        dialog.select_folder(self.get_root(), None, self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            gfile = dialog.select_folder_finish(result)
        except Exception:
            return
        if gfile and gfile.get_path():
            self.database.add_folder(gfile.get_path())
            self._refresh()
            self.on_library_changed()
            self._on_scan(None)

    def _on_remove_folder(self, _button, folder):
        self.database.remove_folder(folder)
        self._refresh()
        self.on_library_changed()

    def _on_scan(self, _button):
        if self.scanner.running:
            return
        self.scan_button.set_sensitive(False)
        self.status.set_label("Escaneando biblioteca…")
        self.scanner.start(on_progress=self._on_progress, on_finished=self._on_finished)

    def _on_progress(self, current, total, filename):
        from gi.repository import GLib
        GLib.idle_add(self._update_progress, current, total, filename)

    def _update_progress(self, current, total, filename):
        self.status.set_label(f"Escaneando {current}/{total}: {filename}")
        return False

    def _on_finished(self, result):
        from gi.repository import GLib
        GLib.idle_add(self._finish_ui, result)

    def _finish_ui(self, result):
        self.scan_button.set_sensitive(True)
        if result["success"]:
            self.status.set_label(
                f"Biblioteca actualizada · +{result['added']} nuevas · {result['updated']} actualizadas · "
                f"{result['removed']} eliminadas · {result['errors']} con error"
            )
        else:
            self.status.set_label("El escaneo terminó con un error. Revisa el registro de Deluxevor Music.")
        self._refresh()
        self.on_library_changed()
        return False

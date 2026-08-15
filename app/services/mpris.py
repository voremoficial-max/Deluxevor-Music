"""Soporte MPRIS (org.mpris.MediaPlayer2).

Publica Deluxevor Music en el bus de sesión de D-Bus para que el entorno de
escritorio (GNOME, KDE, XFCE...) y los teclados con teclas multimedia
dedicadas (Reproducir/Pausar, Siguiente, Anterior) puedan controlarlo, aun
con la ventana minimizada, en otro escritorio virtual, o sin el foco. Es el
mismo mecanismo estándar que usan VLC, Rhythmbox, etc. en Linux — no
requiere ninguna dependencia nueva, D-Bus ya viene
integrado en GLib/PyGObject.
"""
import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gio, Gst

from app.utils.logger import get_logger

logger = get_logger(__name__)

BUS_NAME = "org.mpris.MediaPlayer2.deluxevormusic"
OBJECT_PATH = "/org/mpris/MediaPlayer2"

_INTROSPECTION_XML = """
<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/>
    <method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Pause"/>
    <method name="PlayPause"/>
    <method name="Stop"/>
    <method name="Play"/>
    <method name="Seek"><arg direction="in" type="x" name="Offset"/></method>
    <method name="SetPosition">
      <arg direction="in" type="o" name="TrackId"/>
      <arg direction="in" type="x" name="Position"/>
    </method>
    <signal name="Seeked"><arg type="x" name="Position"/></signal>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Shuffle" type="b" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>
"""


class MprisService:
    def __init__(self, window):
        self.window = window
        self._connection = None
        self._registration_ids = []
        self._owner_id = None
        self._node_info = Gio.DBusNodeInfo.new_for_xml(_INTROSPECTION_XML)
        self._owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            BUS_NAME,
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            None,
            self._on_name_lost,
        )

    def shutdown(self):
        if self._owner_id:
            try:
                Gio.bus_unown_name(self._owner_id)
            except Exception:
                pass
            self._owner_id = None

    def _on_name_lost(self, _connection, _name):
        # No es un error fatal: probablemente ya hay otra instancia de la
        # app corriendo y dueña del nombre. Los controles de esa instancia
        # seguirán funcionando con normalidad.
        logger.info("No se pudo reservar el nombre MPRIS %s.", BUS_NAME)

    def _on_bus_acquired(self, connection, _name):
        self._connection = connection
        try:
            for interface in self._node_info.interfaces:
                reg_id = connection.register_object(
                    OBJECT_PATH,
                    interface,
                    self._handle_method_call,
                    self._handle_get_property,
                    self._handle_set_property,
                )
                self._registration_ids.append(reg_id)
        except Exception:
            logger.exception("No se pudo registrar el objeto MPRIS.")

    # ------------------------------------------------------------------
    def _handle_method_call(self, _connection, _sender, _path, _interface, method, params, invocation):
        w = self.window
        try:
            if method == "Next":
                w._next_song()
            elif method == "Previous":
                w._previous_song()
            elif method == "Pause":
                w.engine.pause()
            elif method == "Play":
                w.engine.play()
            elif method == "PlayPause":
                w.engine.toggle()
            elif method == "Stop":
                w.engine.stop()
            elif method == "Seek":
                (offset_us,) = params.unpack()
                w.engine.seek(w.engine.get_position() + offset_us / 1_000_000)
            elif method == "SetPosition":
                _trackid, position_us = params.unpack()
                w.engine.seek(position_us / 1_000_000)
            elif method == "Raise":
                if hasattr(w, "present"):
                    w.present()
            elif method == "Quit":
                pass
            invocation.return_value(None)
        except Exception:
            logger.exception("Error manejando el método MPRIS %s", method)
            invocation.return_value(None)

    def _handle_get_property(self, _connection, _sender, _path, interface, prop):
        w = self.window
        if interface == "org.mpris.MediaPlayer2":
            values = {
                "CanQuit": GLib.Variant("b", False),
                "CanRaise": GLib.Variant("b", True),
                "HasTrackList": GLib.Variant("b", False),
                "Identity": GLib.Variant("s", "Deluxevor Music"),
                "DesktopEntry": GLib.Variant("s", "vorem"),
                "SupportedUriSchemes": GLib.Variant("as", []),
                "SupportedMimeTypes": GLib.Variant("as", []),
            }
            return values.get(prop)
        if interface == "org.mpris.MediaPlayer2.Player":
            if prop == "PlaybackStatus":
                return GLib.Variant("s", self._playback_status())
            if prop == "Rate":
                return GLib.Variant("d", 1.0)
            if prop == "Shuffle":
                return GLib.Variant("b", bool(getattr(w, "shuffle_enabled", False)))
            if prop == "Metadata":
                return GLib.Variant("a{sv}", self._metadata())
            if prop == "Volume":
                return GLib.Variant("d", w.engine.get_volume())
            if prop == "Position":
                return GLib.Variant("x", int(w.engine.get_position() * 1_000_000))
            if prop == "MinimumRate":
                return GLib.Variant("d", 1.0)
            if prop == "MaximumRate":
                return GLib.Variant("d", 1.0)
            if prop in ("CanGoNext", "CanGoPrevious"):
                return GLib.Variant("b", bool(getattr(w, "queue", None)))
            if prop in ("CanPlay", "CanPause", "CanSeek", "CanControl"):
                return GLib.Variant("b", True)
        return None

    def _handle_set_property(self, _connection, _sender, _path, interface, prop, value):
        w = self.window
        if interface == "org.mpris.MediaPlayer2.Player" and prop == "Volume":
            w.engine.set_volume(value.unpack())
            return True
        return False

    # ------------------------------------------------------------------
    def _playback_status(self):
        try:
            _, state, _ = self.window.engine.get_gst_pipeline().get_state(0)
            if state == Gst.State.PLAYING:
                return "Playing"
            if state == Gst.State.PAUSED:
                return "Paused"
        except Exception:
            pass
        return "Stopped"

    def _metadata(self):
        w = self.window
        row = None
        queue = getattr(w, "queue", None)
        index = getattr(w, "queue_index", -1)
        if queue and 0 <= index < len(queue):
            row = queue[index]
        metadata = {"mpris:trackid": GLib.Variant("o", "/org/mpris/MediaPlayer2/deluxevormusic/CurrentTrack")}
        if row is not None:
            metadata["xesam:title"] = GLib.Variant("s", row["title"] or "")
            metadata["xesam:artist"] = GLib.Variant("as", [row["artist"] or "Artista desconocido"])
            metadata["xesam:album"] = GLib.Variant("s", row["album"] or "")
            duration = row["duration"] or 0
            metadata["mpris:length"] = GLib.Variant("x", int(duration * 1_000_000))
        return metadata

    def notify_properties_changed(self):
        """Avisa al sistema que cambió la canción o el estado (play/pausa),
        para que el centro de notificaciones y las teclas multimedia
        reflejen lo correcto de inmediato."""
        if not self._connection:
            return
        try:
            changed = {
                "PlaybackStatus": GLib.Variant("s", self._playback_status()),
                "Metadata": GLib.Variant("a{sv}", self._metadata()),
            }
            self._connection.emit_signal(
                None,
                OBJECT_PATH,
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", ("org.mpris.MediaPlayer2.Player", changed, [])),
            )
        except Exception:
            logger.exception("No se pudo emitir PropertiesChanged por MPRIS.")

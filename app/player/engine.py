"""Motor de reproducción de audio basado en GStreamer (playbin)."""
from pathlib import Path

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, GObject, Gst

from app.utils.logger import get_logger

logger = get_logger(__name__)
POSITION_POLL_MS = 250


class PlayerEngine(GObject.GObject):
    __gsignals__ = {
        "state-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "position-updated": (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        "duration-changed": (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        "eos": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "error": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "spectrum-updated": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self):
        super().__init__()
        self._pipeline = Gst.ElementFactory.make("playbin", "vorem-player")
        if self._pipeline is None:
            raise RuntimeError("No se pudo crear el elemento GStreamer 'playbin'.")

        self._spectrum = Gst.ElementFactory.make("spectrum", "vorem-spectrum")
        if self._spectrum is not None:
            self._spectrum.set_property("bands", 32)
            self._spectrum.set_property("interval", 50 * Gst.MSECOND)
            self._spectrum.set_property("post-messages", True)
            self._spectrum.set_property("message-magnitude", True)
            self._spectrum.set_property("message-phase", False)
            self._pipeline.set_property("audio-filter", self._spectrum)
        else:
            logger.warning("GStreamer spectrum no está disponible; el visualizador quedará desactivado.")

        self._bus = self._pipeline.get_bus()
        self._bus.add_signal_watch()
        self._bus.connect("message", self._on_bus_message)
        self._duration_ns = 0
        self._poll_source_id = None
        self._current_uri = None
        self._volume = 1.0
        self._muted = False

    def load(self, path: str):
        """Carga una pista y fuerza un reinicio limpio de posición/estado."""
        file_path = Path(path).expanduser().resolve()
        if not file_path.is_file():
            self.emit("error", f"El archivo de audio no existe: {file_path}")
            return False
        uri = Gst.filename_to_uri(str(file_path))
        if not uri:
            self.emit("error", "No se pudo convertir la ruta del audio a una URI válida.")
            return False

        self._stop_polling()
        self._pipeline.set_state(Gst.State.NULL)
        # Quitar primero la URI anterior evita que playbin conserve la posición
        # de la pista previa mientras prepara la nueva.
        try:
            self._pipeline.set_property("uri", None)
        except Exception:
            pass
        self._duration_ns = 0
        self._current_uri = uri
        self.emit("position-updated", 0.0)
        self.emit("duration-changed", 0.0)
        self.emit("spectrum-updated", tuple([0.0] * 32))
        self._pipeline.set_property("uri", uri)
        logger.info("Cargando: %s", path)
        return self.play()

    def play(self):
        if self._current_uri is None:
            return False
        ret = self._pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            self.emit("error", "No se pudo iniciar la reproducción.")
            return False
        self._start_polling()
        self.emit("state-changed", "playing")
        return True

    def pause(self):
        if self._current_uri is None:
            return
        self._pipeline.set_state(Gst.State.PAUSED)
        self._stop_polling()
        self.emit("state-changed", "paused")

    def toggle(self):
        if self._current_uri is None:
            return
        _, state, _ = self._pipeline.get_state(0)
        if state == Gst.State.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self):
        self._pipeline.set_state(Gst.State.NULL)
        self._stop_polling()
        self.emit("state-changed", "stopped")

    def seek(self, position_seconds: float):
        if self._current_uri is None:
            return
        position_seconds = max(0.0, float(position_seconds))
        self._pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            int(position_seconds * Gst.SECOND),
        )

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, float(volume)))
        self._pipeline.set_property("volume", self._volume)

    def get_volume(self) -> float:
        return self._volume

    def get_muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool):
        self._muted = bool(muted)
        self._pipeline.set_property("mute", self._muted)

    def get_position(self) -> float:
        ok, position_ns = self._pipeline.query_position(Gst.Format.TIME)
        if not ok:
            return 0.0
        return position_ns / Gst.SECOND

    def get_duration(self) -> float:
        return self._duration_ns / Gst.SECOND if self._duration_ns else 0.0

    def get_gst_pipeline(self):
        return self._pipeline

    def _start_polling(self):
        if self._poll_source_id is None:
            self._poll_source_id = GLib.timeout_add(POSITION_POLL_MS, self._on_poll_tick)

    def _stop_polling(self):
        if self._poll_source_id is not None:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None

    def _on_poll_tick(self):
        self.emit("position-updated", self.get_position())
        if self._duration_ns == 0:
            ok, duration_ns = self._pipeline.query_duration(Gst.Format.TIME)
            if ok and duration_ns > 0:
                self._duration_ns = duration_ns
                self.emit("duration-changed", self.get_duration())
        return True

    def _on_bus_message(self, _bus, message):
        mtype = message.type
        if mtype == Gst.MessageType.EOS:
            self._stop_polling()
            self.emit("position-updated", self.get_duration())
            self.emit("eos")
        elif mtype == Gst.MessageType.ELEMENT:
            structure = message.get_structure()
            if structure is not None and structure.get_name() == "spectrum":
                try:
                    magnitudes = structure.get_value("magnitude")
                    self.emit("spectrum-updated", tuple(float(v) for v in magnitudes))
                except (TypeError, ValueError, AttributeError):
                    pass
        elif mtype == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error("Error de GStreamer: %s (%s)", err, debug)
            self._stop_polling()
            self.emit("error", str(err))
        elif mtype == Gst.MessageType.STATE_CHANGED and message.src == self._pipeline:
            _old, new, _pending = message.parse_state_changed()
            if new == Gst.State.PLAYING:
                self.emit("state-changed", "playing")
            elif new == Gst.State.PAUSED:
                self.emit("state-changed", "paused")

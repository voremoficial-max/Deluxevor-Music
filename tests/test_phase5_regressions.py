from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase5_regressions_are_wired():
    window = (ROOT / "app/ui/window.py").read_text()
    player = (ROOT / "app/ui/player_bar.py").read_text()
    engine = (ROOT / "app/player/engine.py").read_text()
    visualizer = (ROOT / "app/ui/visualizer.py").read_text()
    songs = (ROOT / "app/ui/pages/songs.py").read_text()
    assert '("songs","Canciones"' in window and '("library","Biblioteca"' in window
    assert 'engine.connect("spectrum-updated", self._on_spectrum_updated)' in player
    assert 'self._pipeline.set_property("uri", None)' in engine
    assert 'self.emit("position-updated", 0.0)' in engine
    assert 'self.on_play_all' in songs and 'self.on_shuffle' in songs and 'self.on_repeat' in songs
    assert 'class MarqueeLabel' in (ROOT / "app/ui/marquee.py").read_text()
    assert 'def _ensure_timer' in visualizer

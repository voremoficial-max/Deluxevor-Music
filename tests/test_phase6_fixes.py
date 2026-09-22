from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_player_view_has_responsive_scroller():
    text = (ROOT / "app/ui/player_view.py").read_text()
    assert 'Gtk.ScrolledWindow()' in text
    assert 'scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)' in text
    assert 'self.cover.set_size_request(250, 250)' in text


def test_visualizer_more_sensitive():
    text = (ROOT / "app/ui/visualizer.py").read_text()
    assert "DB_FLOOR = -78.0" in text
    assert "SENSITIVITY = 1.48" in text
    assert "normalized ** 1.65" in text


def test_small_player_has_expand_button():
    text = (ROOT / "app/ui/player_bar.py").read_text()
    assert 'self.expand_button = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")' in text
    assert 'self.on_expand' in text


def test_auto_next_does_not_force_large_player():
    text = (ROOT / "app/ui/window.py").read_text()
    assert 'def _load_queue_index(self, index, show_view=False):' in text
    assert 'self._load_queue_index(self.queue_index + 1, show_view=False)' in text
    assert 'self._load_queue_index(self.queue_index, show_view=False)' in text


def test_back_returns_to_current_page():
    text = (ROOT / "app/ui/window.py").read_text()
    assert 'self.current_page = key' in text
    assert 'self.stack.set_visible_child_name(self.current_page)' in text

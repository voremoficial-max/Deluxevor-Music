import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_sidebar_is_stored_for_navigation():
    text=(ROOT/"app/ui/window.py").read_text()
    assert "self.sidebar=self._sidebar()" in text
    assert "self.sidebar_separator=Gtk.Separator" in text
    assert "self.sidebar.set_visible(True)" in text
    assert "self._set_player_fullscreen_ui(True)" in text

import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_visualizer_phase7_is_reactive_without_staying_high():
    t=(ROOT/"app/ui/visualizer.py").read_text()
    assert "BAND_COUNT = 29" in t
    assert "SENSITIVITY = 1.48" in t
    assert "normalized ** 1.65" in t
    assert "self.set_content_height(42)" in t

def test_large_player_keeps_sidebar_until_fullscreen():
    t=(ROOT/"app/ui/window.py").read_text()
    assert "self._load_queue_index(self.queue_index, show_view=True)" in t
    assert "self._load_queue_index(0, show_view=True)" in t
    assert "self.content_stack.set_visible_child_name(\"player-view\")" in t
    assert "self.sidebar.set_visible(True)" in t
    assert "self._set_player_fullscreen_ui(True)" in t
    assert "self._set_player_fullscreen_ui(False)" in t

def test_fullscreen_button_changes_to_restore():
    t=(ROOT/"app/ui/player_view.py").read_text()
    assert "self.fullscreen_button" in t
    assert 'self.fullscreen_button.set_icon_name("view-restore-symbolic")' in t
    assert 'self.fullscreen_button.set_icon_name("view-fullscreen-symbolic")' in t

def test_fullscreen_hides_sidebar_only_from_toggle():
    t=(ROOT/"app/ui/window.py").read_text()
    block=t.split("def _toggle_fullscreen",1)[1].split("def _on_global_key",1)[0]
    assert "self._set_player_fullscreen_ui(True)" in block
    assert "self.fullscreen()" in block
def test_visualizer_uses_29_bars_and_32_source_bands():
    v=(ROOT/"app/ui/visualizer.py").read_text()
    e=(ROOT/"app/player/engine.py").read_text()
    assert "BAND_COUNT = 29" in v
    assert 'set_property("bands", 32)' in e
    assert "SENSITIVITY = 1.48" in v

def test_settings_page_exists_and_has_phase7_controls():
    s=(ROOT/"app/ui/pages/settings.py").read_text()
    for key in ("autoplay", "volume", "visualizer_enabled",
                "visualizer_intensity", "animations", "theme", "startup_page"):
        assert key in s
    assert 'self.shuffle = self._switch' not in s
    assert 'self.repeat_row = repeat' not in s


def test_settings_has_soft_theme_palette():
    s=(ROOT/"app/ui/pages/settings.py").read_text()
    for key in ("Vorem oscuro", "Azul noche", "Verde bosque", "Violeta humo"):
        assert key in s

def test_sidebar_selection_syncs_when_opening_library_from_settings():
    w=(ROOT/"app/ui/window.py").read_text()
    assert "self.sidebar_list = lb" in w
    assert "self.sidebar_list.get_row_at_index(index)" in w
    assert "self.sidebar_list.select_row(row)" in w

def test_shuffle_and_repeat_have_visible_active_state():
    s=(ROOT/"app/ui/pages/songs.py").read_text()
    assert "vorem-mode-button" in s
    assert "vorem-mode-active" in s
    assert "vorem-repeat-off" in s
    assert "vorem-repeat-all" in s
    assert "vorem-repeat-one" in s
    assert "Aleatorio: activado" in s
    assert "Repetir: canción actual" in s


def test_themes_change_real_surface_backgrounds():
    w=(ROOT/"app/ui/window.py").read_text()
    assert "vorem-theme-surface" in w
    assert "theme_backgrounds" in w
    for color in ("#0b1522", "#0d1713", "#15101c", "#f4f6f8"):
        assert color in w


def test_song_editor_and_lyrics_are_available_from_three_dot_menu():
    s=(ROOT/"app/ui/pages/song_list.py").read_text()
    assert 'view-more-symbolic' in s
    assert 'Editar nombre' in s
    assert 'Cambiar carátula' in s
    assert 'Editar letra' in s
    assert 'update_song_metadata' in s
    assert 'Cambiar carátula' in s


def test_song_metadata_and_lyrics_are_persisted():
    d=(ROOT/"app/database/db.py").read_text()
    assert 'lyrics TEXT NOT NULL DEFAULT' in d
    assert 'metadata_edited INTEGER NOT NULL DEFAULT 0' in d
    assert 'update_song_metadata' in d
    assert 'metadata_edited=1' in d
    assert 'CASE WHEN songs.metadata_edited=1' in d


def test_player_has_lyrics_view():
    p=(ROOT/"app/ui/player_view.py").read_text()
    assert 'self.lyrics_button' in p
    assert 'self._show_lyrics' in p
    assert 'self._lyrics' in p


def test_group_pages_have_independent_metadata_actions():
    for name, field in (("albums.py", "álbum"), ("artists.py", "artista"), ("genres.py", "género")):
        text=(ROOT/"app/ui/pages"/name).read_text()
        assert f"Editar {field}" in text
        assert "Borrar todo" in text
        assert "MessageDialog" in text


def test_song_list_supports_multiselection():
    s=(ROOT/"app/ui/pages/song_list.py").read_text()
    assert "self.selected_ids" in s
    assert "get_selected_rows" in s
    assert "CheckButton" in s


def test_shuffle_previous_uses_history():
    s=(ROOT/"app/ui/window.py").read_text()
    assert "self.shuffle_history.append(self.queue_index)" in s
    assert "previous_index = self.shuffle_history.pop()" in s

def test_shuffle_tracks_seen_ids_and_never_repeats_until_cycle():
    w=(ROOT/"app/ui/window.py").read_text()
    assert "self.shuffle_seen_ids=set()" in w
    assert 'r["id"] not in self.shuffle_seen_ids' in w
    assert 'self.shuffle_seen_ids.add(row["id"])' in w
    assert 'if self.repeat_mode != "all"' in w


def test_scanner_does_not_delete_library_when_folder_is_unavailable():
    s=(ROOT/"app/library/scanner.py").read_text()
    assert "se conserva la biblioteca" in s
    assert "scanned_roots" in s
    assert "any(p == root or root in p.parents for root in scanned_roots)" in s



def test_download_page_has_retry_and_active_downloads():
    d=(ROOT/"app/ui/pages/download.py").read_text()
    assert "Descargas en curso" in d
    assert "Reintentar" in d
    assert "job[\"status\"] = \"failed\"" in d
    assert 'label="Buscar"' in d

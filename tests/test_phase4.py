import tempfile
from pathlib import Path
from app.database.db import MusicDatabase
from app.models.song import Song


def test_phase4_database_features():
    with tempfile.TemporaryDirectory() as td:
        db = MusicDatabase(Path(td) / "library.db")
        db.upsert_song(Song(path=str(Path(td)/"a.mp3"), title="Uno", artist="Artista", album="Album", genre="Rock", year="2026", duration=10, track_number=1, file_size=1, modified_time=1, cover_data=None))
        db.upsert_song(Song(path=str(Path(td)/"b.mp3"), title="Dos", artist="Artista", album="Album", genre="Rock", year="2026", duration=20, track_number=2, file_size=1, modified_time=1, cover_data=None))
        songs = db.list_songs()
        assert len(songs) == 2
        assert len(db.list_albums()) == 1
        assert len(db.list_artists()) == 1
        assert len(db.list_genres()) == 1
        assert db.toggle_favorite(songs[0]["id"]) is True
        assert len(db.list_favorites()) == 1
        pid = db.create_playlist("Mix")
        db.add_to_playlist(pid, songs[0]["id"])
        db.add_to_playlist(pid, songs[1]["id"])
        assert len(db.list_playlist_songs(pid)) == 2

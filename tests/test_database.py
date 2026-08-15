import tempfile
from pathlib import Path

from app.database.db import MusicDatabase
from app.models.song import Song


def test_database_roundtrip():
    with tempfile.TemporaryDirectory() as temp:
        db = MusicDatabase(Path(temp) / "library.db")
        db.add_folder(temp)
        song = Song(
            path=str(Path(temp) / "track.mp3"),
            title="Track",
            artist="Artist",
            album="Album",
            genre="Rock",
            year="2026",
            duration=123.0,
            track_number=1,
            file_size=100,
            modified_time=10.0,
            cover_data=b"cover",
        )
        db.upsert_song(song)
        rows = db.list_songs()
        assert len(rows) == 1
        assert rows[0]["title"] == "Track"
        assert rows[0]["cover_data"] == b"cover"
        assert not db.needs_update(song.path, 100, 10.0)
        assert db.needs_update(song.path, 101, 10.0)

from dataclasses import dataclass


@dataclass(slots=True)
class Song:
    path: str
    title: str
    artist: str
    album: str
    genre: str
    year: str
    duration: float
    track_number: int
    file_size: int
    modified_time: float
    cover_data: bytes | None = None
    lyrics: str = ""
    metadata_edited: bool = False
    id: int | None = None

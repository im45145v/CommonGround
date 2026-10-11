"""Local media library: music, books and cached audio live under media_dir (swap in an SSD mount)."""
from pathlib import Path

AUDIO = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}
BOOKS = {".txt", ".md", ".epub", ".pdf"}
SECTIONS = {"music": AUDIO, "books": BOOKS, "cache": AUDIO}


class Library:
    def __init__(self, media_dir: str):
        self.root = Path(media_dir)

    def list(self, section: str):
        d = self.root / section
        if section not in SECTIONS or not d.is_dir():
            return []
        return [{"name": p.name, "title": p.stem.replace("_", " ").replace("-", " ").title(), "size": p.stat().st_size}
                for p in sorted(d.iterdir()) if p.is_file() and p.suffix.lower() in SECTIONS[section]]

    def path(self, section: str, name: str):
        """Return a file only if it is listed directly inside the section folder (no path traversal)."""
        if section not in SECTIONS:
            return None
        d = self.root / section
        if not d.is_dir():
            return None
        for p in d.iterdir():
            if p.name == name and p.is_file() and p.suffix.lower() in SECTIONS[section]:
                return p
        return None

    def cache_path(self, name: str) -> Path:
        d = self.root / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d / name

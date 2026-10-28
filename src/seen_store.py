import json
from pathlib import Path


class SeenStore:
    """Registro de URLs ya notificadas, para no repetir avisos entre corridas."""

    def __init__(self, path: str):
        raw_path = Path(path)
        if not raw_path.is_absolute():
            self.path = Path(__file__).resolve().parent.parent / raw_path
        else:
            self.path = raw_path

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen = set(json.loads(self.path.read_text(encoding="utf-8"))) if self.path.exists() else set()

    def filter_new(self, opportunities: list) -> list:
        return [o for o in opportunities if o.url not in self._seen]

    def mark_seen(self, opportunities: list) -> None:
        self._seen.update(o.url for o in opportunities)
        self.path.write_text(json.dumps(sorted(self._seen), ensure_ascii=False, indent=2), encoding="utf-8")

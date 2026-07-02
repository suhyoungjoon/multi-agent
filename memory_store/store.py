import json
import os

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "notes.json")


class Store:
    def __init__(self, path: str = _DEFAULT_DB):
        self._path = path

    def _read(self) -> dict:
        if not os.path.exists(self._path):
            return {"notes": []}
        with open(self._path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save(self, content: str) -> dict:
        data = self._read()
        next_id = max((n["id"] for n in data["notes"]), default=0) + 1
        note = {"id": next_id, "content": content}
        data["notes"].append(note)
        self._write(data)
        return note

    def list_all(self) -> list:
        return self._read()["notes"]

    def get(self, note_id: int) -> dict | None:
        for note in self._read()["notes"]:
            if note["id"] == note_id:
                return note
        return None

import json
import os
import re

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "notes.json")
_LINEAR_THRESHOLD = 500


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

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        seen, result = set(), []
        for t in tags:
            lower = t.strip().lower()
            if lower and lower not in seen:
                seen.add(lower)
                result.append(lower)
        return result

    @staticmethod
    def _note_tags(note: dict) -> list[str]:
        return note.get("tags", [])

    @staticmethod
    def _tag_matches(note: dict, tags: list[str], match_all: bool) -> bool:
        if not tags:
            return True
        note_tags = set(Store._note_tags(note))
        wanted = set(tags)
        return wanted.issubset(note_tags) if match_all else bool(wanted & note_tags)

    def save(self, content: str, tags: list[str] | None = None) -> dict:
        data = self._read()
        next_id = max((n["id"] for n in data["notes"]), default=0) + 1
        note = {
            "id": next_id,
            "content": content,
            "tags": self._normalize_tags(tags or []),
        }
        data["notes"].append(note)
        self._write(data)
        return note

    @staticmethod
    def _normalize_note(note: dict) -> dict:
        if "tags" not in note:
            return {**note, "tags": []}
        return note

    def list_all(self, tags: list[str] | None = None, match_all: bool = True) -> list:
        notes = [self._normalize_note(n) for n in self._read()["notes"]]
        filter_tags = [t.lower() for t in (tags or [])]
        return [n for n in notes if self._tag_matches(n, filter_tags, match_all)]

    def get(self, note_id: int) -> dict | None:
        for note in self._read()["notes"]:
            if note["id"] == note_id:
                return note
        return None

    def search(self, keyword: str, tags: list[str] | None = None, match_all: bool = True) -> list:
        notes = self._read()["notes"]
        filter_tags = [t.lower() for t in (tags or [])]
        kw = keyword.lower()

        if len(notes) <= _LINEAR_THRESHOLD:
            candidates = [n for n in notes if kw in n["content"].lower()]
        else:
            candidates = self._index_search(notes, kw)

        return [n for n in candidates if self._tag_matches(n, filter_tags, match_all)]

    @staticmethod
    def _index_search(notes: list, kw: str) -> list:
        tokens = re.findall(r"\w+", kw)
        if not tokens:
            return []
        index: dict[str, set[int]] = {}
        for note in notes:
            words = re.findall(r"\w+", note["content"].lower())
            for word in words:
                index.setdefault(word, set()).add(note["id"])
        matched_ids: set[int] | None = None
        for token in tokens:
            hits = {nid for word, ids in index.items() if token in word for nid in ids}
            matched_ids = hits if matched_ids is None else matched_ids & hits
        if matched_ids is None:
            return []
        id_set = matched_ids
        return [n for n in notes if n["id"] in id_set]

    def list_tags(self) -> list[dict]:
        counts: dict[str, int] = {}
        for note in self._read()["notes"]:
            for tag in self._note_tags(note):
                counts[tag] = counts.get(tag, 0) + 1
        return [{"tag": t, "count": c} for t, c in sorted(counts.items(), key=lambda x: -x[1])]

import json
import os
import subprocess
import sys
import tempfile
import unittest


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.write(b'{"notes":[]}')
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def _make_store(self):
        from memory_store.store import Store
        return Store(self.path)

    def test_list_all_empty(self):
        s = self._make_store()
        self.assertEqual(s.list_all(), [])

    def test_list_all_on_missing_file_returns_empty(self):
        from memory_store.store import Store
        s = Store("/tmp/nonexistent_notes_xyzzy.json")
        self.assertEqual(s.list_all(), [])

    def test_save_on_missing_file_creates_note(self):
        from memory_store.store import Store
        path = "/tmp/nonexistent_notes_xyzzy2.json"
        if os.path.exists(path):
            os.unlink(path)
        s = Store(path)
        try:
            note = s.save("파일 없을 때 저장")
            self.assertEqual(note["content"], "파일 없을 때 저장")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_save_returns_new_id(self):
        s = self._make_store()
        note = s.save("첫 번째 메모")
        self.assertIn("id", note)
        self.assertEqual(note["content"], "첫 번째 메모")

    def test_save_persists_to_file(self):
        s = self._make_store()
        s.save("저장 테스트")
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["notes"]), 1)
        self.assertEqual(data["notes"][0]["content"], "저장 테스트")

    def test_list_all_returns_all_saved(self):
        s = self._make_store()
        s.save("첫째")
        s.save("둘째")
        notes = s.list_all()
        self.assertEqual(len(notes), 2)
        self.assertEqual([n["content"] for n in notes], ["첫째", "둘째"])

    def test_get_returns_correct_note(self):
        s = self._make_store()
        saved = s.save("찾을 메모")
        found = s.get(saved["id"])
        self.assertEqual(found["content"], "찾을 메모")

    def test_get_missing_id_returns_none(self):
        s = self._make_store()
        self.assertIsNone(s.get(999))

    def test_ids_are_unique_and_incrementing(self):
        s = self._make_store()
        a = s.save("A")
        b = s.save("B")
        self.assertNotEqual(a["id"], b["id"])
        self.assertLess(a["id"], b["id"])


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.write(b'{"notes":[]}')
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def _run(self, *args):
        result = subprocess.run(
            [sys.executable, "-m", "memory_store.cli", "--db", self.path, *args],
            capture_output=True,
            text=True,
        )
        return result

    def test_cli_save_prints_id(self):
        r = self._run("save", "CLI 테스트 메모")
        self.assertEqual(r.returncode, 0)
        self.assertIn("id", r.stdout)

    def test_cli_list_empty(self):
        r = self._run("list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("0", r.stdout)

    def test_cli_list_shows_saved_notes(self):
        self._run("save", "리스트 테스트")
        r = self._run("list")
        self.assertIn("리스트 테스트", r.stdout)

    def test_cli_get_shows_note(self):
        save_r = self._run("save", "조회 테스트")
        note_id = json.loads(save_r.stdout)["id"]
        r = self._run("get", str(note_id))
        self.assertIn("조회 테스트", r.stdout)

    def test_cli_get_missing_id_exits_nonzero(self):
        r = self._run("get", "9999")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()

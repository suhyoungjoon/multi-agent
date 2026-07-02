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
        self.assertIn("없", r.stdout)

    def test_cli_list_shows_saved_notes(self):
        self._run("save", "리스트 테스트")
        r = self._run("list")
        self.assertIn("리스트 테스트", r.stdout)

    def test_cli_get_shows_note(self):
        self._run("save", "조회 테스트")
        r = self._run("get", "1")
        self.assertIn("조회 테스트", r.stdout)

    def test_cli_get_missing_id_exits_nonzero(self):
        r = self._run("get", "9999")
        self.assertNotEqual(r.returncode, 0)


class TestStoreTags(unittest.TestCase):
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

    def test_save_with_tags_persists_tags(self):
        s = self._make_store()
        note = s.save("태그 메모", tags=["Work", "Idea"])
        self.assertEqual(note["tags"], ["work", "idea"])

    def test_save_tags_normalized_to_lowercase(self):
        s = self._make_store()
        note = s.save("내용", tags=["PYTHON", "Django"])
        self.assertIn("python", note["tags"])
        self.assertIn("django", note["tags"])
        self.assertNotIn("PYTHON", note["tags"])

    def test_save_tags_deduplicated(self):
        s = self._make_store()
        note = s.save("내용", tags=["work", "Work", "WORK"])
        self.assertEqual(note["tags"].count("work"), 1)

    def test_save_no_tags_defaults_to_empty(self):
        s = self._make_store()
        note = s.save("태그 없는 메모")
        self.assertEqual(note["tags"], [])

    def test_legacy_note_without_tags_returns_empty_tags(self):
        legacy = {"notes": [{"id": 1, "content": "옛날 메모"}]}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(legacy, f)
        s = self._make_store()
        notes = s.list_all()
        self.assertEqual(notes[0]["tags"], [])

    def test_list_all_no_filter_returns_all(self):
        s = self._make_store()
        s.save("A", tags=["x"])
        s.save("B", tags=["y"])
        self.assertEqual(len(s.list_all()), 2)

    def test_list_all_and_filter(self):
        s = self._make_store()
        s.save("A", tags=["work", "idea"])
        s.save("B", tags=["work"])
        s.save("C", tags=["idea"])
        result = s.list_all(tags=["work", "idea"], match_all=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "A")

    def test_list_all_or_filter(self):
        s = self._make_store()
        s.save("A", tags=["work"])
        s.save("B", tags=["idea"])
        s.save("C", tags=["other"])
        result = s.list_all(tags=["work", "idea"], match_all=False)
        contents = {n["content"] for n in result}
        self.assertEqual(contents, {"A", "B"})

    def test_search_keyword_found(self):
        s = self._make_store()
        s.save("파이썬은 좋은 언어입니다")
        s.save("자바스크립트도 좋습니다")
        result = s.search("파이썬")
        self.assertEqual(len(result), 1)
        self.assertIn("파이썬", result[0]["content"])

    def test_search_case_insensitive(self):
        s = self._make_store()
        s.save("Python is great")
        result = s.search("python")
        self.assertEqual(len(result), 1)

    def test_search_no_match_returns_empty(self):
        s = self._make_store()
        s.save("전혀 관계없는 내용")
        self.assertEqual(s.search("xyz없음"), [])

    def test_search_with_tag_filter(self):
        s = self._make_store()
        s.save("파이썬 work 노트", tags=["work"])
        s.save("파이썬 idea 노트", tags=["idea"])
        result = s.search("파이썬", tags=["work"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tags"], ["work"])

    def test_list_tags_returns_counts(self):
        s = self._make_store()
        s.save("A", tags=["work", "python"])
        s.save("B", tags=["work"])
        s.save("C", tags=["python"])
        tags = s.list_tags()
        tag_map = {t["tag"]: t["count"] for t in tags}
        self.assertEqual(tag_map["work"], 2)
        self.assertEqual(tag_map["python"], 2)

    def test_list_tags_empty_when_no_notes(self):
        s = self._make_store()
        self.assertEqual(s.list_tags(), [])

    def test_search_large_dataset_uses_index(self):
        s = self._make_store()
        for i in range(510):
            s.save(f"노트 번호 {i}")
        s.save("특별한 검색어 xyzzy")
        result = s.search("xyzzy")
        self.assertEqual(len(result), 1)


class TestOutput(unittest.TestCase):
    def test_colorize_applies_ansi_when_enabled(self):
        from memory_store.output import colorize
        result = colorize("hello", 31, use_color=True)
        self.assertIn("\033[", result)
        self.assertIn("hello", result)

    def test_colorize_plain_when_disabled(self):
        from memory_store.output import colorize
        result = colorize("hello", 31, use_color=False)
        self.assertEqual(result, "hello")

    def test_highlight_wraps_keyword(self):
        from memory_store.output import highlight
        result = highlight("Python is great", "python", use_color=True)
        self.assertIn("\033[", result)
        self.assertIn("Python", result)

    def test_highlight_plain_when_color_disabled(self):
        from memory_store.output import highlight
        result = highlight("Python is great", "python", use_color=False)
        self.assertEqual(result, "Python is great")

    def test_use_color_false_when_no_color_env(self):
        import importlib
        import memory_store.output as out_mod
        orig = os.environ.get("NO_COLOR")
        os.environ["NO_COLOR"] = "1"
        try:
            importlib.reload(out_mod)
            self.assertFalse(out_mod.use_color())
        finally:
            if orig is None:
                del os.environ["NO_COLOR"]
            else:
                os.environ["NO_COLOR"] = orig
            importlib.reload(out_mod)


class TestCLIC(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.write(b'{"notes":[]}')
        self.tmp.close()
        self.path = self.tmp.name
        self.env = {**os.environ, "NO_COLOR": "1"}

    def tearDown(self):
        os.unlink(self.path)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "memory_store.cli", "--db", self.path, *args],
            capture_output=True, text=True, env=self.env,
        )

    def test_cli_save_with_tags(self):
        r = self._run("save", "태그 테스트", "--tags", "work,idea")
        self.assertEqual(r.returncode, 0)
        data = json.loads(open(self.path, encoding="utf-8").read())
        self.assertEqual(data["notes"][0]["tags"], ["work", "idea"])

    def test_cli_list_tag_and_filter(self):
        self._run("save", "A 노트", "--tags", "work,idea")
        self._run("save", "B 노트", "--tags", "work")
        r = self._run("list", "--tag", "work", "idea")
        self.assertIn("A 노트", r.stdout)
        self.assertNotIn("B 노트", r.stdout)

    def test_cli_list_tag_or_filter(self):
        self._run("save", "A 노트", "--tags", "work")
        self._run("save", "B 노트", "--tags", "idea")
        self._run("save", "C 노트", "--tags", "other")
        r = self._run("list", "--tag", "work", "idea", "--or")
        self.assertIn("A 노트", r.stdout)
        self.assertIn("B 노트", r.stdout)
        self.assertNotIn("C 노트", r.stdout)

    def test_cli_search_finds_keyword(self):
        self._run("save", "파이썬 프로그래밍")
        self._run("save", "자바스크립트")
        r = self._run("search", "파이썬")
        self.assertEqual(r.returncode, 0)
        self.assertIn("파이썬", r.stdout)
        self.assertNotIn("자바스크립트", r.stdout)

    def test_cli_search_no_results_exits_zero(self):
        r = self._run("search", "없는키워드xyz")
        self.assertEqual(r.returncode, 0)
        self.assertIn("없", r.stdout)

    def test_cli_search_with_tag_filter(self):
        self._run("save", "파이썬 work", "--tags", "work")
        self._run("save", "파이썬 idea", "--tags", "idea")
        r = self._run("search", "파이썬", "--tag", "work")
        self.assertIn("파이썬 work", r.stdout)
        self.assertNotIn("파이썬 idea", r.stdout)

    def test_cli_tags_shows_tag_counts(self):
        self._run("save", "A", "--tags", "work")
        self._run("save", "B", "--tags", "work,python")
        r = self._run("tags")
        self.assertEqual(r.returncode, 0)
        self.assertIn("work", r.stdout)
        self.assertIn("2", r.stdout)


if __name__ == "__main__":
    unittest.main()

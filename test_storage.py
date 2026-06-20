import json
import os
import tempfile
import unittest

import storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "data.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_missing_file_returns_default(self):
        data = storage.load(self.path)
        self.assertEqual(data, {"next_id": 1, "items": []})

    def test_save_then_load_roundtrip(self):
        data = {"next_id": 2, "items": [{"id": 1, "content": "할 일", "done": False, "created_at": "2024-01-01T00:00:00+00:00"}]}
        storage.save(self.path, data)
        loaded = storage.load(self.path)
        self.assertEqual(loaded, data)

    def test_save_leaves_no_temp_files_behind(self):
        storage.save(self.path, {"next_id": 1, "items": []})
        leftovers = [name for name in os.listdir(self.tmpdir.name) if name.startswith(".tmp_")]
        self.assertEqual(leftovers, [])

    def test_load_invalid_json_raises_value_error(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        with self.assertRaises(ValueError):
            storage.load(self.path)


if __name__ == "__main__":
    unittest.main()

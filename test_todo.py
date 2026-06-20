import unittest

from todo import TodoItem, TodoList


class TestTodoItem(unittest.TestCase):
    def test_to_dict_and_from_dict_roundtrip(self):
        item = TodoItem(id=1, content="우유 사기")
        data = item.to_dict()
        restored = TodoItem.from_dict(data)
        self.assertEqual(item, restored)

    def test_default_done_is_false(self):
        item = TodoItem(id=1, content="우유 사기")
        self.assertFalse(item.done)

    def test_from_dict_missing_key_raises_value_error(self):
        with self.assertRaises(ValueError):
            TodoItem.from_dict({"id": 1, "content": "우유 사기"})

    def test_default_priority_is_2(self):
        item = TodoItem(id=1, content="우유 사기")
        self.assertEqual(item.priority, 2)

    def test_to_dict_includes_priority(self):
        item = TodoItem(id=1, content="우유 사기", priority=1)
        data = item.to_dict()
        self.assertEqual(data["priority"], 1)

    def test_from_dict_without_priority_defaults_to_2(self):
        legacy_data = {
            "id": 1,
            "content": "우유 사기",
            "done": False,
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        item = TodoItem.from_dict(legacy_data)
        self.assertEqual(item.priority, 2)

    def test_from_dict_with_priority(self):
        data = {
            "id": 1,
            "content": "우유 사기",
            "done": False,
            "created_at": "2024-01-01T00:00:00+00:00",
            "priority": 1,
        }
        item = TodoItem.from_dict(data)
        self.assertEqual(item.priority, 1)


class TestTodoList(unittest.TestCase):
    def setUp(self):
        self.todo_list = TodoList()

    def test_add_assigns_incrementing_ids(self):
        first = self.todo_list.add("첫번째")
        second = self.todo_list.add("두번째")
        self.assertEqual(first.id, 1)
        self.assertEqual(second.id, 2)
        self.assertEqual(self.todo_list.next_id, 3)

    def test_add_default_priority_is_2(self):
        item = self.todo_list.add("할 일")
        self.assertEqual(item.priority, 2)

    def test_add_with_custom_priority(self):
        item = self.todo_list.add("할 일", priority=1)
        self.assertEqual(item.priority, 1)

    def test_find_existing_item(self):
        item = self.todo_list.add("할 일")
        found = self.todo_list.find(item.id)
        self.assertIs(found, item)

    def test_find_missing_item_returns_none(self):
        self.assertIsNone(self.todo_list.find(999))

    def test_complete_existing_item(self):
        item = self.todo_list.add("할 일")
        result = self.todo_list.complete(item.id)
        self.assertTrue(result)
        self.assertTrue(item.done)

    def test_complete_missing_item_returns_false(self):
        result = self.todo_list.complete(999)
        self.assertFalse(result)

    def test_delete_existing_item(self):
        item = self.todo_list.add("할 일")
        result = self.todo_list.delete(item.id)
        self.assertTrue(result)
        self.assertEqual(self.todo_list.list(), [])

    def test_delete_missing_item_returns_false(self):
        result = self.todo_list.delete(999)
        self.assertFalse(result)

    def test_list_sorted_by_id(self):
        third = self.todo_list.add("3")
        first = self.todo_list.add("4")
        self.todo_list.items.reverse()
        ordered = self.todo_list.list()
        self.assertEqual([item.id for item in ordered], sorted(item.id for item in [third, first]))

    def test_list_empty_when_no_items(self):
        self.assertEqual(self.todo_list.list(), [])

    def test_from_dict_to_dict_roundtrip(self):
        self.todo_list.add("할 일 1")
        self.todo_list.add("할 일 2")
        data = self.todo_list.to_dict()
        restored = TodoList.from_dict(data)
        self.assertEqual(restored.to_dict(), data)


if __name__ == "__main__":
    unittest.main()

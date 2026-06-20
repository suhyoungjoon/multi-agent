from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TodoItem:
    id: int
    content: str
    done: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    priority: int = 2

    REQUIRED_KEYS = ("id", "content", "done", "created_at")

    @classmethod
    def from_dict(cls, data: dict) -> "TodoItem":
        missing = [key for key in cls.REQUIRED_KEYS if key not in data]
        if missing:
            raise ValueError(f"TodoItem 데이터에 필수 키가 없습니다: {', '.join(missing)}")
        return cls(
            id=data["id"],
            content=data["content"],
            done=data["done"],
            created_at=data["created_at"],
            priority=data.get("priority", 2),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "done": self.done,
            "created_at": self.created_at,
            "priority": self.priority,
        }


class TodoList:
    def __init__(self, next_id: int = 1, items: list[TodoItem] | None = None):
        self.next_id = next_id
        self.items: list[TodoItem] = items if items is not None else []

    @classmethod
    def from_dict(cls, data: dict) -> "TodoList":
        items = [TodoItem.from_dict(item) for item in data["items"]]
        return cls(next_id=data["next_id"], items=items)

    def to_dict(self) -> dict:
        return {
            "next_id": self.next_id,
            "items": [item.to_dict() for item in self.items],
        }

    def add(self, content: str, priority: int = 2) -> TodoItem:
        item = TodoItem(id=self.next_id, content=content, priority=priority)
        self.items.append(item)
        self.next_id += 1
        return item

    def find(self, item_id: int) -> TodoItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def delete(self, item_id: int) -> bool:
        item = self.find(item_id)
        if item is None:
            return False
        self.items.remove(item)
        return True

    def complete(self, item_id: int) -> bool:
        item = self.find(item_id)
        if item is None:
            return False
        item.done = True
        return True

    def list(self) -> list[TodoItem]:
        return sorted(self.items, key=lambda item: item.id)

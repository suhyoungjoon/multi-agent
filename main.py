import os
import sys

import storage
from todo import TodoList

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

HELP_TEXT = (
    "명령어:\n"
    "  add <내용>   - 할 일 추가\n"
    "  list         - 목록 조회\n"
    "  done <번호>  - 완료 처리\n"
    "  delete <번호> - 삭제\n"
    "  help         - 도움말\n"
    "  exit         - 종료\n"
)


def format_item(item) -> str:
    status = "x" if item.done else " "
    return f"{item.id}. [{status}] {item.content}"


def run(todo_list: TodoList, data_path: str) -> None:
    print("할 일 목록 콘솔 앱입니다. 'help'를 입력해 사용법을 확인하세요.")
    while True:
        try:
            command = input("> ").strip()
        except EOFError:
            break

        if not command:
            continue

        parts = command.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if action == "add":
            if not arg:
                print("할 일 내용을 입력해주세요")
                continue
            item = todo_list.add(arg)
            storage.save(data_path, todo_list.to_dict())
            print(f"추가되었습니다: [{item.id}] {item.content}")

        elif action == "list":
            items = todo_list.list()
            if not items:
                print("등록된 할 일이 없습니다")
            else:
                for item in items:
                    print(format_item(item))

        elif action == "done":
            if not arg or not arg.isdigit():
                print("번호를 입력해주세요")
                continue
            item = todo_list.find(int(arg))
            if item is None:
                print("해당 번호의 항목이 없습니다")
                continue
            todo_list.complete(item.id)
            storage.save(data_path, todo_list.to_dict())
            print(f"완료 처리되었습니다: [{item.id}] {item.content}")

        elif action == "delete":
            if not arg or not arg.isdigit():
                print("번호를 입력해주세요")
                continue
            item = todo_list.find(int(arg))
            if item is None:
                print("해당 번호의 항목이 없습니다")
                continue
            todo_list.delete(item.id)
            storage.save(data_path, todo_list.to_dict())
            print(f"삭제되었습니다: [{item.id}] {item.content}")

        elif action == "help":
            print(HELP_TEXT)

        elif action == "exit":
            print("종료합니다.")
            break

        else:
            print("알 수 없는 명령어입니다. help를 입력해 사용법을 확인하세요")


def main() -> None:
    try:
        data = storage.load(DATA_PATH)
        todo_list = TodoList.from_dict(data)
    except ValueError as e:
        print(str(e))
        sys.exit(1)
    run(todo_list, DATA_PATH)


if __name__ == "__main__":
    main()

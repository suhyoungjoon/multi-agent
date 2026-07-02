import argparse
import json
import os
import sys

from memory_store.store import Store, _DEFAULT_DB


def main(argv=None):
    parser = argparse.ArgumentParser(description="미니 기억저장소 CLI")
    parser.add_argument("--db", default=_DEFAULT_DB, help="JSON 저장 파일 경로")
    sub = parser.add_subparsers(dest="cmd", required=True)

    save_p = sub.add_parser("save", help="메모 저장")
    save_p.add_argument("content", help="저장할 내용")

    sub.add_parser("list", help="전체 메모 목록")

    get_p = sub.add_parser("get", help="ID로 메모 조회")
    get_p.add_argument("id", type=int, help="메모 ID")

    args = parser.parse_args(argv)
    store = Store(args.db)

    if args.cmd == "save":
        note = store.save(args.content)
        print(json.dumps(note, ensure_ascii=False))

    elif args.cmd == "list":
        notes = store.list_all()
        print(f"총 {len(notes)}개")
        for n in notes:
            print(f"  [{n['id']}] {n['content']}")

    elif args.cmd == "get":
        note = store.get(args.id)
        if note is None:
            print(f"ID {args.id} 메모를 찾을 수 없습니다.", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(note, ensure_ascii=False))


if __name__ == "__main__":
    main()

import argparse
import json
import sys

from memory_store import output as out
from memory_store.store import Store, _DEFAULT_DB


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()] if raw else []


def cmd_save(store: Store, args: argparse.Namespace) -> None:
    tags = _parse_tags(args.tags)
    note = store.save(args.content, tags=tags)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps(note, ensure_ascii=False))
        return
    _color = out.use_color()
    tick = out.colorize("✓ 저장됨", 36, 1, use_color=_color)
    tag_str = " ".join(out.colorize(f"[{t}]", 33, use_color=_color) for t in note["tags"])
    preview = note["content"][:60] + ("…" if len(note["content"]) > 60 else "")
    id_str = out.colorize(f"id: {note['id']}", 90, use_color=_color)
    parts = [f"{tick}  {tag_str}".rstrip() if tag_str else tick, f'  "{preview}"', f"  {id_str}"]
    print("\n".join(parts))


def cmd_list(store: Store, args: argparse.Namespace) -> None:
    tags = _parse_tags(getattr(args, "tag", "") or "")
    match_all = not getattr(args, "tag_or", False)
    notes = store.list_all(tags=tags, match_all=match_all)

    _color = out.use_color()
    if not notes:
        if tags:
            tag_labels = ", ".join(out.colorize(f"[{t}]", 33, use_color=_color) for t in tags)
            print(f"태그 {tag_labels}에 해당하는 노트가 없습니다.")
            print(out.colorize("  팁: python cli.py tags  로 사용 중인 태그를 확인하세요.", 90, use_color=_color))
        else:
            print("저장된 노트가 없습니다.")
            print(out.colorize("  시작하기: python cli.py save '첫 번째 노트' --tags 시작", 90, use_color=_color))
        return

    header = out.colorize(f"총 {len(notes)}개", 1, use_color=_color)
    body = out.format_notes(notes, color=_color)
    out.paginate(f"{header}\n{body}")


def cmd_search(store: Store, args: argparse.Namespace) -> None:
    tags = _parse_tags(getattr(args, "tag", "") or "")
    match_all = not getattr(args, "tag_or", False)
    notes = store.search(args.query, tags=tags, match_all=match_all)

    _color = out.use_color()
    kw_display = out.colorize(f'"{args.query}"', 1, use_color=_color)

    if not notes:
        cnt = out.colorize("0건", 36, use_color=_color)
        print(f"{kw_display} 검색 결과: {cnt}")
        tip = out.colorize("  팁: 다른 키워드로 시도하거나  python cli.py list  로 전체 목록을 확인하세요.", 90, use_color=_color)
        print(tip)
        return

    cnt = out.colorize(f"{len(notes)}건", 36, use_color=_color)
    header = out.colorize("검색 결과:", 1, use_color=_color)
    body = out.format_notes(notes, keyword=args.query, color=_color)
    out.paginate(f"{kw_display} {header} {cnt}\n{body}")


def cmd_tags(store: Store, args: argparse.Namespace) -> None:
    tag_list = store.list_tags()
    _color = out.use_color()
    width, _ = out.terminal_size()
    max_bar = min(width - 20, 30)

    if not tag_list:
        print("등록된 태그가 없습니다.")
        return

    max_count = tag_list[0]["count"]
    header = out.colorize(f"사용 중인 태그 ({len(tag_list)}개)", 1, use_color=_color)
    lines = [header, ""]
    for entry in tag_list:
        bar_len = round(entry["count"] / max_count * max_bar) if max_count else 0
        bar = out.colorize("█" * bar_len, 32, use_color=_color)
        count_str = out.colorize(f"{entry['count']}건", 90, use_color=_color)
        tag_name = out.colorize(f"{entry['tag']:<10}", 36, use_color=_color)
        lines.append(f"  {tag_name} {bar}  {count_str}")

    text = "\n".join(lines)
    if len(tag_list) > 20:
        out.paginate(text)
    else:
        print(text)


def cmd_get(store: Store, args: argparse.Namespace) -> None:
    note = store.get(args.id)
    if note is None:
        out.error(f"ID {args.id} 메모를 찾을 수 없습니다.")
        sys.exit(1)
    print(json.dumps(note, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description="미니 기억저장소 CLI")
    parser.add_argument("--db", default=_DEFAULT_DB, help="JSON 저장 파일 경로")
    sub = parser.add_subparsers(dest="cmd", required=True)

    save_p = sub.add_parser("save", help="노트 저장")
    save_p.add_argument("content", help="저장할 내용")
    save_p.add_argument("--tags", default="", metavar="TAG1,TAG2", help="쉼표 구분 태그")
    save_p.add_argument("--json", action="store_true", help="JSON 형식으로 출력 (스크립팅용)")

    list_p = sub.add_parser("list", help="전체 목록 / 태그 필터")
    list_p.add_argument("--tag", default="", metavar="TAG1,TAG2", help="쉼표 구분 태그 필터")
    list_p.add_argument("--or", dest="tag_or", action="store_true", help="태그 OR 매칭 (기본: AND)")

    search_p = sub.add_parser("search", help="키워드 검색")
    search_p.add_argument("query", help="검색 키워드")
    search_p.add_argument("--tag", default="", metavar="TAG1,TAG2", help="쉼표 구분 태그 필터")
    search_p.add_argument("--or", dest="tag_or", action="store_true")

    sub.add_parser("tags", help="태그 목록 + 사용 통계")

    get_p = sub.add_parser("get", help="ID로 조회")
    get_p.add_argument("id", type=int, help="메모 ID")

    args = parser.parse_args(argv)
    store = Store(args.db)

    dispatch = {
        "save": cmd_save,
        "list": cmd_list,
        "search": cmd_search,
        "tags": cmd_tags,
        "get": cmd_get,
    }
    dispatch[args.cmd](store, args)


if __name__ == "__main__":
    main()

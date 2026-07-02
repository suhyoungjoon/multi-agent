import os
import pydoc
import re
import shutil
import subprocess
import sys
import textwrap


def use_color() -> bool:
    if "NO_COLOR" in os.environ:
        return False
    return sys.stdout.isatty()


def colorize(text: str, *codes: int, use_color: bool | None = None) -> str:
    if use_color is None:
        use_color = globals()["use_color"]()
    if not use_color:
        return text
    code_str = ";".join(str(c) for c in codes)
    return f"\033[{code_str}m{text}\033[0m"


def highlight(text: str, keyword: str, use_color: bool | None = None) -> str:
    if use_color is None:
        use_color = globals()["use_color"]()
    if not use_color or not keyword:
        return text
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)

    def replace(m):
        return colorize(m.group(0), 32, 1, use_color=True)

    return pattern.sub(replace, text)


def terminal_size() -> tuple[int, int]:
    s = shutil.get_terminal_size(fallback=(80, 24))
    return s.columns, s.lines


def format_separator(width: int | None = None, color: bool | None = None) -> str:
    if width is None:
        width, _ = terminal_size()
    line = "─" * min(width, 80)
    return colorize(line, 90, use_color=color if color is not None else use_color())


def format_note(note: dict, keyword: str = "", color: bool | None = None, width: int | None = None) -> str:
    _color = color if color is not None else use_color()
    if width is None:
        width, _ = terminal_size()
    indent = "     "
    wrap_width = max(width - len(indent), 20)

    num = colorize(f"[{note['id']}]", 1, use_color=_color)
    tags_str = " ".join(colorize(f"[{t}]", 33, use_color=_color) for t in note.get("tags", []))
    header = f"{num}  {tags_str}" if tags_str else num

    content = note["content"]
    if keyword:
        content = highlight(content, keyword, use_color=_color)
    wrapped = textwrap.fill(content, wrap_width, subsequent_indent=indent)

    return f"{header}\n{indent}{wrapped}"


def format_notes(notes: list, keyword: str = "", color: bool | None = None) -> str:
    _color = color if color is not None else use_color()
    width, _ = terminal_size()
    sep = format_separator(width, color=_color)
    parts = [sep]
    for note in notes:
        parts.append(format_note(note, keyword=keyword, color=_color, width=width))
    return "\n".join(parts)


def paginate(text: str) -> None:
    lines = text.splitlines()
    _, term_h = terminal_size()
    if not sys.stdout.isatty() or len(lines) <= term_h - 2:
        print(text)
        return
    try:
        proc = subprocess.run(["less", "-R", "-F", "-X"], input=text, text=True)
        if proc.returncode == 0:
            return
    except FileNotFoundError:
        pass
    pydoc.pager(text)


def error(msg: str) -> None:
    icon = colorize("✗", 31, 1, use_color=use_color())
    print(f"{icon} {msg}", file=sys.stderr)

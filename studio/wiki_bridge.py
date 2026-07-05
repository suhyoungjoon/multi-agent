import datetime
import re
from pathlib import Path

DEFAULT_VAULT_PATH = Path.home() / "workspaces" / "multi-agent-wiki"


def read_hot_cache(vault_path: Path = DEFAULT_VAULT_PATH) -> str:
    hot_file = vault_path / "wiki" / "hot.md"
    try:
        return hot_file.read_text(encoding="utf-8")
    except OSError:
        return ""


def search_wiki(query: str, vault_path: Path = DEFAULT_VAULT_PATH) -> list[dict]:
    wiki_dir = vault_path / "wiki"
    if not wiki_dir.exists():
        return []

    results = []
    query_lower = query.lower()
    for md_file in wiki_dir.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if query_lower not in text.lower():
            continue
        idx = text.lower().index(query_lower)
        start = max(0, idx - 40)
        end = min(len(text), idx + len(query) + 40)
        results.append({"file": str(md_file.relative_to(vault_path)), "snippet": text[start:end]})
    return results


def _slugify(title: str) -> str:
    slug = re.sub(r"\s+", "-", title.strip())
    slug = re.sub(r"[^\w\-가-힣]", "", slug)
    return slug or "untitled"


def save_note(
    domain: str,
    title: str,
    content: str,
    tags: list[str],
    vault_path: Path = DEFAULT_VAULT_PATH,
) -> Path:
    """Write a plain frontmatter-templated note. No LLM synthesis (v1 scope)."""
    domain_dir = vault_path / "wiki" / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today().isoformat()
    tags_yaml = "\n".join(f"  - {tag}" for tag in tags)
    body = f'''---
type: note
title: "{title}"
updated: {today}
tags:
{tags_yaml}
status: current
---

# {title}

{content}
'''
    target = domain_dir / f"{_slugify(title)}.md"
    target.write_text(body, encoding="utf-8")
    return target

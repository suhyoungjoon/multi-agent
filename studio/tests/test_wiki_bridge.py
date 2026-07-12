from pathlib import Path

from studio import wiki_bridge


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "hot.md").write_text("# Recent Context\n\nsomething about memory_store", encoding="utf-8")
    (vault / "wiki" / "research").mkdir()
    (vault / "wiki" / "research" / "claude-certification.md").write_text(
        "CCA-F certification details here", encoding="utf-8"
    )
    return vault


def test_read_hot_cache_returns_file_contents(tmp_path: Path):
    vault = _make_vault(tmp_path)
    content = wiki_bridge.read_hot_cache(vault)
    assert "Recent Context" in content


def test_read_hot_cache_returns_empty_string_when_missing(tmp_path: Path):
    vault = tmp_path / "empty_vault"
    vault.mkdir()
    assert wiki_bridge.read_hot_cache(vault) == ""


def test_search_wiki_finds_matching_file(tmp_path: Path):
    vault = _make_vault(tmp_path)
    results = wiki_bridge.search_wiki("certification", vault_path=vault)
    assert len(results) == 1
    assert "claude-certification.md" in results[0]["file"]
    assert "CCA-F" in results[0]["snippet"]


def test_search_wiki_returns_empty_list_when_no_match(tmp_path: Path):
    vault = _make_vault(tmp_path)
    results = wiki_bridge.search_wiki("nonexistent-term-xyz", vault_path=vault)
    assert results == []


def test_save_note_writes_frontmatter_template(tmp_path: Path):
    vault = _make_vault(tmp_path)
    written = wiki_bridge.save_note(
        domain="studio-notes",
        title="테스트 노트",
        content="본문 내용입니다.",
        tags=["studio", "test"],
        vault_path=vault,
    )
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert 'title: "테스트 노트"' in text
    assert "본문 내용입니다." in text
    assert "- studio" in text

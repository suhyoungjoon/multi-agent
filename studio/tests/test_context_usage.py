from studio.context_usage import parse_context_usage

SCREEN_WITH_K = "some header\n12.3k/200k tokens (45.2%)\nfooter"
SCREEN_WITHOUT_K = "some header\n800/200k tokens (0.4%)\nfooter"
SCREEN_NO_USAGE = "nothing relevant here"


def test_parse_context_usage_with_k_suffix():
    result = parse_context_usage(SCREEN_WITH_K)
    assert result == (45.2, 12300)


def test_parse_context_usage_without_k_suffix():
    result = parse_context_usage(SCREEN_WITHOUT_K)
    assert result == (0.4, 800)


def test_parse_context_usage_returns_none_when_not_found():
    assert parse_context_usage(SCREEN_NO_USAGE) is None

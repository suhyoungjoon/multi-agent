from studio.pane_state import PaneState, STUCK_THRESHOLD_SEC, evaluate, is_clean_idle

IDLE_SCREEN = 'some earlier output\n❯ Try "help me debug"'
WORKING_SCREEN = 'Brewed for 12s\n❯ '
UNCHANGED_SCREEN = "same output every tick\n❯ "


def test_is_clean_idle_true_for_placeholder_prompt_without_timer():
    assert is_clean_idle(IDLE_SCREEN) is True


def test_is_clean_idle_false_when_timer_word_present():
    assert is_clean_idle(WORKING_SCREEN) is False


def test_evaluate_resets_timer_on_clean_idle():
    state = PaneState(last_hash="x", last_change_ts=0.0, stuck=True)
    new_state = evaluate(state, IDLE_SCREEN, now=1000.0, stuck_check_enabled=True)
    assert new_state.stuck is False
    assert new_state.last_change_ts == 1000.0


def test_evaluate_marks_stuck_after_threshold_when_screen_unchanged():
    state = PaneState(last_hash=hash(UNCHANGED_SCREEN[-400:]), last_change_ts=0.0, stuck=False)
    now = STUCK_THRESHOLD_SEC + 1
    new_state = evaluate(state, UNCHANGED_SCREEN, now=float(now), stuck_check_enabled=True)
    assert new_state.stuck is True


def test_evaluate_does_not_mark_stuck_before_threshold():
    state = PaneState(last_hash=hash(UNCHANGED_SCREEN[-400:]), last_change_ts=0.0, stuck=False)
    now = STUCK_THRESHOLD_SEC - 1
    new_state = evaluate(state, UNCHANGED_SCREEN, now=float(now), stuck_check_enabled=True)
    assert new_state.stuck is False


def test_evaluate_never_marks_stuck_when_toggle_disabled():
    state = PaneState(last_hash=hash(UNCHANGED_SCREEN[-400:]), last_change_ts=0.0, stuck=False)
    now = STUCK_THRESHOLD_SEC + 100
    new_state = evaluate(state, UNCHANGED_SCREEN, now=float(now), stuck_check_enabled=False)
    assert new_state.stuck is False


def test_evaluate_resets_timer_when_screen_changes():
    state = PaneState(last_hash=hash("old screen"), last_change_ts=0.0, stuck=False)
    new_state = evaluate(state, "brand new screen content\n❯ ", now=50.0, stuck_check_enabled=True)
    assert new_state.last_change_ts == 50.0
    assert new_state.stuck is False

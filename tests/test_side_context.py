"""sola/side_context.py — 사이드 채팅 시스템 메시지 조립기 (순수 함수)."""
from __future__ import annotations

from persona.schema import Persona
from sola.side_context import (
    DEFAULT_MAX_CHARS,
    PROPOSAL_HEAD_CHARS,
    build_side_system,
)
from store.bookmarks import Bookmark


def test_returns_only_base_when_no_extras():
    sys_msg, labels = build_side_system(
        base_system="BASE",
        persona=None,
        page_context="",
    )
    assert sys_msg == "BASE"
    assert labels == []


def test_includes_page_context_with_marker_and_label():
    sys_msg, labels = build_side_system(
        base_system="BASE",
        page_context="화면 요약: 트렌드 5건",
    )
    assert "현재 화면 컨텍스트" in sys_msg
    assert "트렌드 5건" in sys_msg
    assert "/화면" in sys_msg
    assert "현재 화면" in labels


def test_persona_block_attached_with_label_when_set():
    p = Persona(name="홍길동", dept="용접", job="용접 담당")
    sys_msg, labels = build_side_system(
        base_system="BASE",
        persona=p,
        page_context="",
    )
    assert "용접" in sys_msg
    assert any("페르소나" in lbl for lbl in labels)


def test_persona_unset_yields_no_label_even_if_persona_passed():
    p = Persona()  # 미설정
    sys_msg, labels = build_side_system(
        base_system="BASE",
        persona=p,
        page_context="page",
    )
    # 미설정 페르소나는 라벨에 포함되지 않음
    assert all("페르소나" not in lbl for lbl in labels)


def test_session_proposal_truncated_to_head_chars():
    long_md = "A" * (PROPOSAL_HEAD_CHARS + 5000)
    sys_msg, labels = build_side_system(
        base_system="BASE",
        page_context="",
        session_proposal=long_md,
    )
    assert "직전 작성 제안서" in sys_msg
    assert "직전 제안서" in labels
    # 본문이 PROPOSAL_HEAD_CHARS 까지만 포함됨
    proposal_section = sys_msg.split("--- 직전 작성 제안서 ---")[1]
    body = proposal_section.split("--- /제안서 ---")[0]
    assert body.count("A") == PROPOSAL_HEAD_CHARS


def test_adopted_proposals_include_title_decided_and_note():
    adopted = [
        Bookmark(
            id="x", type="proposal", title="용접 PoC",
            status="adopted",
            decision_note="3분기 승인",
            decided_at="2026-05-10T10:00:00+00:00",
        ),
        Bookmark(
            id="y", type="proposal", title="검사 자동화",
            status="adopted",
            decided_at="2026-05-11T10:00:00+00:00",
        ),
    ]
    sys_msg, labels = build_side_system(
        base_system="BASE",
        page_context="",
        adopted_proposals=adopted,
    )
    assert "용접 PoC" in sys_msg
    assert "검사 자동화" in sys_msg
    assert "2026-05-10" in sys_msg
    assert "3분기 승인" in sys_msg
    assert "채택 제안서 2건" in labels


def test_empty_adopted_iterable_yields_no_section():
    sys_msg, labels = build_side_system(
        base_system="BASE",
        page_context="page",
        adopted_proposals=[],
    )
    assert "채택" not in sys_msg
    assert all("채택" not in lbl for lbl in labels)


def test_max_chars_truncates_full_message():
    long_page = "X" * (DEFAULT_MAX_CHARS + 2000)
    sys_msg, _ = build_side_system(
        base_system="BASE",
        page_context=long_page,
        max_chars=DEFAULT_MAX_CHARS,
    )
    assert len(sys_msg) <= DEFAULT_MAX_CHARS + len("\n...[컨텍스트 길이 제한으로 잘림]")
    assert sys_msg.endswith("[컨텍스트 길이 제한으로 잘림]")


def test_ordering_page_then_session_proposal_then_adopted():
    """페이지 → 직전 제안서 → 채택 제안서 순으로 배치됨."""
    adopted = [Bookmark(id="x", type="proposal", title="채택본", status="adopted")]
    sys_msg, _ = build_side_system(
        base_system="BASE",
        page_context="PAGE_CONTEXT",
        session_proposal="SESSION_PROP",
        adopted_proposals=adopted,
    )
    idx_page = sys_msg.index("PAGE_CONTEXT")
    idx_sess = sys_msg.index("SESSION_PROP")
    idx_adopt = sys_msg.index("채택본")
    assert idx_page < idx_sess < idx_adopt


def test_base_system_kept_at_top():
    sys_msg, _ = build_side_system(
        base_system="MY_BASE_SYSTEM",
        page_context="PAGE",
    )
    assert sys_msg.startswith("MY_BASE_SYSTEM")

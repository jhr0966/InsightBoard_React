"""Phase C-4 — 보관함 정리: 컨트롤 스트립·하단 표/미리보기·칸반 가짜요소 제거."""
from __future__ import annotations

from ui import archive_v2


def test_strip_removes_controls_and_bottom_keeps_kanban():
    raw = archive_v2._ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
    out = archive_v2._strip_oa_mockups(raw)
    assert "oa-controls" not in out        # 죽은 컨트롤 스트립
    assert "oa-bottom" not in out          # 하단 표 + 미리보기 패널
    assert "PRO-2026" not in out           # 가짜 산출물 ID
    assert "전체 산출물" not in out         # 가짜 리스트 헤더
    assert "묶음 내보내기" not in out       # 죽은 내보내기 버튼
    # 칸반(실데이터)·셸·헤더 통계 보존
    assert 'class="oa-board"' in out
    assert "{{OA_CARDS_PENDING}}" in out
    assert "{{OA_TOTAL}}" in out
    assert 'class="oa-shell"' in out


def test_strip_noop_when_blocks_absent():
    html = '<div class="oa-shell"><section class="oa-board">{{OA_CARDS_PENDING}}</section></div>'
    assert archive_v2._strip_oa_mockups(html) == html


def test_template_kanban_mockup_removed():
    raw = archive_v2._ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
    assert "oa-col-add" not in raw         # "+ 새로 만들기" 가짜 버튼
    assert "전월 대비" not in raw          # "+6 (전월 대비)" 가짜 트렌드

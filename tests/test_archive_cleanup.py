"""보관함 정리: 정적 목업(컨트롤 스트립·하단 표/미리보기·칸반 가짜요소)이
템플릿에서 **영구 제거**됐는지 검증.

이전엔 런타임 `_strip_oa_mockups` 가 매 렌더마다 마커 슬라이스로 잘라냈으나
(마커 드리프트 시 목업 재등장 위험·테스트 부재), 완성도 점검 D1/D2 후속으로
목업을 `archive_main.html` 에서 직접 삭제하고 스트리퍼를 제거했다.
"""
from __future__ import annotations

from ui import archive_v2


def test_template_has_no_static_mockup():
    raw = archive_v2._ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
    for gone in ("oa-controls", "oa-bottom", "PRO-2026", "전체 산출물", "묶음 내보내기"):
        assert gone not in raw, f"목업 잔존: {gone}"
    # 헤더 통계·셸은 템플릿에 보존
    assert "{{OA_TOTAL}}" in raw
    assert 'class="oa-shell"' in raw
    assert 'class="oa-head"' in raw
    # 칸반 보드는 위젯(st.columns + _render_kanban_column)으로 이동 → 템플릿엔 없음
    assert 'class="oa-board"' not in raw
    assert "{{OA_CARDS_PENDING}}" not in raw


def test_runtime_stripper_removed():
    """런타임 문자열-수술 스트리퍼 제거 — 템플릿에서 직접 삭제했으므로 불필요."""
    assert not hasattr(archive_v2, "_strip_oa_mockups")


def test_template_kanban_mockup_removed():
    raw = archive_v2._ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
    assert "oa-col-add" not in raw         # "+ 새로 만들기" 가짜 버튼
    assert "전월 대비" not in raw          # "+6 (전월 대비)" 가짜 트렌드

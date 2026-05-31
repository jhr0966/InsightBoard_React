"""보드 음성으로 듣기 (TTS) wire — Web Speech API 인라인 재생."""
from __future__ import annotations

import json as _json
from unittest.mock import patch

import pandas as pd


# ── _tts_button_html ────────────────────────────────────────

def test_tts_button_encodes_text_safely_in_data_attr():
    from ui import board_v2
    html = board_v2._tts_button_html('"악의적" <script>alert(1)</script>')
    # JSON.dumps + html escape 로 안전 인코딩
    assert "<script>" not in html  # 원문 그대로 들어가지 않음
    # script 태그 자체는 escape 됨
    assert "&lt;script&gt;" in html
    # data-tts 속성에 JSON 페이로드 존재
    assert 'data-tts="' in html
    # onclick 핸들러 + SpeechSynthesisUtterance + ko-KR
    assert "speechSynthesis" in html
    assert "SpeechSynthesisUtterance" in html
    assert "ko-KR" in html


def test_tts_button_returns_empty_for_empty_text():
    from ui import board_v2
    assert board_v2._tts_button_html("") == ""
    assert board_v2._tts_button_html("   ") == ""


def test_tts_button_label_is_escaped():
    from ui import board_v2
    html = board_v2._tts_button_html("hi", label='<bad label>')
    # 라벨도 escape
    assert "&lt;bad label&gt;" in html
    assert "<bad label>" not in html


def test_tts_disabled_html_has_disabled_attr():
    from ui import board_v2
    html = board_v2._tts_disabled_html()
    assert "disabled" in html
    assert "음성으로 듣기" in html


# ── _brief_html — tts_btn 키 ────────────────────────────────

def test_brief_html_includes_tts_button_when_items_exist():
    from ui import board_v2
    news = pd.DataFrame([{
        "title": "AI 비전 검사 도입",
        "summary": "도장 검사 자동화",
        "keywords": "AI, 비전",
        "source": "naver",
        "link": "https://x.com/1",
        "collected_at": "2026-05-31T06:00:00+00:00",
        "content": "내용",
    }])
    matches = pd.DataFrame([{
        "link": "https://x.com/1",
        "news_title": "AI 비전 검사 도입",
        "score": 0.9,
    }])
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_matches", return_value=matches):
        board_v2._brief_html.clear()
        brief = board_v2._brief_html()

    assert "tts_btn" in brief
    btn = brief["tts_btn"]
    assert btn  # 비어있지 않음
    assert "data-tts" in btn
    assert "speechSynthesis" in btn
    # 본문 안에 뉴스 제목이 JSON-encoded 로 들어가야
    assert "AI" in btn


def test_brief_html_empty_state_returns_disabled_tts_button():
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame()):
        board_v2._brief_html.clear()
        brief = board_v2._brief_html()
    assert "tts_btn" in brief
    btn = brief["tts_btn"]
    assert "disabled" in btn
    assert "speechSynthesis" not in btn  # disabled 버튼은 핸들러 없음


# ── 매트릭스 detail TTS ────────────────────────────────────

def _synthetic_cells():
    return pd.DataFrame([
        {"dept": "도장1팀", "lv3": "비전 검사", "cell_score": 95.0,
         "matched_news": 40, "matched_tasks": 18,
         "sample_tasks": "AI 막두께 검사", "sample_news": "AI 자동",
         "sample_objectives": ""},
    ])


def test_matrix_detail_includes_tts_button():
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        board_v2._board_matrix_html.clear()
        html = board_v2._board_matrix_html()

    # 매트릭스 detail TTS 버튼
    assert "db-mx-tts" in html
    assert "data-tts" in html
    # CTA 와 함께 노출
    assert "db-mx-detail-actions" in html
    assert "제안서 작업장에서 보기" in html
    # disabled 자취 없음
    assert "disabled" not in html
    # ko-KR 음성
    assert "ko-KR" in html


def test_matrix_detail_tts_payload_includes_selected_cell_info():
    """detail 패널 TTS 페이로드에 dept/lv3/점수가 포함된다."""
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        board_v2._board_matrix_html.clear()
        html = board_v2._board_matrix_html()

    # data-tts 속성에서 페이로드 추출 (JSON 인코딩)
    import re
    m = re.search(r'class="db-mx-tts"[^>]+data-tts="([^"]+)"', html)
    assert m
    # HTML escape 된 JSON
    raw = m.group(1).replace("&quot;", '"').replace("&amp;", "&")
    text = _json.loads(raw)
    assert "도장1팀" in text
    assert "비전 검사" in text
    assert "95" in text  # 점수


# ── 템플릿 placeholder 치환 ────────────────────────────────

def test_board_template_has_brief_tts_placeholder():
    """board_main.html 에 {{BRIEF_TTS_BTN}} 자리가 있어야 한다."""
    from pathlib import Path
    from config import ASSETS_DIR
    template = (ASSETS_DIR / "v2" / "screens" / "board_main.html").read_text(encoding="utf-8")
    assert "{{BRIEF_TTS_BTN}}" in template
    # 이전 disabled 버튼 사라짐
    assert "TTS 미구현" not in template
    assert "음성으로 듣기 · 준비 중" not in template

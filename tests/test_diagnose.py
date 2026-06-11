"""scraping.diagnose — 기사 URL 단계별 진단 (mock 세션) + 🔬 진단 카드 UI."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scraping import diagnose as diag


_ARTICLE_HTML = """
<html><head><meta property="og:image" content="/photo.jpg"></head><body>
  <script>noise()</script>
  <div id="article_main">
    이번 발표에서 회사는 비전 AI 기반 용접 검사 시스템을 공개했다.
    해당 기술은 6축 매니퓰레이터와 결합해 검사 시간을 30% 단축한다.
    현장 적용은 가공·조립 공정에서 우선 진행된다.
    <img src="/body_photo.jpg">
  </div>
</body></html>
"""

_SOFT_BLOCK_HTML = """
<html><head><title>안내</title></head><body>
  <div class="msg">잘못된 접근입니다. 접근 권한이 없습니다.</div>
</body></html>
"""


class _FakeResp:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _ScriptedSession:
    """기사 URL 요청만 순서대로 스크립트된 응답을 주고, 홈(origin) 워밍업은 200."""

    def __init__(self, article_resps: list[_FakeResp]):
        self._resps = list(article_resps)
        self.calls: list[str] = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if url.endswith("/") and "?" not in url:  # 홈 워밍업
            return _FakeResp("<html>home</html>")
        if self._resps:
            return self._resps.pop(0)
        return _FakeResp("Forbidden", status=403)


_URL = "https://www.thebell.co.kr/front/newsview.asp?key=1"


# ── diagnose() — 요청 3단계 ─────────────────────────────────────

def test_diagnose_blocked_then_impersonation_succeeds():
    """①403 → ②403 → ③TLS 위장 200: 단계별 상태가 기록되고 본문 분석까지 간다."""
    sess = _ScriptedSession([_FakeResp("Forbidden", status=403)] * 10)
    with patch.object(diag, "fetch_impersonated", return_value=_FakeResp(_ARTICLE_HTML)), \
         patch("scraping.enrich.fetch_impersonated", return_value=_FakeResp(_ARTICLE_HTML)):
        rep = diag.diagnose(_URL, session=sess)

    s1, s2, s3 = rep["steps"]
    assert (s1["name"], s1["status"], s1["ok"]) == ("basic", 403, False)
    assert (s2["name"], s2["status"], s2["ok"]) == ("warmup", 403, False)
    assert (s3["name"], s3["status"], s3["ok"]) == ("impersonate", 200, True)
    assert rep["fetched"] is True and rep["all_blocked"] is False
    # 본문 분석: thebell 셀렉터 매칭 + 메타/본문 이미지 후보
    assert rep["content_selector"]["selector"] == "div#article_main"
    assert rep["content_selector"]["length"] >= 80
    assert "비전 AI" in rep["content_selector"]["preview"]
    assert any(c["url"] == "/photo.jpg" for c in rep["meta_images"])
    assert any(c["url"] == "/body_photo.jpg" and c["attr"] == "src"
               for c in rep["body_images"])
    # 최종 파이프라인도 위장 폴백으로 본문 확보
    assert rep["final"]["content_len"] > 0
    assert "비전 AI" in rep["final"]["content_preview"]
    assert rep["soft_block_suspect"] is False


def test_diagnose_all_blocked_without_curl_cffi():
    """①②③ 전부 실패(위장 폴백 None) → all_blocked + ③ 단계 에러 메시지."""
    sess = _ScriptedSession([_FakeResp("Forbidden", status=403)] * 10)
    with patch.object(diag, "fetch_impersonated", return_value=None), \
         patch.object(diag, "curl_cffi_available", return_value=False):
        rep = diag.diagnose(_URL, session=sess)

    assert rep["fetched"] is False and rep["all_blocked"] is True
    assert rep["curl_cffi_available"] is False
    assert "미설치" in rep["steps"][2]["error"]
    assert rep["final"]["content_len"] == 0  # 본문 분석 단계로 안 넘어감


def test_diagnose_detects_soft_block_200():
    """200 인데 본문 셀렉터 0 + 짧은 텍스트 + 차단 문구 → soft_block_suspect."""
    sess = _ScriptedSession([_FakeResp(_SOFT_BLOCK_HTML), _FakeResp(_SOFT_BLOCK_HTML)])
    rep = diag.diagnose(_URL, session=sess)

    assert rep["steps"][0]["status"] == 200 and rep["steps"][0]["ok"] is True
    assert rep["steps"][1]["skipped"] is True and rep["steps"][2]["skipped"] is True
    assert rep["content_selector"] is None
    assert rep["soft_block_suspect"] is True
    reasons = " / ".join(rep["soft_block_reasons"])
    assert "본문 셀렉터 0개" in reasons
    assert "잘못된 접근" in reasons or "접근 권한" in reasons
    assert f"< {diag.SOFT_BLOCK_TEXT_LEN}자" in reasons


def test_diagnose_normal_article_no_suspect():
    """정상 200 기사: ① 한 번으로 끝(②③ 생략), 셀렉터 매칭, 의심 플래그 없음."""
    sess = _ScriptedSession([_FakeResp(_ARTICLE_HTML), _FakeResp(_ARTICLE_HTML)])
    rep = diag.diagnose(_URL, session=sess)

    assert rep["steps"][0]["ok"] is True
    assert rep["steps"][1]["skipped"] is True and rep["steps"][2]["skipped"] is True
    assert rep["soft_block_suspect"] is False and rep["all_blocked"] is False
    assert rep["content_selector"]["selector"] == "div#article_main"
    assert rep["final"]["content_len"] > 0
    assert rep["final"]["image_url"].endswith("/photo.jpg")


def test_diagnose_request_exception_recorded_as_step_error():
    """요청 예외(망 차단 등)는 단계 error 로 기록되고 진단은 죽지 않는다."""
    class BoomSession:
        def get(self, url, headers=None, timeout=None):
            raise ConnectionError("Host not in allowlist")

    with patch.object(diag, "fetch_impersonated", return_value=None):
        rep = diag.diagnose(_URL, session=BoomSession())

    assert rep["all_blocked"] is True
    assert "ConnectionError" in rep["steps"][0]["error"]
    assert "ConnectionError" in rep["steps"][1]["error"]


# ── UI — 🔬 진단 카드 (pending 플래그 + 결과 렌더) ───────────────

_UI_KEYS = ("_sc_diag_pending", "sc_diag_url", "sc_diag_result")


@pytest.fixture(autouse=True)
def _reset_ui_state():
    import streamlit as st
    for k in _UI_KEYS:
        st.session_state.pop(k, None)
    yield
    for k in _UI_KEYS:
        st.session_state.pop(k, None)


def test_consume_diag_pending_runs_diagnose_once():
    """pending 플래그 1회 소비 → diagnose() 호출 → 결과 세션 저장."""
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_sc_diag_pending"] = True
    st.session_state["sc_diag_url"] = "https://example.com/a"
    fake = {"steps": [], "fetched": True}
    with patch("scraping.diagnose.diagnose", return_value=fake) as mock_d:
        assert dm._consume_diag_pending_if_any() is True
    mock_d.assert_called_once_with("https://example.com/a")
    assert st.session_state["sc_diag_result"] == fake
    # pending 은 1회 소비 — 재호출 시 noop (실 네트워크 재호출 방지)
    with patch("scraping.diagnose.diagnose") as mock_d2:
        assert dm._consume_diag_pending_if_any() is False
    mock_d2.assert_not_called()


def test_consume_diag_pending_rejects_non_http_url():
    """URL 미입력/비 http 면 네트워크 호출 없이 에러 결과만 저장."""
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_sc_diag_pending"] = True
    st.session_state["sc_diag_url"] = "thebell"
    with patch("scraping.diagnose.diagnose") as mock_d:
        assert dm._consume_diag_pending_if_any() is True
    mock_d.assert_not_called()
    assert "URL" in st.session_state["sc_diag_result"]["error"]


def test_consume_diag_pending_absorbs_exception():
    """diagnose() 예외도 에러 결과로 흡수 — 설정 화면이 죽지 않는다."""
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_sc_diag_pending"] = True
    st.session_state["sc_diag_url"] = "https://example.com/a"
    with patch("scraping.diagnose.diagnose", side_effect=RuntimeError("boom")):
        assert dm._consume_diag_pending_if_any() is True
    assert "RuntimeError" in st.session_state["sc_diag_result"]["error"]


def test_diag_step_md_colors_and_escapes():
    """단계 1줄 markdown — 성공 초록/차단 빨강/생략 회색, 라벨 escape."""
    from ui import data_management_v2 as dm

    ok = dm._diag_step_md({"label": "① 기본 요청", "status": 200, "ok": True,
                           "skipped": False, "error": None, "length": 12345})
    assert ":green[**HTTP 200**]" in ok and "12,345자" in ok
    blocked = dm._diag_step_md({"label": "① 기본 요청", "status": 403, "ok": False,
                                "skipped": False, "error": None, "length": 10})
    assert ":red[**HTTP 403**]" in blocked
    skipped = dm._diag_step_md({"label": "② 워밍업", "skipped": True})
    assert ":gray[" in skipped
    err = dm._diag_step_md({"label": "<b>x</b>", "status": None, "ok": False,
                            "skipped": False, "error": "ConnectionError: <bad>",
                            "length": 0})
    assert "<b>" not in err and "&lt;b&gt;" in err  # escape
    assert "&lt;bad&gt;" in err and ":red[**실패**]" in err


def test_settings_view_renders_diagnose_card():
    """⚙ 수집 설정 서브뷰(AppTest)에 진단 카드(URL 입력 + 실행 버튼)가 뜬다."""
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona

    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["app_area"] = "🗞 뉴스 수집"
    at.session_state["sc_collect_view"] = "settings"
    at.run()
    assert not at.exception
    md = "\n".join(m.proto.body for m in at.get("markdown"))
    assert "기사 URL 진단" in md
    assert any(b.key == "_sc_diag_btn" for b in at.get("button"))
    assert any(t.key == "sc_diag_url" for t in at.get("text_input"))

"""persona.derive — LLM 관심사 추출(폴백/캐시) + 작업정의 토큰 매칭."""
from __future__ import annotations

import json
from unittest.mock import patch

from persona import derive
from persona.schema import Persona
from sola.client import LLMNotConfigured


def _persona() -> Persona:
    return Persona(
        dept="도장1팀", job="품질 검사관",
        interest_lv3=["도장 검사"],
        interest_keywords=["비전 검사", "막두께 측정"],
    )


# ── profile_text / 파서 ──────────────────────────────────────

def test_profile_text_contains_input_fields():
    text = derive.profile_text(_persona())
    assert "도장1팀" in text
    assert "품질 검사관" in text
    assert "비전 검사" in text
    assert derive.profile_text(Persona()) == ""


def test_parse_llm_keywords_handles_commas_and_noise():
    raw = "비전 AI, 용접 로봇 · 디지털 트윈\n- MES, 비전 AI"
    out = derive._parse_llm_keywords(raw)
    assert out == ["비전 AI", "용접 로봇", "디지털 트윈", "MES"]
    assert derive._parse_llm_keywords("") == []


# ── extract_interests — LLM / 캐시 / 폴백 ────────────────────

def test_extract_interests_llm_path_and_cache():
    p = _persona()
    with patch.object(derive, "_call_llm", return_value="비전 AI, 도막 측정, 결함 판독") as m:
        kws, source = derive.extract_interests(p)
    assert source == "llm"
    assert kws == ["비전 AI", "도막 측정", "결함 판독"]
    assert m.call_count == 1

    # 같은 프로필 재호출 → 캐시 히트 (LLM 미호출)
    with patch.object(derive, "_call_llm", return_value="다른 결과") as m2:
        kws2, source2 = derive.extract_interests(p)
    assert source2 == "cache"
    assert kws2 == kws
    assert m2.call_count == 0


def test_extract_interests_fallback_when_llm_not_configured():
    p = _persona()
    with patch.object(derive, "_call_llm", side_effect=LLMNotConfigured("no key")):
        kws, source = derive.extract_interests(p)
    assert source == "fallback"
    # 폴백 = 입력 항목 그대로 (관심 키워드 우선)
    assert kws[0] == "비전 검사"
    assert "막두께 측정" in kws
    assert "도장 검사" in kws


def test_extract_interests_empty_profile_returns_empty():
    kws, source = derive.extract_interests(Persona())
    assert kws == []
    assert source == "fallback"


def test_extract_interests_force_skips_cache():
    p = _persona()
    with patch.object(derive, "_call_llm", return_value="첫 결과"):
        derive.extract_interests(p)
    with patch.object(derive, "_call_llm", return_value="새 결과") as m:
        kws, source = derive.extract_interests(p, use_cache=False)
    assert m.call_count == 1
    assert source == "llm"
    assert kws == ["새 결과"]


# ── match_task_defs — 작업정의 토큰 매칭 ─────────────────────

def _seed_task_def(process_id: str, process: str, task: str, text: str = "") -> None:
    from store import task_defs_db
    obj = {
        "process_id": process_id,
        "org_meta": {"team": "자동화팀", "dept": "도장1팀",
                     "process": process, "task": task},
    }
    task_defs_db.upsert(process_id, json.dumps(obj, ensure_ascii=False),
                        task_def_text=text, source="test")


def test_match_task_defs_ranks_matching_process():
    _seed_task_def("P-1", "도장 검사", "막두께 측정", "비전 검사 기반 도막 두께 판독")
    _seed_task_def("P-2", "용접", "백킹재 부착", "수동 용접 보조")

    out = derive.match_task_defs(["비전 검사", "막두께 측정"])
    assert out, "매칭 결과가 비어있으면 안 됨"
    top = out[0]
    assert top["process"] == "도장 검사"
    assert "막두께 측정" in top["tasks"]
    assert top["score"] > 0
    assert "비전 검사" in top["matched"]
    # 용접 공정은 비전/막두께 관심사와 무관 → 미포함 또는 하위
    procs = [m["process"] for m in out]
    assert procs[0] != "용접"


def test_match_task_defs_empty_inputs():
    assert derive.match_task_defs([]) == []
    # 작업정의 DB 가 비어 있으면 빈 추천
    assert derive.match_task_defs(["비전 검사"]) == []


# ── derive_and_store — persona 갱신·영구 저장 ────────────────

def test_derive_and_store_saves_derived_fields():
    from persona import store as persona_store
    p = _persona()
    persona_store.save(p)
    _seed_task_def("P-1", "도장 검사", "막두께 측정", "비전 검사 기반 도막 두께 판독")

    with patch.object(derive, "_call_llm", side_effect=LLMNotConfigured("no key")):
        updated = derive.derive_and_store(p)

    assert updated.derived_interests
    assert updated.derived_source == "fallback"
    assert updated.derived_at
    assert updated.matched_processes
    assert updated.matched_processes[0]["process"] == "도장 검사"

    loaded = persona_store.load()
    assert loaded.derived_interests == updated.derived_interests
    assert loaded.matched_processes == updated.matched_processes


def test_derive_and_store_swallows_unexpected_errors():
    """분석 실패가 프로필 저장 흐름을 깨지 않는다 — 기존 persona 반환."""
    p = _persona()
    with patch.object(derive, "extract_interests", side_effect=RuntimeError("boom")):
        out = derive.derive_and_store(p)
    assert out is p
    assert out.derived_source == ""

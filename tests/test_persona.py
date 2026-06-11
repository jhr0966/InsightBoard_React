"""persona — 스키마/저장/컨텍스트 테스트."""
from __future__ import annotations

from persona import context, store
from persona.schema import Persona


def test_persona_is_set_and_label():
    p = Persona()
    assert p.is_set() is False
    assert p.label() == "(미설정)"

    p2 = Persona(dept="가공부", job="용접 담당")
    assert p2.is_set() is True
    assert "가공부" in p2.label() and "용접 담당" in p2.label()


def test_persona_to_dict_and_from_dict():
    p = Persona(name="홍길동", team="가공팀", dept="가공부",
                job="용접 담당", interest_lv3=["B/up", "형강"], interest_tasks=["사상"])
    d = p.to_dict()
    p2 = Persona.from_dict(d)
    assert p == p2


def test_persona_roundtrip_with_keywords_and_derived_fields():
    p = Persona(
        name="홍길동", dept="가공부", job="용접 담당",
        interest_keywords=["용접 로봇", "비전 검사"],
        derived_interests=["용접 자동화", "AI 결함 판독"],
        matched_processes=[{"process": "용접", "tasks": ["사상"], "score": 1.5,
                            "matched": ["용접 로봇"]}],
        derived_at="2026-06-10T00:00:00+00:00",
        derived_source="fallback",
    )
    p2 = Persona.from_dict(p.to_dict())
    assert p == p2
    assert p2.interest_keywords == ["용접 로봇", "비전 검사"]
    assert p2.matched_processes[0]["process"] == "용접"


def test_persona_from_dict_backward_compat_old_json():
    """구버전 profile.json(신규 키 없음)도 기본값으로 로드된다."""
    old = {"name": "A", "team": "", "dept": "가공부", "job": "용접",
           "interest_lv3": ["전처리"], "interest_tasks": [], "muted_keywords": []}
    p = Persona.from_dict(old)
    assert p.dept == "가공부"
    assert p.interest_keywords == []
    assert p.derived_interests == []
    assert p.matched_processes == []
    assert p.derived_at == ""
    assert p.derived_source == ""


def test_parse_keywords_input_splits_comma_newline_and_dedups():
    from persona.schema import parse_keywords_input
    out = parse_keywords_input("용접 로봇, 비전 검사\n디지털 트윈 · 용접 로봇;  ,")
    assert out == ["용접 로봇", "비전 검사", "디지털 트윈"]
    assert parse_keywords_input("") == []
    assert parse_keywords_input("   ,\n  ") == []


def test_persona_store_roundtrip(tmp_path):
    # conftest 가 DATA_ROOT 를 tmp 로 패치함
    p = Persona(name="A", dept="가공부", job="용접 담당", interest_lv3=["전처리"])
    saved_path = store.save(p)
    assert saved_path.exists()

    loaded = store.load()
    assert loaded == p


def test_persona_store_load_missing_returns_default():
    store.reset()
    loaded = store.load()
    assert loaded == Persona()
    assert loaded.is_set() is False


def test_persona_context_empty_when_unset():
    assert context.system_block(Persona()) == ""


def test_persona_context_includes_fields():
    p = Persona(dept="가공부", job="용접 담당", interest_lv3=["B/up"])
    block = context.system_block(p)
    assert "가공부" in block
    assert "용접 담당" in block
    assert "B/up" in block
    assert "사용자 페르소나" in block


def test_persona_context_includes_keywords_and_derived():
    p = Persona(
        dept="가공부",
        interest_keywords=["용접 로봇"],
        derived_interests=["AI 결함 판독"],
        matched_processes=[{"process": "용접", "tasks": [], "score": 1.0}],
    )
    block = context.system_block(p)
    assert "관심 키워드" in block and "용접 로봇" in block
    assert "SOLA 분석 관심사" in block and "AI 결함 판독" in block
    assert "연관 공정(분석)" in block and "용접" in block

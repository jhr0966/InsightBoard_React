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

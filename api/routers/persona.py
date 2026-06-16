"""페르소나 API — `persona.store`/`persona.derive` 위임.

GET/PUT 프로필 + POST /derive(SOLA LLM 분석, 룰 폴백). 사이드바 페르소나 카드·
페르소나 설정 화면·온보딩이 소비.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from persona import derive as persona_derive
from persona import store as persona_store
from persona.schema import Persona

router = APIRouter(prefix="/api/persona", tags=["persona"])


class PersonaModel(BaseModel):
    name: str = ""
    team: str = ""
    dept: str = ""
    job: str = ""
    interest_lv3: list[str] = Field(default_factory=list)
    interest_tasks: list[str] = Field(default_factory=list)
    interest_keywords: list[str] = Field(default_factory=list)
    muted_keywords: list[str] = Field(default_factory=list)
    derived_interests: list[str] = Field(default_factory=list)
    matched_processes: list[dict[str, Any]] = Field(default_factory=list)
    derived_at: str = ""
    derived_source: str = ""
    # 파생 표시용(읽기 전용)
    label: str = ""
    is_set: bool = False


def _out(p: Persona) -> PersonaModel:
    d = p.to_dict()
    d["label"] = p.label()
    d["is_set"] = p.is_set()
    return PersonaModel(**d)


class PersonaIn(BaseModel):
    name: str = ""
    team: str = ""
    dept: str = ""
    job: str = ""
    interest_lv3: list[str] = Field(default_factory=list)
    interest_tasks: list[str] = Field(default_factory=list)
    interest_keywords: list[str] = Field(default_factory=list)
    muted_keywords: list[str] = Field(default_factory=list)


@router.get("", response_model=PersonaModel)
def get_persona() -> PersonaModel:
    return _out(persona_store.load())


@router.put("", response_model=PersonaModel)
def put_persona(body: PersonaIn) -> PersonaModel:
    # 기존 파생 결과는 유지하고 입력 필드만 갱신.
    cur = persona_store.load()
    merged = cur.to_dict()
    merged.update(body.model_dump())
    p = Persona.from_dict(merged)
    persona_store.save(p)
    return _out(p)


@router.post("/derive", response_model=PersonaModel)
def derive_persona() -> PersonaModel:
    p = persona_store.load()
    updated = persona_derive.derive_and_store(p, force=True)
    return _out(updated)


@router.post("/reset", response_model=PersonaModel)
def reset_persona() -> PersonaModel:
    persona_store.reset()
    return _out(persona_store.load())

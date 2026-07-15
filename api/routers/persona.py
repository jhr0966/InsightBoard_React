"""페르소나 API — `persona.store`/`persona.derive` 위임.

GET/PUT 프로필 + POST /derive(SOLA LLM 분석, 룰 폴백). 사이드바 페르소나 카드·
페르소나 설정 화면·온보딩이 소비.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import Identity, current_identity
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
def get_persona(identity: Identity = Depends(current_identity)) -> PersonaModel:
    return _out(persona_store.load(identity.user_id))


@router.put("", response_model=PersonaModel)
def put_persona(body: PersonaIn, identity: Identity = Depends(current_identity)) -> PersonaModel:
    # 기존 파생 결과는 유지하고 입력 필드만 갱신. 사용자별 프로필(Step 10).
    cur = persona_store.load(identity.user_id)
    merged = cur.to_dict()
    merged.update(body.model_dump())
    p = Persona.from_dict(merged)
    persona_store.save(p, user=identity.user_id)
    return _out(p)


@router.post("/derive", response_model=PersonaModel)
def derive_persona(identity: Identity = Depends(current_identity)) -> PersonaModel:
    p = persona_store.load(identity.user_id)
    updated = persona_derive.derive_and_store(p, force=True, user=identity.user_id)
    return _out(updated)


@router.post("/reset", response_model=PersonaModel)
def reset_persona(identity: Identity = Depends(current_identity)) -> PersonaModel:
    persona_store.reset(identity.user_id)
    return _out(persona_store.load(identity.user_id))

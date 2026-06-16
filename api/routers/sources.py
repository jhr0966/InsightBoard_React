"""뉴스 수집 출처 설정 API — `store.sources` 위임.

기본 출처(toggle) + 커스텀 RSS(추가/제거). 수집 설정 화면이 소비.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from store import sources

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceItem(BaseModel):
    name: str
    enabled: bool
    custom: bool = False
    url: str | None = None


class SourcesOut(BaseModel):
    items: list[SourceItem]


class CustomIn(BaseModel):
    name: str
    url: str


@router.get("", response_model=SourcesOut)
def list_sources() -> SourcesOut:
    disabled = sources.disabled_set()
    items = [SourceItem(name=n, enabled=n not in disabled) for n in sources.DEFAULT_SOURCES]
    for c in sources.custom_sources():
        items.append(SourceItem(name=c.name, enabled=c.name not in disabled, custom=True, url=c.url))
    return SourcesOut(items=items)


@router.post("/{name}/toggle", response_model=SourcesOut)
def toggle_source(name: str) -> SourcesOut:
    sources.toggle_disabled(name)
    return list_sources()


@router.post("", response_model=SourcesOut, status_code=201)
def add_source(body: CustomIn) -> SourcesOut:
    try:
        sources.add_custom(body.name, body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return list_sources()


@router.delete("/{name}", response_model=SourcesOut)
def delete_source(name: str) -> SourcesOut:
    if not sources.remove_custom(name):
        raise HTTPException(status_code=404, detail=f"custom source not found: {name}")
    return list_sources()

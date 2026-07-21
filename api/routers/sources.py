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


class SourceHealth(BaseModel):
    name: str
    enabled: bool
    custom: bool = False
    count_7d: int = 0
    last_collected: str = ""
    status: str = "정상"  # 정상 | 무수집 | 비활성


# 출처 표시명 → 기사 매칭. 네이버/구글은 source 코드, AI Times 등 tech 사이트는
# source="tech" 묶음이라 press(사이트명)로 구분, 커스텀은 source==name.
_SOURCE_CODE = {"네이버 뉴스": "naver", "구글 뉴스": "google"}
_PRESS_SITES = {"AI Times"}


def _source_stats(news, name: str) -> tuple[int, str]:
    """출처별 최근 뉴스 건수 + 마지막 수집 시각."""
    if news is None or news.empty:
        return 0, ""
    if name in _SOURCE_CODE and "source" in news.columns:
        sub = news[news["source"] == _SOURCE_CODE[name]]
    elif name in _PRESS_SITES and "press" in news.columns:
        sub = news[news["press"] == name]
    elif "source" in news.columns:
        sub = news[news["source"] == name]   # 커스텀 RSS
    else:
        return 0, ""
    if sub.empty:
        return 0, ""
    col = "collected_at" if "collected_at" in sub.columns else "date"
    last = max((str(v) for v in sub[col].tolist() if str(v).strip()), default="")
    return int(len(sub)), last


@router.get("/health", response_model=list[SourceHealth])
def sources_health(days: int = 7) -> list[SourceHealth]:
    """출처별 최근 N일 수집 건수·마지막 수집·상태 배지(수집 설정 화면).

    Streamlit `_src_status_html` 이식 — 출처 행에 OK/무수집/비활성을 표시.
    """
    from store import news_db

    news = news_db.load_news_for_days(days)
    disabled = sources.disabled_set()
    names = list(sources.DEFAULT_SOURCES) + [c.name for c in sources.custom_sources()]
    custom_names = {c.name for c in sources.custom_sources()}
    out: list[SourceHealth] = []
    for n in names:
        enabled = n not in disabled
        cnt, last = _source_stats(news, n)
        status = "비활성" if not enabled else ("무수집" if cnt == 0 else "정상")
        out.append(SourceHealth(name=n, enabled=enabled, custom=n in custom_names,
                                count_7d=cnt, last_collected=last, status=status))
    return out


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

"""뉴스 article dict 리스트 ↔ 일자별 Parquet 저장소.

조회(load_*) 반환 계약 — 결정적 최신순:
  모든 조회 결과는 `sort_at` 내림차순 + `link` 오름차순(tie-break)으로 정렬된다.
  `sort_at` 은 저장 컬럼이 아니라 로드 시 계산되는 **파생 컬럼**:
      sort_at = published_at 정규화값 → collected_at 정규화값 → 일자 디렉토리 날짜
  정규화는 혼재 포맷(ISO±offset·'Z'·RFC822·date-only)을 UTC ISO8601 로 통일한다.
  파싱이 전부 실패한 행도 목록에서 제거하지 않고 맨 뒤에 남긴다.
  → 다운스트림의 `head(limit)` 이 항상 "가장 최신 기사"를 취함을 보장.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

from config import NEWS_DIR
from store.paths import latest_parquet, news_dir_for

logger = logging.getLogger(__name__)


_ARTICLE_COLS = (
    "title", "press", "date", "published_at", "link",
    "summary", "keywords", "source", "query",
    # M4-α enrich 컬럼 — 본문/대표 이미지/LLM 키워드·요약/타임스탬프
    "content", "image_url", "keywords_llm", "summary_llm", "enriched_at",
    # 단일 '수집 시각' — 저장 시점에 enriched_at→published_at 폴백으로 채운다
    # (board 데일리 브리핑·정렬이 이 컬럼을 읽는다). 과거 parquet 엔 없어 빈값.
    "collected_at",
)

_NULLISH = {"", "nan", "none", "nat", "<na>"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%SZ")


# ── 시각 정규화 (파생 컬럼 sort_at·published_at_norm) ──────────────────
# 스크레이퍼 출력이 소스마다 다르다: google/rss 는 원문 offset(+09:00) 유지,
# naver/tech 는 UTC, 과거 데이터·date 필드는 RFC822/date-only/빈값 혼재.
# 문자열 그대로는 사전순 ≠ 시간순이라, 전부 UTC ISO8601 로 통일해야 정렬 가능.
_TS_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y.%m.%d")


def _parse_ts(val) -> datetime | None:
    """혼재 포맷 타임스탬프 → aware UTC datetime. 실패 시 None."""
    s = str(val or "").strip()
    if not s or s.lower() in _NULLISH:
        return None
    dt: datetime | None = None
    try:  # ISO 8601 ('Z' 접미 포함) — 스크레이퍼 표준 출력
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    if dt is None:
        try:  # RFC 822 — 과거 데이터의 date/pubDate 원문
            dt = parsedate_to_datetime(s)
        except (TypeError, ValueError):
            dt = None
    if dt is None:
        for fmt in _TS_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        # naive 는 UTC 로 간주 — 스크레이퍼의 naive 출력(extract·date-only)이 UTC 기준.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _norm_ts(val) -> str:
    """혼재 포맷 → UTC ISO8601 문자열(초 단위). 실패 시 ''."""
    dt = _parse_ts(val)
    return dt.replace(microsecond=0).isoformat() if dt else ""


def _with_sort_at(df: pd.DataFrame, *, fallback_day: str = "") -> pd.DataFrame:
    """파생 컬럼 `published_at_norm`·`sort_at` 계산 (저장하지 않음 — 로드 시 항상 재계산).

    sort_at 폴백 체인: published_at_norm → collected_at 정규화 → fallback_day
    (일자 디렉토리 날짜, UTC 자정). 셋 다 없으면 '' — 목록에서 사라지지 않고
    정렬 시 맨 뒤로 간다.
    """
    if df.empty:
        df["published_at_norm"] = pd.Series(dtype=str)
        df["sort_at"] = pd.Series(dtype=str)
        return df
    day_iso = f"{fallback_day}T00:00:00+00:00" if fallback_day else ""
    pub = df["published_at"].map(_norm_ts)
    col = df["collected_at"].map(_norm_ts)
    df["published_at_norm"] = pub
    df["sort_at"] = pub.where(pub != "", col).where((pub != "") | (col != ""), day_iso)
    return df


def _sorted_latest(df: pd.DataFrame) -> pd.DataFrame:
    """결정적 최신순 — sort_at 내림차순, 동률은 link 오름차순(안정 tie-break)."""
    if df.empty or "sort_at" not in df.columns:
        return df.reset_index(drop=True)
    return df.sort_values(
        ["sort_at", "link"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)


def _first_ts(row: dict) -> str:
    """collected_at 정규화 — collected_at→enriched_at→published_at 중 첫 비어있지 않은 값."""
    for key in ("collected_at", "enriched_at", "published_at"):
        val = str(row.get(key, "") or "").strip()
        if val.lower() not in _NULLISH:
            return val
    return ""


def _to_df(articles: list[dict]) -> pd.DataFrame:
    if not articles:
        return pd.DataFrame(columns=list(_ARTICLE_COLS))
    df = pd.DataFrame(articles)
    for col in _ARTICLE_COLS:
        if col not in df.columns:
            df[col] = ""
    df["collected_at"] = df.apply(_first_ts, axis=1)
    # fillna 로 None/NaN → "" (astype(str) 가 'nan'/'None' 문자열을 만들지 않게).
    return df[list(_ARTICLE_COLS)].fillna("").astype(str)


def save_articles(articles: list[dict], *, source: str) -> Path | None:
    """오늘자 디렉토리에 source 별 Parquet로 저장. 빈 리스트는 저장 안 함."""
    if not articles:
        return None
    df = _to_df(articles)
    path = news_dir_for() / f"{source}_{_utc_stamp()}.parquet"
    df.to_parquet(path, index=False)
    return path


def _normalize_loaded(df: pd.DataFrame, *, day: str = "") -> pd.DataFrame:
    """과거 스키마(컬럼 부족) Parquet 도 신규 컬럼을 빈값으로 채워 안전.

    `day`(일자 디렉토리 이름 YYYY-MM-DD)는 시각이 전무한 과거 레코드의
    sort_at 최후 폴백으로 쓰인다.
    """
    for col in _ARTICLE_COLS:
        if col not in df.columns:
            df[col] = ""
    # 과거 parquet 의 NaN 도 "" 로 — 다운스트림 `if image_url:` 가 'nan' 문자열에
    # 속지 않게(C2). collected_at 없던 과거 데이터는 빈값으로 남는다(정렬 시 뒤로).
    return _with_sort_at(df[list(_ARTICLE_COLS)].fillna(""), fallback_day=day)


def _empty_frame() -> pd.DataFrame:
    return _with_sort_at(pd.DataFrame(columns=list(_ARTICLE_COLS)))


def load_latest(source: str | None = None) -> pd.DataFrame:
    """가장 최근 일자 디렉토리의 source(또는 전체) Parquet 로드."""
    today_dir = news_dir_for()
    pattern = f"{source}_*.parquet" if source else "*.parquet"
    latest = latest_parquet(today_dir, pattern)
    if not latest:
        return _empty_frame()
    return _normalize_loaded(pd.read_parquet(latest), day=today_dir.name)


def load_all_today() -> pd.DataFrame:
    """오늘자 디렉토리의 모든 Parquet 합본 — 결정적 최신순(모듈 docstring 계약)."""
    today = news_dir_for().name
    df = _load_day_frame(today)
    if df is None or df.empty:
        return _empty_frame()
    return _sorted_latest(df.drop_duplicates(subset=["link"], keep="last"))


# 디스크 재읽기 캐시 2단 — (개선 백로그 #2 → 리팩토링: 일자별 dedup)
#  · _day_frame_memo: 일자 디렉토리 1개 → DataFrame. (mtime_ns, parquet 수) 시그니처.
#    윈도우(days=3/7/14/30/56…)가 서로 달라도 **같은 날짜 parquet 은 한 번만 읽는다**
#    — 보드 한 렌더가 3·14·30·56일 윈도우를 섞어 불러도 디스크 I/O 는 일자당 1회.
#  · _news_window_memo: (days) 윈도우 → concat+dedup 결과. 시그니처 동일 시 재결합 생략.
# 새 수집(parquet 추가/변경) 시 두 캐시 모두 시그니처 불일치로 자동 무효화(stale 없음).
_day_frame_memo: dict[str, tuple[tuple, pd.DataFrame]] = {}
_news_window_memo: dict = {}


def _day_sig(day_dir: Path) -> tuple | None:
    """일자 디렉토리 시그니처 (mtime_ns, parquet 수). 없으면 None."""
    try:
        return (day_dir.stat().st_mtime_ns, len(list(day_dir.glob("*.parquet"))))
    except OSError:
        return None


def _load_day_frame(d: str) -> pd.DataFrame | None:
    """일자 디렉토리 1개의 parquet 합본(메모이즈). 디렉토리 없으면 None.

    반환 객체는 캐시 공유본 — 내부 호출 전용이며 호출부는 변형 없이 concat/파생만 한다.
    """
    day_dir = NEWS_DIR / d
    sig = _day_sig(day_dir)
    if sig is None:
        return None
    cached = _day_frame_memo.get(d)
    if cached is not None and cached[0] == sig:
        return cached[1]
    frames: list[pd.DataFrame] = []
    for p in sorted(day_dir.glob("*.parquet")):
        try:
            frames.append(_normalize_loaded(pd.read_parquet(p), day=d))
        except Exception:  # noqa: BLE001 — 깨진 parquet 은 스킵(어느 파일인지 로깅)
            logger.warning("깨진 parquet 스킵: %s", p, exc_info=True)
            continue
    df = _empty_frame() if not frames else pd.concat(frames, ignore_index=True)
    _day_frame_memo[d] = (sig, df)
    return df


def _day_dirs_sig(days: int, cur: datetime) -> tuple:
    """최근 `days` 일 디렉토리의 (날짜, mtime_ns, parquet 수) — 변하면 캐시 무효."""
    parts: list[tuple] = []
    for i in range(days):
        d = (cur - timedelta(days=i)).strftime("%Y-%m-%d")
        sig = _day_sig(NEWS_DIR / d)
        if sig is None:
            continue  # 없는 날 → 스킵
        parts.append((d, *sig))
    return tuple(parts)


def load_news_for_days(days: int = 7, *, now: datetime | None = None) -> pd.DataFrame:
    """오늘 포함 최근 `days` 일치 일자 디렉토리의 모든 Parquet 합본.

    Args:
        days: 1 이상. `days=1` 이면 오늘만(= `load_all_today` 와 동등).
        now: 테스트용 시점 주입 (UTC).

    각 일자 디렉토리는 `data/news/YYYY-MM-DD/`. 존재하지 않으면 스킵.
    중복 link 는 마지막(=최신 저장 시점) 항목 보존. 디스크 읽기는 일자별 메모
    (`_day_frame_memo`)로 dedup — 윈도우 길이가 달라도 같은 날짜는 1회만 읽는다.
    결과는 윈도우 시그니처가 동일하면 메모이즈본을 `.copy()` 로 반환(호출부의
    in-place 변형으로부터 캐시 보호).

    반환 순서는 **결정적 최신순**(sort_at desc, link asc — 모듈 docstring 계약).
    dedup(keep="last") 은 정렬 **전에** 로드 순서(과거→오늘·파일명순) 기준으로
    수행한다 — "나중 저장본(enrich 보강본) 우선" 의미론 유지.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    cur = now or datetime.now(timezone.utc)

    key = (str(NEWS_DIR), days)
    sig = _day_dirs_sig(days, cur)
    cached = _news_window_memo.get(key)
    if cached is not None and cached[0] == sig:
        return cached[1].copy()

    frames: list[pd.DataFrame] = []
    # 과거 → 오늘 순으로 쌓는다 — drop_duplicates(keep="last") 가 **가장 최근 저장본**
    # (예: refresh_articles 가 오늘 디렉토리에 upsert 한 과거 기사 보강본)을 남기게.
    # 직전엔 오늘 → 과거 순이라 과거 일자 원본이 보강본을 가렸다.
    for i in reversed(range(days)):
        d = (cur - timedelta(days=i)).strftime("%Y-%m-%d")
        day_df = _load_day_frame(d)
        if day_df is not None and not day_df.empty:
            frames.append(day_df)
    result = (
        _empty_frame() if not frames
        else _sorted_latest(
            pd.concat(frames, ignore_index=True).drop_duplicates(subset=["link"], keep="last")
        )
    )
    _news_window_memo[key] = (sig, result)
    return result.copy()


def upsert_articles(articles: list[dict], *, source: str) -> Path | None:
    """enrich 후 갱신된 article dict 리스트를 동일 파일명 규칙으로 새로 저장.

    중복 link 는 (저장 시점 기준 최신) article 로 덮어쓰기 효과 — 별도 파일로 추가되지만
    load_all_today 의 drop_duplicates(subset=['link']) 에서 마지막 항목이 남음.
    """
    return save_articles(articles, source=source)

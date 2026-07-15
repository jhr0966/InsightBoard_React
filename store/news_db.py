"""뉴스 article dict 리스트 ↔ 일자별 Parquet 저장소.

기사 식별·중복 병합 계약 (Step 2 `feat-article-identity`):
  조회 결과에는 파생 컬럼 `article_id`(정규화 URL 해시, `store/article_id.py`)가
  붙는다. 같은 `article_id` 의 중복 레코드는 **행 단위 승자 선택이 아니라
  필드 단위 병합**(`_merge_duplicates`, MERGE_VERSION)으로 하나가 된다 —
  한 레코드의 정확한 게시시각과 다른 레코드의 풍부한 본문·이미지를 모두 보존.
  원본 parquet 은 변형하지 않는다(병합은 로드 시 파생 — 언제든 재실행 가능).

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
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

from config import NEWS_DIR
from store.article_id import article_id as _article_id
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


# 필드 단위 병합 정책 버전 — 규칙 변경 시 +1 (docs/INVARIANTS.md I-15).
MERGE_VERSION = 1


def _with_identity(df: pd.DataFrame) -> pd.DataFrame:
    """파생 컬럼 `article_id` 계산 (원본 link 는 그대로 보존)."""
    if df.empty:
        df["article_id"] = pd.Series(dtype=str)
        return df
    df["article_id"] = df["link"].map(_article_id)
    return df


def _longest(values: list[str]) -> str:
    """비어 있지 않은 값 중 가장 긴 것 (없으면 '')."""
    best = ""
    for v in values:
        if len(v) > len(best):
            best = v
    return best


def _last_nonempty(values: list[str]) -> str:
    for v in reversed(values):
        if v:
            return v
    return ""


def _merge_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """같은 article_id 레코드들을 **필드 단위**로 병합 (MERGE_VERSION=1).

    행 단위 승자 선택(keep="last")은 '정확한 게시시각을 가진 레코드'와 '본문이
    풍부한 레코드'가 다를 때 정보를 잃는다 → 필드별 규칙으로 합친다:

      published_at(_norm)  가장 이른 저장본의 비어 있지 않은 원문 게시시각
      collected_at         가장 최근 수집시각 (정규화 비교)
      content / summary / keywords   비어 있지 않은 값 중 가장 풍부한(긴) 값
      image_url            가장 나중 저장본의 비어 있지 않은 값 (enrich 보강 우선)
      summary_llm / keywords_llm / enriched_at   가장 나중의 정상(비어 있지 않은) 결과
      나머지(title·press·source·query·link 등)   가장 나중 저장본(대표 레코드) 기준
      merged_record_count / original_urls        병합 메타 (파생 컬럼)

    link 가 비어 article_id 가 없는 행은 병합하지 않고 그대로 남긴다(유실 금지).
    입력 순서 = 로드 순서(과거→오늘·파일명순) 가정 — "나중 = 최신 저장본".
    """
    if df.empty:
        df["merged_record_count"] = pd.Series(dtype=int)
        df["original_urls"] = pd.Series(dtype=str)
        return df
    ids = df["article_id"].tolist()
    # 빈 id(링크 없음)는 행마다 고유 키 — 절대 서로 합쳐지지 않는다.
    keys = [aid if aid else f"__row{i}" for i, aid in enumerate(ids)]
    if len(set(keys)) == len(keys):  # 중복 없음 — 빠른 경로
        df = df.copy()
        df["merged_record_count"] = 1
        df["original_urls"] = df["link"]
        return df

    order: list[str] = []
    groups: dict[str, list[dict]] = {}
    for key, rec in zip(keys, df.to_dict("records")):
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(rec)

    merged_rows: list[dict] = []
    for key in order:
        rows = groups[key]
        if len(rows) == 1:
            row = dict(rows[0])
            row["merged_record_count"] = 1
            row["original_urls"] = str(row.get("link") or "")
            merged_rows.append(row)
            continue
        cols = {c: [str(r.get(c) or "") for r in rows] for c in rows[0]}
        out = dict(rows[-1])  # 대표 = 가장 나중 저장본
        # 원문 게시시각 — 가장 이른 저장본의 비어 있지 않은 값(원본이 정확).
        for i, v in enumerate(cols["published_at_norm"]):
            if v:
                out["published_at_norm"] = v
                out["published_at"] = cols["published_at"][i]
                break
        # 수집시각 — 정규화 비교로 최신.
        col_norm = [(_norm_ts(v), v) for v in cols["collected_at"]]
        out["collected_at"] = max(col_norm)[1] if any(n for n, _ in col_norm) else ""
        out["content"] = _longest(cols["content"])
        out["summary"] = _longest(cols["summary"])
        out["keywords"] = _longest(cols["keywords"])
        out["image_url"] = _last_nonempty(cols["image_url"])
        out["summary_llm"] = _last_nonempty(cols["summary_llm"])
        out["keywords_llm"] = _last_nonempty(cols["keywords_llm"])
        out["enriched_at"] = _last_nonempty(cols["enriched_at"])
        # sort_at 재산출 — 병합된 published/collected 기준(둘 다 없으면 그룹 max 유지).
        out["sort_at"] = (out.get("published_at_norm")
                          or _norm_ts(out.get("collected_at"))
                          or max(cols["sort_at"]))
        out["merged_record_count"] = len(rows)
        seen_links = list(dict.fromkeys(v for v in cols["link"] if v))
        out["original_urls"] = "|".join(seen_links)
        merged_rows.append(out)
    return pd.DataFrame(merged_rows)


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
    """오늘자 디렉토리에 source 별 Parquet로 저장. 빈 리스트는 저장 안 함.

    파일명에 uuid 접미사 — 같은 source 를 같은 초에 두 번 저장해도 앞선
    파일을 덮어쓰지 않는다(초 해상도 타임스탬프 충돌 → 기사 유실 버그).
    중복 기사는 로드 시 article_id 필드 병합(I-15)이 처리하므로 파일이
    늘어나는 것은 무해하다.
    """
    if not articles:
        return None
    df = _to_df(articles)
    path = news_dir_for() / f"{source}_{_utc_stamp()}_{uuid.uuid4().hex[:8]}.parquet"
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
    return _with_identity(_with_sort_at(df[list(_ARTICLE_COLS)].fillna(""), fallback_day=day))


def _empty_frame() -> pd.DataFrame:
    df = _with_identity(_with_sort_at(pd.DataFrame(columns=list(_ARTICLE_COLS))))
    df["merged_record_count"] = pd.Series(dtype=int)
    df["original_urls"] = pd.Series(dtype=str)
    return df


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
    return _sorted_latest(_merge_duplicates(df))


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
    같은 article_id(정규화 URL) 중복은 **필드 단위 병합**(`_merge_duplicates`) —
    enrich 보강본의 본문·이미지와 원본의 게시시각을 모두 보존. 디스크 읽기는
    일자별 메모(`_day_frame_memo`)로 dedup — 윈도우 길이가 달라도 같은 날짜는
    1회만 읽는다. 결과는 윈도우 시그니처가 동일하면 메모이즈본을 `.copy()` 로
    반환(호출부의 in-place 변형으로부터 캐시 보호).

    반환 순서는 **결정적 최신순**(sort_at desc, link asc — 모듈 docstring 계약).
    병합은 정렬 **전에** 로드 순서(과거→오늘·파일명순) 기준으로 수행한다 —
    "나중 저장본 = 최신"이라는 필드 병합 규칙의 전제.
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
        else _sorted_latest(_merge_duplicates(pd.concat(frames, ignore_index=True)))
    )
    _news_window_memo[key] = (sig, result)
    return result.copy()


def upsert_articles(articles: list[dict], *, source: str) -> Path | None:
    """enrich 후 갱신된 article dict 리스트를 동일 파일명 규칙으로 새로 저장.

    중복 link 는 (저장 시점 기준 최신) article 로 덮어쓰기 효과 — 별도 파일로 추가되지만
    load_all_today 의 drop_duplicates(subset=['link']) 에서 마지막 항목이 남음.
    """
    return save_articles(articles, source=source)

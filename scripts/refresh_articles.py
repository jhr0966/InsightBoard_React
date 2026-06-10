"""저장된 기사 일괄 재-enrich — 본문이 비었거나 노이즈(짧음/코드 잔재)인 기사,
대표 이미지가 없는 기사를 다시 fetch 해 **content/image_url 만** 채운다.
LLM 은 호출하지 않는다 — keywords_llm/summary_llm 등 나머지 컬럼은 원본 그대로.

Usage:
  python scripts/refresh_articles.py [--days 30] [--dry-run] [--limit N]

동작:
  ① store.news_db.load_news_for_days(days) 로 최근 N일 합본 로드
  ② 후보 선별 — enrich.content_needs_refresh(content) 이거나 image_url 이 빈 row
     (link 없는 row 는 fetch 불가 → 후보 제외, 요약에 별도 카운트)
  ③ --dry-run 이면 선별 결과만 출력하고 종료 (fetch/저장 없음)
  ④ 후보마다 scraping.enrich.fetch_article(link) — 네트워크 fetch 만, LLM 없음
  ⑤ 갱신은 '필요했던 필드'에 한해, fetch 결과가 비어있지 않을 때만:
     본문이 필요했고 fetch 본문이 비어있지 않으면 content 교체,
     이미지가 없었고 fetch 이미지가 비어있지 않으면 image_url 교체.
     (멀쩡한 기존 본문을 fetch 결과로 덮지 않는다 — 안전 우선)
  ⑥ 갱신된 row 를 source 별로 묶어 news_db.upsert_articles(...) 로 저장.
     row dict 는 **전 컬럼**을 그대로 담는다 — load 의 link 중복 제거(keep="last")
     에서 갱신본이 원본을 대체하므로 부분 dict 로 저장하면 다른 컬럼이 유실된다.

⚠ 알려진 한계 (news_db upsert 의미론 — 이 스크립트 밖):
  upsert 는 **오늘자** 디렉토리에 새 parquet 을 추가한다. '최신이 이긴다'는
  같은 일자 디렉토리 안(파일명 타임스탬프 정렬 → keep="last")에서만 보장된다.
  원본이 과거 일자 디렉토리에 있는 기사는 load_news_for_days 의 concat 순서
  (오늘→과거) + keep="last" 때문에 다일 윈도우 조회에서 과거 row 가 남는다.
  즉 오늘 수집된 기사 재-enrich(일일 cron 직후 보강)에는 완전하고, 과거 기사는
  저장은 되지만 다일 윈도우에 반영되지 않을 수 있다 (수정은 store/news_db.py 몫).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 레포 루트

import pandas as pd

from scraping import enrich
from scraping.http import build_session
from store import news_db

# parquet 직렬화 잔재 — store.news_db._NULLISH 와 동일 기준(빈값 취급 문자열)
_NULLISH = {"", "nan", "none", "nat", "<na>"}


def _is_blank(value) -> bool:
    """None/NaN 및 'nan'/'None' 같은 직렬화 잔재 문자열까지 빈값으로 취급."""
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return True
    except Exception:
        pass
    return str(value).strip().lower() in _NULLISH


def _row_to_record(row) -> dict:
    """pandas row → 전 컬럼 str dict (NaN → ''). upsert 시 컬럼 유실 방지."""
    rec: dict = {}
    for k, v in row.items():
        rec[str(k)] = "" if _is_blank(v) else str(v)
    return rec


def _refresh_reason(rec: dict) -> str:
    """후보 사유 — '본문' / '이미지' / '본문+이미지' / '' (후보 아님)."""
    reasons = []
    if enrich.content_needs_refresh(rec.get("content", "")):
        reasons.append("본문")
    if _is_blank(rec.get("image_url", "")):
        reasons.append("이미지")
    return "+".join(reasons)


def select_candidates(df) -> tuple[list[tuple[dict, str]], int]:
    """뉴스 df → ([(row dict, 사유)], link 없는 후보 수).

    후보 = content_needs_refresh(content) 이거나 image_url 빈 row.
    link 가 http 로 시작하지 않으면 fetch 불가 → 후보에서 제외하고 카운트만.
    """
    out: list[tuple[dict, str]] = []
    no_link = 0
    if df is None or df.empty:
        return out, no_link
    for _, row in df.iterrows():
        rec = _row_to_record(row)
        reason = _refresh_reason(rec)
        if not reason:
            continue
        if not rec.get("link", "").startswith("http"):
            no_link += 1
            continue
        out.append((rec, reason))
    return out, no_link


def _fmt_img(rec: dict) -> str:
    return "무" if _is_blank(rec.get("image_url", "")) else "유"


def refresh_records(targets: list[tuple[dict, str]], *, session=None) -> dict:
    """후보 리스트를 순회하며 fetch → 필드 갱신. LLM 호출 없음.

    Returns:
      {"updated": [갱신 rec], "ok": n, "skip": n, "fail": n}
    """
    sess = session or build_session()
    updated: list[dict] = []
    ok = skip = fail = 0
    for rec, reason in targets:
        link = rec.get("link", "")
        old_len = len(rec.get("content", ""))
        try:
            fetched = enrich.fetch_article(link, session=sess)
        except Exception as e:  # noqa: BLE001 — 1건 실패가 배치를 못 죽이게
            fail += 1
            print(f"[FAIL] {type(e).__name__}: {e} · {link[:90]}")
            continue
        changed = False
        if "본문" in reason and (fetched.get("content") or "").strip():
            rec["content"] = str(fetched["content"])
            changed = True
        if "이미지" in reason and (fetched.get("image_url") or "").strip():
            rec["image_url"] = str(fetched["image_url"])
            changed = True
        if changed:
            ok += 1
            updated.append(rec)
            print(f"[OK  ] {reason:>6s} 본문 {old_len}→{len(rec.get('content', ''))}자 "
                  f"· 이미지 {_fmt_img(rec)} · {link[:90]}")
        else:
            skip += 1
            print(f"[SKIP] {reason:>6s} fetch 빈 결과(본문 {old_len}자 유지) · {link[:90]}")
    return {"updated": updated, "ok": ok, "skip": skip, "fail": fail}


def persist_updates(updated: list[dict]) -> dict[str, int]:
    """갱신 rec 들을 source 별로 묶어 news_db.upsert_articles 로 저장.

    Returns: {source: 저장 건수}
    """
    by_source: dict[str, list[dict]] = {}
    for rec in updated:
        src = rec.get("source", "") or "unknown"
        by_source.setdefault(src, []).append(rec)
    saved: dict[str, int] = {}
    for src, rows in sorted(by_source.items()):
        path = news_db.upsert_articles(rows, source=src)
        saved[src] = len(rows)
        print(f"      저장: {src} {len(rows)}건 → {path}")
    return saved


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="저장된 기사 일괄 재-enrich (본문/이미지만, LLM 없음)")
    parser.add_argument("--days", type=int, default=30,
                        help="조회 윈도우(일). 기본 30")
    parser.add_argument("--dry-run", action="store_true",
                        help="선별 결과만 출력 — fetch/저장 안 함")
    parser.add_argument("--limit", type=int, default=None,
                        help="처리 최대 건수 (기본: 전부)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.days < 1:
        print("--days 는 1 이상이어야 합니다.")
        return 2

    df = news_db.load_news_for_days(days=args.days)
    candidates, no_link = select_candidates(df)
    print(f"최근 {args.days}일 기사 {len(df)}건 → 재-enrich 후보 {len(candidates)}건"
          + (f" (link 없어 제외 {no_link}건)" if no_link else ""))
    if not candidates:
        return 0

    targets = candidates[: args.limit] if args.limit else candidates
    if len(targets) != len(candidates):
        print(f"--limit {args.limit} → {len(targets)}건만 처리")

    if args.dry_run:
        for rec, reason in targets:
            print(f"[대상] {reason:>6s} 본문 {len(rec.get('content', ''))}자 "
                  f"· 이미지 {_fmt_img(rec)} · {rec.get('source', '') or '?'} "
                  f"· {rec.get('link', '')[:90]}")
        print(f"dry-run: {len(targets)}건 선별만 — fetch/저장 안 함")
        return 0

    result = refresh_records(targets)
    saved = persist_updates(result["updated"])
    print(f"완료: 갱신 {result['ok']} · 변화없음 {result['skip']} · 실패 {result['fail']}"
          + (f" · 저장 {sum(saved.values())}건/{len(saved)}소스" if saved else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

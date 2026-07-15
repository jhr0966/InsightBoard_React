"""기사 → 적용 사례 추출 배치 (개편 Step 12, 계획 §14).

수집 과정에서 **동기 실행하지 않는다** — 실행 경로는 links 인덱싱과 동일 원칙:
  ① 일일 cron(`scripts/daily_scrape.py`) 말미  ② 관리자 `POST /api/cases/extract`.
실패 복구: 기사 단위 격리(한 건 실패가 배치를 안 깨움), 시도한 기사는
cases_db 에 기록(사례 아님 포함)되어 재실행 시 중복 LLM 호출이 없다(멱등).

후보 선정: 최근 N일 기사 중 ①본문 확보(사례 판별에 본문 필요) ②작업과 매칭
(links 존재 — 조선소 작업과 무관한 기사는 사례화 가치 낮음) ③미추출 순으로
links 점수 상위 `limit` 건만 — LLM 비용 상한.
"""
from __future__ import annotations

import json
import logging
import re

from sola.client import LLMNotConfigured, chat
from sola.prompts import CASE_EXTRACT_VERSION, SYSTEM_CASE_EXTRACT
from store import cases_db, taxonomy

logger = logging.getLogger(__name__)

_BODY_MIN = 200          # 본문이 이보다 짧으면 사례 판별 신뢰 불가 → 후보 제외
_BODY_MAX = 3500         # LLM 입력 캡
_CONF_MIN = 0.5          # 이 미만 확신도는 저장하지 않음(잡음 방지)


def _parse_json(text: str) -> dict | None:
    """LLM 출력에서 JSON 오브젝트 파싱 — 코드펜스·앞뒤 잡음 허용."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def extract_one(article: dict) -> dict | None:
    """기사 1건 → 사례 dict(저장 형식) 또는 None(사례 아님/실패).

    LLMNotConfigured 는 호출부로 전파(배치가 전체 skip 판단).
    """
    body = str(article.get("content") or "")[:_BODY_MAX]
    user = (f"[제목] {article.get('title', '')}\n"
            f"[언론사] {article.get('press', '')}\n"
            f"[본문]\n{body}")
    reply = chat(
        messages=[{"role": "system", "content": SYSTEM_CASE_EXTRACT},
                  {"role": "user", "content": user}],
        temperature=0.1, max_tokens=900,
    )
    obj = _parse_json(reply)
    if obj is None:
        logger.warning("사례 추출 JSON 파싱 실패: %s", article.get("link"))
        return None
    if not obj.get("is_case") or float(obj.get("confidence", 0) or 0) < _CONF_MIN:
        return None
    # 기술 태깅 — LLM 기술명 + 기사 텍스트를 taxonomy alias 로 ID 수렴(§10: 문자열 금지).
    tech_text = " ".join([str(t) for t in (obj.get("technologies") or [])]
                         + [str(article.get("title", "")), body[:500]])
    effects = []
    for e in (obj.get("quantified_effects") or []):
        if isinstance(e, dict) and str(e.get("evidence_text", "")).strip():
            effects.append({"metric": str(e.get("metric", "")),
                            "value": str(e.get("value", "")),
                            "evidence_text": str(e.get("evidence_text", ""))})
    aid = str(article.get("article_id", ""))
    return {
        "case": {
            "case_id": cases_db.case_id_for_article(aid),
            "title": str(obj.get("title") or article.get("title", "")),
            "industry": str(obj.get("industry", "")),
            "target_work": str(obj.get("target_work", "")),
            "problem": str(obj.get("problem", "")),
            "solution": str(obj.get("solution", "")),
            "technology_ids": taxonomy.tag_text(tech_text),
            "implementation": str(obj.get("implementation", "")),
            "quantified_effects": effects,
            "shipyard_implications": str(obj.get("shipyard_implications", "")),
            "confidence": float(obj.get("confidence", 0) or 0),
            "review_status": "pending_review",
            "extract_version": CASE_EXTRACT_VERSION,
        },
        "sources": [{
            "article_id": aid, "link": str(article.get("link", "")),
            "title": str(article.get("title", "")),
            # 수치 효과가 있으면 원문 구절(source_fact), 없으면 시스템 요약.
            "evidence_text": (effects[0]["evidence_text"] if effects
                              else str(obj.get("solution", ""))[:200]),
            "evidence_type": "source_fact" if effects else "system_summary",
        }],
    }


def extract_batch(days: int = 7, limit: int = 10) -> dict:
    """후보 선정 → 기사별 추출 → 저장. 요약 dict 반환 (cron·관리자 API 공용)."""
    from roadmap import query as roadmap_query
    from store import links_db, news_db

    news = news_db.load_news_for_days(days)
    if news.empty:
        return {"attempted": 0, "extracted": 0, "reason": "뉴스 없음"}
    roadmap = roadmap_query.load_latest()
    links = (links_db.matches_for_window(news, roadmap, days=days)
             if not roadmap.empty else None)
    # 후보: links 점수 상위 기사(작업 연관) → 본문 확보 → 미추출.
    scored: dict[str, float] = {}
    if links is not None and not links.empty:
        for r in links.to_dict("records"):
            aid = str(r.get("article_id", ""))
            scored[aid] = max(scored.get(aid, 0.0), float(r.get("score", 0) or 0))
    done = cases_db.extracted_article_ids()
    candidates = []
    for rec in news.to_dict("records"):
        aid = str(rec.get("article_id", ""))
        if aid in done or len(str(rec.get("content") or "")) < _BODY_MIN:
            continue
        if scored and aid not in scored:
            continue  # 작업과 무관한 기사는 후보 제외(links 있을 때만 적용)
        candidates.append((scored.get(aid, 0.0), rec))
    candidates.sort(key=lambda x: -x[0])
    candidates = candidates[:limit]

    attempted = extracted = failed = 0
    for _, rec in candidates:
        attempted += 1
        aid = str(rec.get("article_id", ""))
        try:
            result = extract_one(rec)
        except LLMNotConfigured:
            return {"attempted": attempted - 1, "extracted": extracted,
                    "reason": "LLM 미설정 — 사례 추출 생략"}
        except Exception:  # noqa: BLE001 — 기사 단위 격리
            logger.warning("사례 추출 실패: %s", rec.get("link"), exc_info=True)
            failed += 1
            continue
        if result is None:
            cases_db.mark_non_case(aid)   # 재시도 낭비 방지
            continue
        cases_db.upsert_case(result["case"], result["sources"])
        extracted += 1
    return {"attempted": attempted, "extracted": extracted, "failed": failed,
            "extract_version": CASE_EXTRACT_VERSION}

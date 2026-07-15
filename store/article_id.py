"""기사 식별 — URL 정규화(canonical_url) + 안정적 article_id.

설계 원칙 (Step 2 `feat-article-identity`):
- **원본 URL 은 절대 변형·유실하지 않는다** — 정규화는 식별 계산에만 쓰고,
  저장·표시·링크 이동은 전부 원본 `link` 를 쓴다.
- **보수적 정규화**: 명백한 추적 파라미터(utm_*·fbclid·gclid 등)만 제거한다.
  기사 식별에 쓰일 수 있는 파라미터(articleId·id·idx·idxno·newsId·seq 등)는
  **기본 유지** — 전체 쿼리 제거는 서로 다른 기사를 잘못 합치므로 금지.
- **버전 관리**: 규칙이 바뀌면 `IDENTITY_VERSION` 을 올린다 — article_id 파생
  데이터(후속 article_task_links 등)는 이 버전으로 stale 판정·재빌드한다.
- **도메인별 확장**: `DOMAIN_RULES` 에 도메인 전용 제거/유지 규칙을 추가할 수 있다.
"""
from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 정규화 규칙 버전 — 규칙 변경 시 반드시 +1 (파생 데이터 재빌드 트리거).
IDENTITY_VERSION = 1

# 제거해도 안전한 **추적 전용** 파라미터 (광고·분석·공유 경로 식별용 — 기사 식별과 무관).
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_brand", "fbclid", "gclid", "dclid", "msclkid", "igshid",
    "mc_cid", "mc_eid", "ref", "cmpid", "ncid", "sr_share", "share",
})

# 도메인별 예외 규칙 — {"drop": 추가로 제거할 파라미터, "keep_only": 이것만 유지}.
# 예) 특정 언론사가 세션 토큰을 쿼리에 실을 때 여기서 제거. 필요 시 확장.
DOMAIN_RULES: dict[str, dict[str, frozenset[str]]] = {}


def canonical_url(url: str) -> str:
    """식별용 정규화 URL. 실패/빈값이면 원문 그대로(strip) 반환.

    변환: 스킴·호스트 소문자화, 기본 포트 제거, fragment 제거, 추적 파라미터
    제거(그 외 파라미터는 유지·정렬), 경로 끝 `/` 정리(루트 제외).
    """
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    if not parts.scheme or not parts.netloc:
        return raw

    scheme = parts.scheme.lower()
    host = parts.netloc.lower()
    if (scheme == "http" and host.endswith(":80")) or (
            scheme == "https" and host.endswith(":443")):
        host = host.rsplit(":", 1)[0]

    domain = host.split("@")[-1].split(":")[0]
    rules = DOMAIN_RULES.get(domain, {})
    drop = _TRACKING_PARAMS | rules.get("drop", frozenset())
    keep_only = rules.get("keep_only")

    pairs = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in drop and (keep_only is None or k in keep_only)
    ]
    # 파라미터 순서만 다른 동일 기사가 같은 ID 가 되도록 정렬(결정성).
    query = urlencode(sorted(pairs))

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"

    return urlunsplit((scheme, host, path, query, ""))


def article_id(url: str) -> str:
    """정규화 URL 기반 안정 식별자 (md5 16hex). 빈 URL 은 ''.

    md5 는 보안 목적이 아니라 **안정 해시**로만 쓴다(짧고 결정적).
    """
    canon = canonical_url(url)
    if not canon:
        return ""
    return hashlib.md5(canon.encode("utf-8")).hexdigest()[:16]

"""기사 1건 수집 진단 — 어느 단계에서 본문/사진이 빠지는지 구조화 리포트.

`scripts/diagnose_article.py`(CLI)와 ⚙ 수집 설정의 '🔬 기사 URL 진단' 카드(UI)가
공유하는 단계 로직. 실 네트워크 호출이므로 호출부는 반드시 명시적 사용자 액션
(CLI 실행 / 진단 버튼)으로만 트리거한다.

리포트 단계:
  ① 기본 요청(브라우저 헤더) → ② 홈 워밍업+강화 헤더 → ③ TLS 위장(curl_cffi)
  ④ 메타 이미지 후보 ⑤ 본문 img 후보 ⑥ 본문 셀렉터 매칭 ⑥-b 구조화 데이터
  ⑦ 최종 fetch_article 결과 + 200 위장 차단(soft block) 휴리스틱
"""
from __future__ import annotations

from urllib.parse import urlparse

from scraping import enrich
from scraping.extract import is_junk_image, soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers, fetch_impersonated


# 200 인데 본문이 사실상 빈 '위장 차단' 페이지로 의심하는 가시 텍스트 길이 기준.
SOFT_BLOCK_TEXT_LEN = 500

# WAF/anti-bot 차단 페이지가 흔히 싣는 문구(소문자 비교).
_BLOCK_PHRASES = (
    "잘못된 접근", "비정상적인 접근", "접근 권한", "권한이 없", "접근이 거부",
    "차단되었", "captcha", "access denied", "request blocked", "robot",
    "are you human", "cloudflare",
)


def curl_cffi_available() -> bool:
    """TLS 지문 위장 폴백(curl_cffi, 선택 의존성) 설치 여부."""
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        return False
    return True


def _new_step(name: str, label: str) -> dict:
    return {"name": name, "label": label, "status": None, "length": 0,
            "ok": False, "skipped": False, "error": None}


def _try_get(step: dict, fn) -> str:
    """요청 1회 실행 → step dict 채우고, 성공(<400)이면 응답 text 반환."""
    try:
        resp = fn()
        step["status"] = resp.status_code
        step["length"] = len(getattr(resp, "text", "") or "")
        if resp.status_code < 400:
            step["ok"] = True
            return resp.text or ""
    except Exception as e:  # noqa: BLE001 — 진단은 모든 실패를 리포트로 흡수
        step["error"] = f"{type(e).__name__}: {e}"
    return ""


def _meta_image_candidates(soup) -> list[dict]:
    """④ og:image 계열 메타 후보 + junk 판정."""
    out: list[dict] = []
    for sel in enrich._IMAGE_SELECTORS:
        tag = soup.select_one(sel)
        if not tag:
            continue
        val = (tag.get("content") or tag.get("href") or "").strip()
        if val:
            out.append({"selector": sel, "url": val, "junk": is_junk_image(val)})
    return out


def _body_image_candidates(soup, limit: int = 5) -> list[dict]:
    """⑤ 본문 img 후보 상위 N — src/lazy 속성 출처 + junk 판정."""
    out: list[dict] = []
    for img in soup.find_all("img"):
        src = enrich._img_src_from_attrs(img)
        if not src:
            continue
        attr = next((a for a in enrich._IMAGE_ATTR_ORDER if (img.get(a) or "").strip()),
                    "srcset")
        out.append({"attr": attr, "url": src, "junk": is_junk_image(src)})
        if len(out) >= limit:
            break
    return out


def _content_selector_match(text: str) -> dict | None:
    """⑥ 본문 셀렉터 매칭 — 첫 매칭 셀렉터명·텍스트 길이·첫 80자. 미매칭이면 None."""
    work = soup_of(text)
    enrich._strip_noise(work)
    for sel in enrich._CONTENT_SELECTORS:
        tag = work.select_one(sel)
        if not tag:
            continue
        t = enrich._text_from_tag(tag)
        if len(t) >= enrich._MIN_CONTENT_LEN:
            return {"selector": sel, "length": len(t), "preview": t[:80]}
    return None


def _soft_block_reasons(text: str, soup, selector_hit: bool, status: int | None) -> list[str]:
    """200 위장 차단 휴리스틱 — 응답은 200 인데 본문 셀렉터 0 + (짧은 텍스트 또는
    차단 문구) 면 의심 사유 목록을 돌려준다. 의심 없으면 빈 리스트."""
    if status != 200 or selector_hit:
        return []
    reasons: list[str] = []
    visible = soup.get_text(" ", strip=True)
    if len(visible) < SOFT_BLOCK_TEXT_LEN:
        reasons.append(f"가시 텍스트 {len(visible)}자 < {SOFT_BLOCK_TEXT_LEN}자")
    lowered = text.lower()
    hits = [p for p in _BLOCK_PHRASES if p in lowered]
    if hits:
        reasons.append("차단 문구 감지: " + ", ".join(hits))
    if not reasons:
        return []
    return ["본문 셀렉터 0개 매칭(HTTP 200)"] + reasons


def diagnose(url: str, *, session=None) -> dict:
    """기사 URL 1건을 단계별 진단해 구조화 dict 로 반환. (실 네트워크 호출)

    Returns:
      url, curl_cffi_available: bool,
      steps: [{name,label,status,length,ok,skipped,error}, ...] (①②③),
      fetched: bool — 어느 단계든 HTML 확보 여부,
      all_blocked: bool — ①~③ 전부 실패(IP 대역 차단 의심),
      soft_block_suspect: bool / soft_block_reasons: [str] — 200 위장 차단,
      meta_images / body_images: 이미지 후보 + junk 판정,
      content_selector: {selector,length,preview} | None,
      structured: {ldjson_len, fusion_len},
      final: {content_len, content_preview, image_url} — fetch_article 파이프라인 결과.
    """
    sess = session or build_session()
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}/"
    report: dict = {
        "url": url,
        "curl_cffi_available": curl_cffi_available(),
        "steps": [],
        "fetched": False,
        "all_blocked": False,
        "soft_block_suspect": False,
        "soft_block_reasons": [],
        "meta_images": [],
        "body_images": [],
        "content_selector": None,
        "structured": {"ldjson_len": 0, "fusion_len": 0},
        "final": {"content_len": 0, "content_preview": "", "image_url": ""},
    }

    # ① 기본 요청 (브라우저 헤더 + same-origin referer)
    s1 = _new_step("basic", "① 기본 요청")
    text = _try_get(s1, lambda: sess.get(
        url, headers=default_headers(referer=origin), timeout=REQUEST_TIMEOUT))
    report["steps"].append(s1)

    # ② 홈 워밍업(쿠키) + 강화 헤더 재시도 — ① 실패 시에만
    s2 = _new_step("warmup", "② 워밍업+강화 헤더")
    if text:
        s2["skipped"] = True
    else:
        def _warmup_get():
            try:
                sess.get(origin, headers=enrich._full_browser_headers(),
                         timeout=REQUEST_TIMEOUT)
            except Exception:  # noqa: BLE001 — 워밍업 실패는 무시, 본 요청이 본질
                pass
            return sess.get(url, headers=enrich._full_browser_headers(
                referer="https://search.naver.com/"), timeout=REQUEST_TIMEOUT)
        text = _try_get(s2, _warmup_get)
    report["steps"].append(s2)

    # ③ TLS 지문 위장(curl_cffi) — ②까지 실패 시에만
    s3 = _new_step("impersonate", "③ TLS 위장(curl_cffi)")
    if text:
        s3["skipped"] = True
    else:
        imp = fetch_impersonated(url, referer="https://search.naver.com/")
        if imp is None:
            s3["error"] = ("curl_cffi 미설치 — pip install curl_cffi"
                           if not report["curl_cffi_available"] else "위장 요청 실패")
        else:
            s3["status"] = imp.status_code
            s3["length"] = len(getattr(imp, "text", "") or "")
            if imp.status_code < 400:
                s3["ok"] = True
                text = imp.text or ""
    report["steps"].append(s3)

    report["fetched"] = bool(text)
    if not text:
        report["all_blocked"] = True
        return report

    soup = soup_of(text)
    report["meta_images"] = _meta_image_candidates(soup)
    report["body_images"] = _body_image_candidates(soup)
    report["content_selector"] = _content_selector_match(text)
    report["structured"] = {
        "ldjson_len": len(enrich._ldjson_article_body(soup)),
        "fusion_len": len(enrich._arc_fusion_body(text)),
    }

    # 200 위장 차단(soft block) — 마지막으로 status 가 찍힌 단계 기준.
    last_status = next((s["status"] for s in reversed(report["steps"])
                        if s["status"] is not None), None)
    reasons = _soft_block_reasons(text, soup, report["content_selector"] is not None,
                                  last_status)
    report["soft_block_suspect"] = bool(reasons)
    report["soft_block_reasons"] = reasons

    # ⑦ 최종 파이프라인 — 실제 fetch_article 이 내놓는 본문/이미지.
    art = enrich.fetch_article(url, session=sess)
    report["final"] = {
        "content_len": len(art["content"]),
        "content_preview": art["content"][:120],
        "image_url": art["image_url"],
    }
    return report

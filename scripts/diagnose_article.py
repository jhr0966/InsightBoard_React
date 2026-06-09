"""기사 1건 수집 진단 — 어느 단계에서 본문/사진이 빠지는지 단계별 리포트.

샌드박스가 아닌 **실제 망이 열린 환경**(로컬/배포 서버)에서 실행해, 특정 사이트
(thebell·slist 등)가 왜 본문·사진을 못 가져오는지 원인을 좁힌다.

Usage:
  python scripts/diagnose_article.py <기사URL>

리포트 항목:
  ① 기본 요청(브라우저 헤더) HTTP 상태
  ② 차단 시: 홈 워밍업 + 강화 헤더 재시도 상태
  ③ 차단 시: TLS 지문 위장(curl_cffi) 상태
  ④ og:image 계열 메타 후보 + junk 판정
  ⑤ 본문 img 후보 상위 5(src/lazy 속성 출처 + junk 판정)
  ⑥ 본문 셀렉터 매칭 결과(셀렉터/길이) 또는 폴백 경로
  ⑦ 최종 fetch_article 결과(본문 길이·이미지 URL)
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 레포 루트

from scraping import enrich
from scraping.extract import is_junk_image, soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers, fetch_impersonated


def _status_of(resp) -> str:
    return f"HTTP {resp.status_code} · {len(getattr(resp, 'text', '') or '')}자"


def main(url: str) -> int:
    print(f"진단 대상: {url}\n")
    sess = build_session()
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"

    # ① 기본 요청
    text = ""
    try:
        r1 = sess.get(url, headers=default_headers(referer=origin), timeout=REQUEST_TIMEOUT)
        print(f"① 기본 요청            {_status_of(r1)}")
        if r1.status_code < 400:
            text = r1.text
    except Exception as e:  # noqa: BLE001
        print(f"① 기본 요청            실패: {type(e).__name__}: {e}")

    # ② 워밍업 + 강화 헤더 (차단일 때만 의미)
    if not text:
        try:
            sess.get(origin, headers=enrich._full_browser_headers(), timeout=REQUEST_TIMEOUT)
            r2 = sess.get(url, headers=enrich._full_browser_headers(
                referer="https://search.naver.com/"), timeout=REQUEST_TIMEOUT)
            print(f"② 워밍업+강화 헤더     {_status_of(r2)}")
            if r2.status_code < 400:
                text = r2.text
        except Exception as e:  # noqa: BLE001
            print(f"② 워밍업+강화 헤더     실패: {type(e).__name__}: {e}")

    # ③ TLS 지문 위장
    if not text:
        imp = fetch_impersonated(url, referer="https://search.naver.com/")
        if imp is None:
            print("③ TLS 위장(curl_cffi)  사용 불가(미설치) — pip install curl_cffi")
        else:
            print(f"③ TLS 위장(curl_cffi)  {_status_of(imp)}")
            if imp.status_code < 400:
                text = imp.text
    if not text:
        print("\n→ 모든 요청이 차단됨: 사이트가 IP 대역 차단일 가능성. "
              "다른 회선/배포 환경에서 재시도 필요.")
        return 1

    soup = soup_of(text)

    # ④ 메타 이미지 후보
    print("\n④ 메타 이미지 후보")
    found_meta = False
    for sel in enrich._IMAGE_SELECTORS:
        tag = soup.select_one(sel)
        if not tag:
            continue
        val = (tag.get("content") or tag.get("href") or "").strip()
        if val:
            found_meta = True
            print(f"   {sel:38s} {'JUNK' if is_junk_image(val) else 'OK  '} {val[:90]}")
    if not found_meta:
        print("   (없음 — og:image 계열 메타 자체가 없음)")

    # ⑤ 본문 img 후보
    print("\n⑤ 본문 img 후보 (상위 5)")
    shown = 0
    for img in soup.find_all("img"):
        src = enrich._img_src_from_attrs(img)
        if not src:
            continue
        attr_used = next((a for a in enrich._IMAGE_ATTR_ORDER if (img.get(a) or "").strip()), "srcset")
        print(f"   [{attr_used:12s}] {'JUNK' if is_junk_image(src) else 'OK  '} {src[:90]}")
        shown += 1
        if shown >= 5:
            break
    if not shown:
        print("   (img 태그에서 src/lazy 속성을 찾지 못함)")

    # ⑥ 본문 셀렉터
    print("\n⑥ 본문 셀렉터 매칭")
    work = soup_of(text)
    enrich._strip_noise(work)
    hit = False
    for sel in enrich._CONTENT_SELECTORS:
        tag = work.select_one(sel)
        if tag:
            t = enrich._text_from_tag(tag)
            if len(t) >= enrich._MIN_CONTENT_LEN:
                print(f"   매칭: {sel}  → {len(t)}자 · 첫 80자: {t[:80]!r}")
                hit = True
                break
    if not hit:
        print("   (셀렉터 미매칭 → 문단/최대블록 폴백 경로 사용)")

    # ⑥-b 구조화 데이터 본문 (SPA — 조선닷컴 등 Arc 계열)
    raw_soup = soup_of(text)
    ld = enrich._ldjson_article_body(raw_soup)
    fusion = enrich._arc_fusion_body(text)
    print("\n⑥-b 구조화 데이터 본문")
    print(f"   ld+json articleBody : {len(ld)}자")
    print(f"   Fusion.globalContent: {len(fusion)}자")

    # ⑦ 최종 파이프라인 결과
    art = enrich.fetch_article(url)
    print(f"\n⑦ fetch_article 결과   본문 {len(art['content'])}자 · 이미지: "
          f"{art['image_url'] or '(없음)'}")
    if art["content"]:
        print(f"   본문 첫 120자: {art['content'][:120]!r}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

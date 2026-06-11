"""기사 1건 수집 진단 — 어느 단계에서 본문/사진이 빠지는지 단계별 리포트.

단계 로직은 `scraping/diagnose.py` 의 `diagnose()` 가 담당하고(⚙ 수집 설정의
'🔬 기사 URL 진단' 카드와 공유), 이 스크립트는 CLI 출력 래퍼다.

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
  ⑦ 최종 fetch_article 결과(본문 길이·이미지 URL) + 200 위장 차단 의심 여부
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 레포 루트

from scraping.diagnose import diagnose


def _step_line(step: dict) -> str:
    if step["skipped"]:
        return "(생략 — 이전 단계 성공)"
    if step["error"]:
        return f"실패: {step['error']}"
    if step["status"] is None:
        return "(미실행)"
    return f"HTTP {step['status']} · {step['length']}자"


def main(url: str) -> int:
    print(f"진단 대상: {url}\n")
    rep = diagnose(url)

    for step in rep["steps"]:
        print(f"{step['label']:<22s} {_step_line(step)}")
    if rep["all_blocked"]:
        print("\n→ 모든 요청이 차단됨: 사이트가 IP 대역 차단일 가능성. "
              "다른 회선/배포 환경에서 재시도 필요.")
        if not rep["curl_cffi_available"]:
            print("  (curl_cffi 미설치 — TLS 위장 폴백 비활성. pip install curl_cffi)")
        return 1

    print("\n④ 메타 이미지 후보")
    for cand in rep["meta_images"]:
        print(f"   {cand['selector']:38s} {'JUNK' if cand['junk'] else 'OK  '} {cand['url'][:90]}")
    if not rep["meta_images"]:
        print("   (없음 — og:image 계열 메타 자체가 없음)")

    print("\n⑤ 본문 img 후보 (상위 5)")
    for cand in rep["body_images"]:
        print(f"   [{cand['attr']:12s}] {'JUNK' if cand['junk'] else 'OK  '} {cand['url'][:90]}")
    if not rep["body_images"]:
        print("   (img 태그에서 src/lazy 속성을 찾지 못함)")

    print("\n⑥ 본문 셀렉터 매칭")
    sel = rep["content_selector"]
    if sel:
        print(f"   매칭: {sel['selector']}  → {sel['length']}자 · 첫 80자: {sel['preview']!r}")
    else:
        print("   (셀렉터 미매칭 → 문단/최대블록 폴백 경로 사용)")

    print("\n⑥-b 구조화 데이터 본문")
    print(f"   ld+json articleBody : {rep['structured']['ldjson_len']}자")
    print(f"   Fusion.globalContent: {rep['structured']['fusion_len']}자")

    if rep["soft_block_suspect"]:
        print("\n⚠ 200 위장 차단 의심 — " + " / ".join(rep["soft_block_reasons"]))

    final = rep["final"]
    print(f"\n⑦ fetch_article 결과   본문 {final['content_len']}자 · 이미지: "
          f"{final['image_url'] or '(없음)'}")
    if final["content_preview"]:
        print(f"   본문 첫 120자: {final['content_preview']!r}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

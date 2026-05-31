"""SOLA workshop thread 제목 LLM 생성기.

첫 user 메시지에서 5~12자 한국어 제목을 LLM 으로 만든다. 디스크 캐시 + 룰
fallback 으로 LLM 미설정·실패에도 무중단 동작.
"""
from __future__ import annotations

import re

from config import llm_model
from sola.client import LLMNotConfigured, chat
from sola.prompts import SYSTEM_THREAD_TITLE
from store import cache
from store.sola_threads import title_from_first_user_message


_MIN_LEN = 3
_MAX_LEN = 20  # 룰 truncation 한계와 호환
_STRIP_CHARS = "\"'“”‘’`「」『』·"


def _clean_title(raw: str) -> str:
    """LLM 응답을 안전한 제목 형태로 정제.

    - 양끝 공백·따옴표 제거
    - 줄바꿈 → 첫 줄만
    - 이모지/장식 문자 제거(간단 휴리스틱)
    - 길이 _MAX_LEN 초과 시 자름
    """
    if not raw:
        return ""
    text = raw.strip()
    # 첫 줄만
    text = text.split("\n", 1)[0].strip()
    # 양쪽 따옴표/장식 제거
    text = text.strip(_STRIP_CHARS).strip()
    # 코드 블록 잔여 제거
    text = text.strip("`").strip()
    # 마침표/물음표 끝 제거
    text = text.rstrip(" .。!?")
    # 비ASCII 이모지 등 surrogate 영역 제거 (간단 휴리스틱)
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text)
    text = text.strip()
    if len(text) > _MAX_LEN:
        text = text[:_MAX_LEN].rstrip()
    return text


def _cache_signature(user_message: str) -> str:
    """캐시 키 — 메시지 앞 100자 + 모델."""
    flat = " ".join((user_message or "").split())
    return flat[:100]


def generate(user_message: str, *, force: bool = False) -> str:
    """첫 user 메시지로 thread 제목 생성. 캐시 우선 + 룰 fallback.

    Args:
        user_message: 첫 사용자 발화.
        force: 캐시 무시.

    Returns:
        제목 문자열. LLM 미설정·실패·빈 응답 시
        `store.sola_threads.title_from_first_user_message()` fallback.
    """
    msg = (user_message or "").strip()
    if not msg:
        return title_from_first_user_message(msg)

    sig = _cache_signature(msg)
    key = cache.make_key("thread_title", sig, llm_model() or "")
    if not force:
        hit = cache.get(key)
        if hit is not None:
            return hit

    try:
        reply = chat(
            messages=[
                {"role": "system", "content": SYSTEM_THREAD_TITLE},
                {"role": "user", "content": msg[:500]},
            ],
            temperature=0.1,
            max_tokens=40,
        )
    except LLMNotConfigured:
        return title_from_first_user_message(msg)
    except Exception:  # noqa: BLE001
        return title_from_first_user_message(msg)

    title = _clean_title(reply)
    if len(title) < _MIN_LEN:
        return title_from_first_user_message(msg)
    cache.put(key, title)
    return title

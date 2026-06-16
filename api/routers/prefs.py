"""표시 설정 API — `store.ui_prefs` 위임 (테마 4종·글자 3단).

React ThemeProvider 가 서버 영속이 필요할 때 사용(현재 localStorage, 후속 동기화).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from store import ui_prefs

router = APIRouter(prefix="/api/ui-prefs", tags=["prefs"])


class PrefsModel(BaseModel):
    theme: str = "light"
    font: str = "medium"


@router.get("", response_model=PrefsModel)
def get_prefs() -> PrefsModel:
    return PrefsModel(**ui_prefs.load())


@router.put("", response_model=PrefsModel)
def put_prefs(body: PrefsModel) -> PrefsModel:
    return PrefsModel(**ui_prefs.save(theme=body.theme, font=body.font))

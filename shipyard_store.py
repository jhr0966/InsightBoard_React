"""Shipyard 작업 데이터(Excel) 업로드/검증/Parquet 저장."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
import random

import pandas as pd


REQUIRED_COLUMNS = ["task_id", "process", "task_name", "description"]


@dataclass
class ShipyardIngestResult:
    is_valid: bool
    errors: list[str]
    raw_path: str | None = None
    parquet_path: str | None = None
    row_count: int = 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _dated_dir(base: Path, when: datetime) -> Path:
    path = base / when.strftime("%Y-%m-%d")
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_shipyard_df(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df.empty:
        errors.append("엑셀 데이터가 비어 있습니다.")
        return errors

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"필수 컬럼 누락: {', '.join(missing)}")
        return errors

    for col in REQUIRED_COLUMNS:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            errors.append(f"필수 컬럼 '{col}'에 빈 값이 {null_count}개 있습니다.")

    if "task_id" in df.columns:
        dup_count = int(df["task_id"].duplicated().sum())
        if dup_count > 0:
            errors.append(f"'task_id' 중복이 {dup_count}개 있습니다.")

    return errors


def ingest_shipyard_excel(
    file_name: str,
    file_obj: BinaryIO,
    data_root: str | Path = "data",
) -> ShipyardIngestResult:
    """업로드한 엑셀을 raw 저장 후 검증하고 parquet 저장."""
    root = Path(data_root)
    raw_base = root / "shipyard" / "raw"
    processed_base = root / "shipyard" / "processed"

    now = _utc_now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    raw_dir = _dated_dir(raw_base, now)
    processed_dir = _dated_dir(processed_base, now)

    raw_path = raw_dir / f"{stamp}_{Path(file_name).name}"
    with raw_path.open("wb") as f:
        f.write(file_obj.read())

    try:
        df = pd.read_excel(raw_path)
    except ImportError:
        return ShipyardIngestResult(
            is_valid=False,
            errors=["엑셀 엔진(openpyxl)이 설치되어 있지 않습니다. requirements 설치 후 다시 시도하세요."],
            raw_path=str(raw_path),
            row_count=0,
        )
    except Exception as exc:
        return ShipyardIngestResult(
            is_valid=False,
            errors=[f"엑셀 파일을 읽지 못했습니다: {exc}"],
            raw_path=str(raw_path),
            row_count=0,
        )
    df.columns = [str(c).strip() for c in df.columns]

    errors = validate_shipyard_df(df)
    if errors:
        return ShipyardIngestResult(
            is_valid=False,
            errors=errors,
            raw_path=str(raw_path),
            row_count=len(df),
        )

    parquet_path = processed_dir / f"shipyard_tasks_{stamp}.parquet"
    df.to_parquet(parquet_path, index=False)

    return ShipyardIngestResult(
        is_valid=True,
        errors=[],
        raw_path=str(raw_path),
        parquet_path=str(parquet_path),
        row_count=len(df),
    )


def load_latest_shipyard_tasks(data_root: str | Path = "data") -> pd.DataFrame:
    root = Path(data_root)
    processed_base = root / "shipyard" / "processed"
    if not processed_base.exists():
        return pd.DataFrame()

    candidates = sorted(
        processed_base.glob("*/shipyard_tasks_*.parquet"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return pd.DataFrame()

    return pd.read_parquet(candidates[0])


def create_fake_shipyard_tasks(
    row_count: int = 30,
    data_root: str | Path = "data",
) -> ShipyardIngestResult:
    """조선소 관련 페이크 작업 데이터를 생성해 parquet로 저장."""
    root = Path(data_root)
    processed_base = root / "shipyard" / "processed"
    now = _utc_now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    processed_dir = _dated_dir(processed_base, now)

    teams = ["생산팀", "도장팀", "의장팀", "품질팀", "안전팀"]
    process_map = {
        "생산팀": ["조립", "취부", "수동용접", "자동용접"],
        "도장팀": ["전처리", "선체도장", "블라스팅", "도막검사"],
        "의장팀": ["의장설치", "배관설치", "케이블포설", "시운전준비"],
        "품질팀": ["비파괴검사", "치수검사", "용접부검사", "품질문서검토"],
        "안전팀": ["작업허가", "위험성평가", "가스측정", "안전순찰"],
    }
    task_map = {
        "조립": ["블록 정렬", "프레임 고정"],
        "취부": ["가접", "부재 위치맞춤"],
        "수동용접": ["필렛 용접", "맞대기 용접"],
        "자동용접": ["SAW 용접", "로봇 용접"],
        "전처리": ["표면 세척", "녹 제거"],
        "선체도장": ["하도 도장", "중도 도장", "상도 도장"],
        "블라스팅": ["샷 블라스팅", "그릿 블라스팅"],
        "도막검사": ["도막 두께 측정", "핀홀 검사"],
        "의장설치": ["밸브 설치", "펌프 설치"],
        "배관설치": ["배관 피팅", "플랜지 체결"],
        "케이블포설": ["케이블 루트 포설", "단자 결선"],
        "시운전준비": ["체크리스트 점검", "장비 예열"],
        "비파괴검사": ["UT 검사", "RT 검사"],
        "치수검사": ["정렬도 측정", "간격 측정"],
        "용접부검사": ["비드 외관 검사", "결함 리포트 작성"],
        "품질문서검토": ["검사 성적서 검토", "변경 이력 검토"],
        "작업허가": ["고소작업 허가", "밀폐공간 허가"],
        "위험성평가": ["JSA 작성", "위험요인 식별"],
        "가스측정": ["산소 농도 측정", "가연성 가스 측정"],
        "안전순찰": ["현장 순찰", "PPE 착용 점검"],
    }

    rows: list[dict[str, str]] = []
    for i in range(1, row_count + 1):
        team = random.choice(teams)
        process = random.choice(process_map[team])
        task_name = random.choice(task_map[process])
        rows.append(
            {
                "task_id": f"TASK-{stamp[-6:]}-{i:03d}",
                "team": team,
                "process": process,
                "task_name": task_name,
                "description": f"{team} {process} 공정에서 수행되는 '{task_name}' 작업 자동화 검토",
            }
        )

    df = pd.DataFrame(rows)
    errors = validate_shipyard_df(df)
    if errors:
        return ShipyardIngestResult(is_valid=False, errors=errors, row_count=len(df))

    parquet_path = processed_dir / f"shipyard_tasks_fake_{stamp}.parquet"
    df.to_parquet(parquet_path, index=False)
    return ShipyardIngestResult(
        is_valid=True,
        errors=[],
        parquet_path=str(parquet_path),
        row_count=len(df),
    )

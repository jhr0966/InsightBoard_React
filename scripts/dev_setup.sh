#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[OK] 개발 환경 준비 완료"
echo "다음 명령으로 앱을 실행하세요:"
echo "  백엔드: source .venv/bin/activate && uvicorn api.main:app --reload"
echo "  프런트: cd web && npm install && npm run dev"

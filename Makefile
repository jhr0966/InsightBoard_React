.PHONY: install run run-web check test format clean verify-scrape

PY_FILES := $(shell git ls-files '*.py')

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

run:
	uvicorn api.main:app --reload

run-web:
	cd web && npm run dev

check:
	python -m py_compile $(PY_FILES)
	@violations="$$(rg -n 'requests\.(get|post|Session)\(' api sola store roadmap persona scraping | rg -v '^scraping/http\.py:' || true)"; \
	if [ -n "$$violations" ]; then \
		echo "requests.* 직접 호출 발견. scraping.http.build_session()을 사용하세요."; \
		echo "$$violations"; \
		exit 1; \
	fi
	@secret_matches="$$(rg -n 'gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}' .env.example || true)"; \
	if [ -n "$$secret_matches" ]; then \
		echo "실제 API 키로 보이는 값이 .env.example에 있습니다. .env로 옮기고 예시는 placeholder만 남기세요."; \
		echo "$$secret_matches"; \
		exit 1; \
	fi

test:
	python -m pytest -q

# 크롤링 파이프라인 자체검증 — 로컬 fixture 서버, 외부망 불필요
verify-scrape:
	python scripts/verify_scrape.py

format:
	python -m pip install ruff
	ruff format $(PY_FILES)

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +

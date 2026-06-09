.PHONY: install run check test format clean verify-browser verify-scrape

PY_FILES := $(shell git ls-files '*.py')

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

run:
	streamlit run app.py

check:
	python -m py_compile $(PY_FILES)
	@if rg -n 'on_click\s*=' app.py ui; then \
		echo "on_click= 사용 발견. pending flag + st.rerun 패턴을 사용하세요."; \
		exit 1; \
	fi
	@violations="$$(rg -n 'requests\.(get|post|Session)\(' app.py ui sola store roadmap persona scraping | rg -v '^scraping/http\.py:' || true)"; \
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

# Streamlit 이 떠 있는 상태에서 v2 화면 7개 스크린샷 검증 (Playwright)
verify-browser:
	python scripts/verify_browser.py http://127.0.0.1:8501

# 크롤링 파이프라인 자체검증 — 로컬 fixture 서버, 외부망 불필요
verify-scrape:
	python scripts/verify_scrape.py

format:
	python -m pip install ruff
	ruff format $(PY_FILES)

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +

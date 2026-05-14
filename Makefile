.PHONY: install run check test format clean

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
	pytest -q

format:
	python -m pip install ruff
	ruff format $(PY_FILES)

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +

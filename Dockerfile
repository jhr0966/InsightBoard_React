# InsightBoard 백엔드(FastAPI) — 상시 호스팅용(Render/Railway/Fly 등).
# 프런트(web/)는 Vercel, 백엔드만 이 이미지로.
FROM python:3.11-slim

WORKDIR /app

# 빌드 의존(lxml/curl_cffi 등) — slim 에 없는 것 보강
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# API 가 import 하는 패키지만 복사(.dockerignore 로 web/ui/tests 등 제외)
COPY api ./api
COPY store ./store
COPY sola ./sola
COPY persona ./persona
COPY roadmap ./roadmap
COPY scraping ./scraping
COPY config.py ./

# 데이터 경로. 무료 플랜은 휘발(임시) /app/data, 영구화하려면 디스크를 /data 에
# 마운트하고 INSIGHTBOARD_DATA_ROOT 를 /data 로 오버라이드(render.yaml 참고).
ENV INSIGHTBOARD_DATA_ROOT=/app/data
ENV PORT=8000
EXPOSE 8000

# PORT 환경변수(Render/Railway 가 주입) 사용
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

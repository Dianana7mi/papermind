FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libgomp1 curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.11.29
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra pdf --extra local --no-install-project
COPY . .
RUN uv sync --frozen --extra pdf --extra local && useradd --uid 10001 --create-home app && mkdir -p /app/data /home/app/.cache && chown -R app:app /app /home/app/.cache
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

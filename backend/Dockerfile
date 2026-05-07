FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY pyproject.toml uv.lock /app/
ENV UV_HTTP_TIMEOUT=120
RUN uv sync --frozen

COPY src/ ./src/

EXPOSE 8000

ENV PYTHONPATH=/app
CMD [".venv/bin/python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

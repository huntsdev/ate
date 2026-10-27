FROM python:3.12-slim-bookworm@sha256:fc169880a4d941f3142c0e2e623f05f246150add19dc36fc9224df20fb19e5fd
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app:/worker"
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.12
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY apps/api/sentinelforge ./sentinelforge
COPY apps/api/alembic.ini ./
COPY apps/worker /worker
RUN groupadd --gid 10001 ate && useradd --uid 10001 --gid ate --no-create-home ate
USER ate
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "sentinelforge.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
ENV PYTHONUNBUFFERED=1
ENV PORT=5004
EXPOSE 5004
CMD ["gunicorn", "--bind", "0.0.0.0:5004", "--workers", "2", "app:app"]

# Slim, multi-stage build - see architecture-design-phase1.md §1 for the
# problem this avoids (the reference bots' full python:3.10 image with a
# 50+ package requirements.txt hurting image size and cold-start time on
# Koyeb's free tier).

FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src ./src

# Runs as a non-root user.
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python", "-m", "media_platform.server"]

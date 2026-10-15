# Service `runtime` : expose GET /health. Image construite localement par `wap-runtime setup`.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --system --no-create-home runtime

USER runtime
EXPOSE 8787
# Dans le conteneur on écoute sur toutes les interfaces ; Compose ne publie que sur 127.0.0.1.
CMD ["wap-runtime", "serve", "--host", "0.0.0.0", "--port", "8787"]

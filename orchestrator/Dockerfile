# Service `runtime` : FastAPI servi par uvicorn (GET /health, API du cockpit sous /api/, front sur /).
# Image construite localement par `wap-runtime setup`. Node ne sert qu’à construire le front.
FROM node:24-slim AS cockpit

WORKDIR /cockpit
# Dépendances verrouillées par package-lock.json (intégrité vérifiée par `npm ci`).
COPY cockpit/package.json cockpit/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY cockpit ./
RUN npm run build

FROM python:3.12-slim AS build

WORKDIR /src
COPY requirements-build.txt ./
RUN pip install --no-cache-dir --require-hashes --only-binary :all: -r requirements-build.txt
COPY pyproject.toml ./
COPY src ./src
RUN pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /dist .

FROM python:3.12-slim

# Dépendances du service (extra `serve`) verrouillées par hash, puis la wheel sans résolution.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --only-binary :all: -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
COPY --from=build /dist /dist
RUN pip install --no-cache-dir --no-index --no-deps --only-binary :all: /dist/*.whl \
    && rm -rf /dist \
    && useradd --system --no-create-home runtime
COPY --from=cockpit /cockpit/dist /opt/wap-cockpit
ENV WAP_COCKPIT=/opt/wap-cockpit

USER runtime
EXPOSE 8787
# Dans le conteneur on écoute sur toutes les interfaces ; Compose ne publie que sur 127.0.0.1.
CMD ["wap-runtime", "serve", "--host", "0.0.0.0", "--port", "8787"]

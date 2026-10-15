# Service `runtime` : expose GET /health. Image construite localement par `wap-runtime setup`.
FROM python:3.12-slim AS build

WORKDIR /src
COPY requirements-build.txt ./
RUN pip install --no-cache-dir --require-hashes --only-binary :all: -r requirements-build.txt
COPY pyproject.toml ./
COPY src ./src
RUN pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /dist .

FROM python:3.12-slim

# Le paquet n’a aucune dépendance sur 3.12 : on n’installe que sa wheel, sans résolution.
COPY --from=build /dist /dist
RUN pip install --no-cache-dir --no-index --no-deps --only-binary :all: /dist/*.whl \
    && rm -rf /dist \
    && useradd --system --no-create-home runtime

USER runtime
EXPOSE 8787
# Dans le conteneur on écoute sur toutes les interfaces ; Compose ne publie que sur 127.0.0.1.
CMD ["wap-runtime", "serve", "--host", "0.0.0.0", "--port", "8787"]

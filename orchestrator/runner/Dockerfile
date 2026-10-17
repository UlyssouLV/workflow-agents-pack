# Service `runner` : sessions des agents (ADR 0004). Image construite localement par
# `wap-runtime setup`, contexte `orchestrator/` comme `runtime`.
FROM python:3.12-slim AS build

WORKDIR /src
COPY requirements-build.txt ./
RUN pip install --no-cache-dir --require-hashes --only-binary :all: -r requirements-build.txt
COPY pyproject.toml ./
COPY src ./src
RUN pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /dist .

FROM node:24-slim

# Versions épinglées : changer l’une d’elles = relancer `setup` pour reconstruire l’image.
ARG CLAUDE_VERSION=2.1.302
ARG SKILLS_CLI_VERSION=1.7.2
ARG SKILLS_MATT_COMMIT=49dd158d1076134a641b33efb035946536778336
# Le `HOME` réel est `runner-home/` de l’instance, monté par-dessus au démarrage :
# ce qui s’installe « pour l’utilisateur » au build vit sous ce squelette.
ARG SQUELETTE=/opt/runner-squelette

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git tmux python3 python3-venv \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod a+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g --no-audit --no-fund "@anthropic-ai/claude-code@${CLAUDE_VERSION}" \
    && npm cache clean --force

# Cursor : le script officiel n’accepte pas de version (dernière au build).
RUN mkdir -p /opt/cursor \
    && curl -fsSL https://cursor.com/install | HOME=/opt/cursor bash \
    && ln -s "$(readlink -f /opt/cursor/.local/bin/agent)" /usr/local/bin/agent \
    && chmod -R a+rX /opt/cursor

# Skills de Matt Pocock, portée utilisateur (`~/.agents/skills`, liés dans
# `~/.claude/skills` et `~/.cursor/skills`), au commit épinglé.
RUN git clone --quiet https://github.com/mattpocock/skills /tmp/skills-matt \
    && git -C /tmp/skills-matt checkout --quiet "${SKILLS_MATT_COMMIT}" \
    && mkdir -p "${SQUELETTE}" \
    && HOME="${SQUELETTE}" npx -y "skills@${SKILLS_CLI_VERSION}" add /tmp/skills-matt \
        --global --yes --agent claude-code --agent cursor --skill '*' \
    && rm -rf /tmp/skills-matt /root/.npm \
    && chmod -R a+rX "${SQUELETTE}"

# API interne du runner (`wap-runtime runner`) : son venv, hors du `PATH` des agents (seul
# `wap-runtime` y est lié). Le verrou liste les wheels de toutes les versions de Python.
COPY requirements.txt /tmp/requirements.txt
COPY --from=build /dist /dist
RUN python3 -m venv /opt/wap-runtime \
    && /opt/wap-runtime/bin/pip install --no-cache-dir --require-hashes --only-binary :all: \
        -r /tmp/requirements.txt \
    && /opt/wap-runtime/bin/pip install --no-cache-dir --no-index --no-deps --only-binary :all: /dist/*.whl \
    && ln -s /opt/wap-runtime/bin/wap-runtime /usr/local/bin/wap-runtime \
    && rm -rf /dist /tmp/requirements.txt

ENV WAP_RUNNER_SQUELETTE=${SQUELETTE}
COPY runner/entrypoint.sh /usr/local/bin/wap-runner-entrypoint
RUN chmod 0755 /usr/local/bin/wap-runner-entrypoint

WORKDIR /clones
ENTRYPOINT ["wap-runner-entrypoint"]
# Compose passe la même commande ; port non publié, joint par le `runtime` seul.
CMD ["wap-runtime", "runner", "--host", "0.0.0.0", "--port", "8788"]

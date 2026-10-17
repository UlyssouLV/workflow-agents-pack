# Service `runner` : sessions des agents (ADR 0004). Image construite localement par
# `wap-runtime setup`, contexte `orchestrator/` comme `runtime`.
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

ENV WAP_RUNNER_SQUELETTE=${SQUELETTE}
COPY runner/entrypoint.sh /usr/local/bin/wap-runner-entrypoint
RUN chmod 0755 /usr/local/bin/wap-runner-entrypoint

WORKDIR /clones
ENTRYPOINT ["wap-runner-entrypoint"]
# L’API interne du runner (sessions tmux) remplacera cette attente.
CMD ["sleep", "infinity"]

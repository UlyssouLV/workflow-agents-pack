#!/usr/bin/env bash
# Construit et pousse les images de l’instance vers ghcr au commit <sha> (défaut : HEAD),
# étiquetées :sha-<sha> et :staging, manifestes linux/amd64 + linux/arm64 (ADR 0013).
# Appelé par le job `images` de la CI ; hors Actions, prérequis : docker buildx avec QEMU
# (`docker run --privileged --rm tonistiigi/binfmt --install arm64` sur un hôte amd64) et
# `docker login ghcr.io` avec un jeton qui a `write:packages`. Le dépôt doit être à ce commit.
set -euo pipefail

ORCHESTRATOR="$(cd "$(dirname "$0")/.." && pwd)"
SHA="${1:-$(git -C "$ORCHESTRATOR" rev-parse HEAD)}"
PLATEFORMES="linux/amd64,linux/arm64"

publier() {
    local image="$1" dockerfile="$2"
    docker buildx build \
        --platform "$PLATEFORMES" \
        --provenance=false \
        --label "org.opencontainers.image.source=https://github.com/UlyssouLV/workflow-agents-pack" \
        --file "$ORCHESTRATOR/$dockerfile" \
        --tag "$image:sha-$SHA" \
        --tag "$image:staging" \
        --push \
        "$ORCHESTRATOR"
}

# Même contexte `orchestrator/` que le build sur l’hôte (compose généré par `setup`).
publier ghcr.io/ulyssoulv/wap-runtime Dockerfile
publier ghcr.io/ulyssoulv/wap-runner runner/Dockerfile

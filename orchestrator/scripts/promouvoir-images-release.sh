#!/usr/bin/env bash
# Promeut les images de l’instance à la Release <tag> (ADR 0013) : retaggue le digest
# :sha-<sha> vers :X.Y.Z et :latest, sans rebuild (`docker buildx imagetools create`).
# Usage : promouvoir-images-release.sh orchestrator-vX.Y.Z [<sha>] (défaut : commit du tag).
# Appelé par le workflow `promotion` ; hors Actions, prérequis : docker buildx et
# `docker login ghcr.io` avec un jeton qui a `write:packages`.
set -euo pipefail

TAG="${1:-}"
if [[ ! "$TAG" =~ ^orchestrator-v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    echo "tag « $TAG » refusé : attendu orchestrator-vX.Y.Z" >&2
    exit 1
fi
VERSION="${BASH_REMATCH[1]}"

ORCHESTRATOR="$(cd "$(dirname "$0")/.." && pwd)"
SHA="${2:-$(git -C "$ORCHESTRATOR" rev-list -n 1 "$TAG")}"
if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then
    echo "SHA « $SHA » refusé : attendu un commit complet (40 caractères hexadécimaux)" >&2
    exit 1
fi

IMAGES=(ghcr.io/ulyssoulv/wap-runtime ghcr.io/ulyssoulv/wap-runner)

# Toutes les sources d’abord : une image manquante ne laisse aucun tag à moitié promu.
for image in "${IMAGES[@]}"; do
    if ! docker buildx imagetools inspect "$image:sha-$SHA" > /dev/null; then
        echo "$image:sha-$SHA absente de ghcr : le job \`images\` n’a pas publié ce commit, rien n’est promu" >&2
        exit 1
    fi
done

for image in "${IMAGES[@]}"; do
    docker buildx imagetools create --tag "$image:$VERSION" --tag "$image:latest" "$image:sha-$SHA"
done

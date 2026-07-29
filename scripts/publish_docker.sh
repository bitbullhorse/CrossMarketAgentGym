#!/usr/bin/env bash
set -euo pipefail

image="ghcr.io/bitbullhorse/crossmarket-agent-gym:1.0.0"
publish=false
if [[ "${1:-}" == "--publish" ]]; then
  publish=true
elif [[ "${1:-}" != "" && "${1:-}" != "--dry-run" ]]; then
  echo "usage: scripts/publish_docker.sh [--dry-run|--publish]" >&2
  exit 2
fi

docker build --pull --no-cache --tag "${image}" .
docker image inspect "${image}" --format '{{.Id}}'
docker run --rm \
  --network none \
  --cpus 2 \
  --memory 7g \
  --env CUDA_VISIBLE_DEVICES="" \
  --env NVIDIA_VISIBLE_DEVICES=void \
  "${image}" quickstart --smoke-steps 64

if [[ "${publish}" == "true" ]]; then
  docker push "${image}"
  docker tag "${image}" ghcr.io/bitbullhorse/crossmarket-agent-gym:stable
  docker tag "${image}" ghcr.io/bitbullhorse/crossmarket-agent-gym:latest
  docker push ghcr.io/bitbullhorse/crossmarket-agent-gym:stable
  docker push ghcr.io/bitbullhorse/crossmarket-agent-gym:latest
else
  echo "DRY RUN: image was built and tested locally; no registry push was performed."
fi

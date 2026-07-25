#!/usr/bin/env bash
# Rollback script for Vid's Clone
set -euo pipefail

ENVIRONMENT="${1:-}"
if [[ -z "$ENVIRONMENT" ]]; then
  echo "Usage: $0 <dev|staging|prod> [revision]"
  exit 1
fi

REVISION="${2:-}"
NAMESPACE="vids-clone-${ENVIRONMENT}"

echo "=== Rolling back ${ENVIRONMENT} ==="

if command -v kubectl &>/dev/null; then
  if [[ -n "$REVISION" ]]; then
    echo "Rolling back to revision ${REVISION}..."
    kubectl rollout undo deployment/api -n "${NAMESPACE}" --to-revision="${REVISION}"
    kubectl rollout undo deployment/frontend -n "${NAMESPACE}" --to-revision="${REVISION}"
  else
    echo "Rolling back to previous revision..."
    kubectl rollout undo deployment/api -n "${NAMESPACE}"
    kubectl rollout undo deployment/frontend -n "${NAMESPACE}"
  fi

  echo "Waiting for rollout to complete..."
  kubectl rollout status deployment/api -n "${NAMESPACE}" --timeout=300s
  kubectl rollout status deployment/frontend -n "${NAMESPACE}" --timeout=300s

  echo "Rollback complete. Checking health..."
  sleep 5
  kubectl get pods -n "${NAMESPACE}" -l app=api
elif command -v docker &>/dev/null && command -v docker-compose &>/dev/null; then
  echo "Docker Compose environment detected."
  echo "To rollback: docker-compose -f infra/docker/docker-compose.yml pull <service>:<previous-tag> && docker-compose up -d"
  echo "Or use the Docker Swarm deploy with --rollback flag."
fi

echo "=== Done ==="

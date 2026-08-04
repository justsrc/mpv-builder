#!/usr/bin/env bash
set -euo pipefail

workflow_name="${WORKFLOW_NAME:-${GITHUB_WORKFLOW:-}}"
repository="${GITHUB_REPOSITORY:-}"
current_run_id="${GITHUB_RUN_ID:-}"

if [[ -z "$workflow_name" || -z "$repository" || -z "$current_run_id" ]]; then
  echo "cleanup-failed-runs.sh requires WORKFLOW_NAME, GITHUB_REPOSITORY, and GITHUB_RUN_ID" >&2
  exit 1
fi

# Delete older failed runs for the same workflow so the repository stays tidy.
while IFS= read -r run_id; do
  [[ -z "$run_id" || "$run_id" == "$current_run_id" ]] && continue
  gh api "repos/$repository/actions/runs/$run_id" -X DELETE >/dev/null
done < <(gh run list --workflow "$workflow_name" --status failure --json databaseId --jq '.[].databaseId')

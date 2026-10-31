#!/usr/bin/env bash
# Fail closed before starting a credentialed AI worker. Never print secrets.
set -euo pipefail
umask 077
fail() { printf 'HOST_PREFLIGHT_BLOCKED: %s\n' "$1" >&2; exit 1; }
[[ "$(id -un)" == 'hangeul-worker' ]] || fail 'unexpected service user'
[[ "${GITHUB_REPOSITORY:-}" == 'anigio2705-dev/hangeul-swipji' ]] || fail 'repository mismatch'
[[ -n "${OPENAI_API_KEY:-}" ]] || fail 'missing AI credential'
[[ -n "${GH_TOKEN:-}" ]] || fail 'missing GitHub credential'
[[ "${HS_DURABLE_WORKER_DB:-}" == /var/lib/hangeul-swipji/* ]] || fail 'DB not on durable volume'
[[ "${HS_DURABLE_WORKER_DB:-}" != *'..'* ]] || fail 'unsafe DB path'
mountpoint -q /var/lib/hangeul-swipji || fail 'durable volume not mounted'
[[ -d /var/lib/hangeul-swipji/home ]] || fail 'worker home not provisioned'
[[ -d "${HS_WORKTREE:-}" ]] || fail 'missing isolated worktree'
command -v codex >/dev/null 2>&1 || fail 'Codex CLI not installed'
command -v git >/dev/null 2>&1 || fail 'git not installed'
branch="$(git -C "$HS_WORKTREE" branch --show-current 2>/dev/null)" || fail 'invalid worktree'
[[ "$branch" =~ ^(work|automation|agent)/[A-Za-z0-9][A-Za-z0-9._/-]{0,100}$ ]] || fail 'unsafe branch'
[[ "$branch" != *'..'* && "$branch" != *'//'* ]] || fail 'unsafe branch path'
[[ -z "$(git -C "$HS_WORKTREE" status --porcelain 2>/dev/null)" ]] || fail 'dirty worktree'
remote="$(git -C "$HS_WORKTREE" remote get-url origin 2>/dev/null)" || fail 'missing origin'
case "$remote" in
  https://github.com/anigio2705-dev/hangeul-swipji|https://github.com/anigio2705-dev/hangeul-swipji.git|git@github.com:anigio2705-dev/hangeul-swipji|git@github.com:anigio2705-dev/hangeul-swipji.git) ;;
  *) fail 'unapproved git origin' ;;
esac
printf 'HOST_PREFLIGHT_OK: safe pilot worktree and mounted queue volume\n'

#!/usr/bin/env bash
# Fail closed before starting a credentialed AI worker. Never print secrets.
# Install as a root-owned, non-writable host copy; never run from an AI worktree.
set -euo pipefail
umask 077
fail() { printf 'HOST_PREFLIGHT_BLOCKED: %s\n' "$1" >&2; exit 1; }
trusted=/usr/local/libexec/hangeul-swipji/host-preflight.sh
[[ "${BASH_SOURCE[0]}" == "$trusted" && ! -L "$trusted" ]] || fail 'untrusted preflight path'
for p in /usr/local/libexec/hangeul-swipji "$trusted"; do
  [[ "$(stat -c '%u' -- "$p" 2>/dev/null)" == 0 ]] || fail 'preflight owner is not root'
  [[ -z "$(find "$p" -maxdepth 0 -perm /022 -print 2>/dev/null)" ]] || fail 'preflight writable by non-root'
done
# The AI must never be able to rewrite the controller that holds GitHub credentials.
# The original unit executed ai_agent_runner.py from the agent-writable worktree.
# Check every trusted controller path (including import dependencies) before start.
for p in /opt /opt/hangeul-swipji-controller /opt/hangeul-swipji-controller/automation \
         /opt/hangeul-swipji-controller/automation/ai_agent_runner.py \
         /opt/hangeul-swipji-controller/automation/work_request_worker.py \
         /opt/hangeul-swipji-controller/automation/continuous_dispatcher.py; do
  [[ -e "$p" && ! -L "$p" ]] || fail 'missing or symlinked controller path'
  [[ "$(stat -c '%u' -- "$p" 2>/dev/null)" == 0 ]] || fail 'controller path owner is not root'
  [[ -z "$(find "$p" -maxdepth 0 -perm /022 -print 2>/dev/null)" ]] || fail 'controller path writable by non-root'
done
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
[[ -x /usr/bin/git ]] || fail 'system git not installed'
# Do not pass controller/AI secrets to Git helpers while inspecting agent-controlled config.
safe_git() {
  /usr/bin/env -u GH_TOKEN -u GITHUB_TOKEN -u OPENAI_API_KEY \
    -u GIT_SSH_COMMAND -u GIT_ASKPASS -u SSH_ASKPASS \
    -u GIT_CONFIG_COUNT -u GIT_CONFIG_PARAMETERS -u GIT_EXEC_PATH \
    /usr/bin/git "$@"
}
# Git helpers can execute code. Reject executable Git settings before any remote or status operation.
for key in core.sshCommand core.fsmonitor core.hooksPath credential.helper remote.origin.receivepack remote.origin.uploadpack; do
  [[ -z "$(safe_git -C "$HS_WORKTREE" config --get-all "$key" 2>/dev/null)" ]] || fail 'unsafe executable git configuration'
done
branch="$(safe_git -C "$HS_WORKTREE" branch --show-current 2>/dev/null)" || fail 'invalid worktree'
[[ "$branch" =~ ^(work|automation|agent)/[A-Za-z0-9][A-Za-z0-9._/-]{0,100}$ ]] || fail 'unsafe branch'
[[ "$branch" != *'..'* && "$branch" != *'//'* ]] || fail 'unsafe branch path'
[[ -z "$(safe_git -C "$HS_WORKTREE" status --porcelain 2>/dev/null)" ]] || fail 'dirty worktree'
# Effective fetch AND push URLs must each be a single, identical approved destination.
# This catches pushurl and pushInsteadOf redirection, including multiple push targets.
fetch_urls="$(safe_git -C "$HS_WORKTREE" remote get-url --all origin 2>/dev/null)" || fail 'missing origin'
push_urls="$(safe_git -C "$HS_WORKTREE" remote get-url --push --all origin 2>/dev/null)" || fail 'missing push destination'
[[ -n "$fetch_urls" && "$fetch_urls" != *$'\n'* ]] || fail 'multiple fetch URLs'
[[ -n "$push_urls" && "$push_urls" != *$'\n'* ]] || fail 'multiple push URLs'
[[ "$fetch_urls" == "$push_urls" ]] || fail 'effective push destination differs from fetch'
case "$fetch_urls" in
  https://github.com/anigio2705-dev/hangeul-swipji|https://github.com/anigio2705-dev/hangeul-swipji.git|git@github.com:anigio2705-dev/hangeul-swipji|git@github.com:anigio2705-dev/hangeul-swipji.git) ;;
  *) fail 'unapproved effective git destination' ;;
esac
printf 'HOST_PREFLIGHT_OK: trusted host guard, isolated worktree and mounted queue volume\n'

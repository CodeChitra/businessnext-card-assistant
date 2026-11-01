#!/usr/bin/env bash
# Fails if tracked files contain company- or developer-specific values or secrets, or if a file
# that must never be committed is tracked. Private gateway URLs, corporate CA bundles and
# private tracing endpoints belong only in the gitignored .env.local (see CLAUDE.md).
#
#   scripts/hygiene.sh        # also run by CI and `make hygiene`
set -u
cd "$(dirname "$0")/.."
fail=0
report() { echo "hygiene: $1"; fail=1; }

# 1. Files that must never be tracked.
forbidden=$(git ls-files | grep -E '(^|/)\.env(\.local)?$|^docs_akash/|^02_GenAI_LLM_Engineer/|GenAI_LLM_Engineer_Brief' || true)
[ -n "$forbidden" ] && report "tracked files that must stay local:" && echo "$forbidden"

# 2. Content patterns (extended regex), searched in tracked text files only.
EXCLUDE=(':!scripts/hygiene.sh' ':!*package-lock.json' ':!*uv.lock' ':!.env.example')
check() {  # check <label> <regex>
  hits=$(git grep -nIE "$2" -- . "${EXCLUDE[@]}" || true)
  [ -n "$hits" ] && report "$1" && echo "$hits" | head -20
}
check "private hostnames or internal URLs" \
  'https?://[A-Za-z0-9._-]+\.(corp|internal|intranet|lan)([:/]|$)'
check "key or certificate material" \
  'BEGIN [A-Z ]*PRIVATE KEY|\.(pem|p12|pfx)([^A-Za-z0-9]|$)'
check "API keys" \
  'sk-[A-Za-z0-9_-]{20,}|lsv2_[A-Za-z0-9_]{10,}|AKIA[0-9A-Z]{16}'
check "secret assigned a literal value" \
  '(API_KEY|SECRET|PASSWORD|TOKEN)[A-Z_]*[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_-]{20,}'
check "developer-specific absolute paths" \
  '/Users/[A-Za-z0-9._-]+/|[A-Z]:\\Users\\'

[ "$fail" -eq 0 ] && echo "hygiene: ok"
exit "$fail"

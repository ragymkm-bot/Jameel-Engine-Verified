#!/usr/bin/env bash
# RAGY Copilot key setup — reads the key from a LOCAL file, never from chat.
# Usage:
#  1) put your OpenRouter key in this file:  cloud/.openrouter-key   (gitignored)
#  2) run:  bash cloud/setup_copilot_key.sh
set -euo pipefail
cd "$(dirname "$0")"
KEYFILE=".openrouter-key"
if [ ! -f "$KEYFILE" ]; then
  echo "ERROR: $KEYFILE not found. Create it with your OpenRouter key first."
  exit 1
fi
KEY="$(tr -d '\r\n' < "$KEYFILE")"
if [ -z "$KEY" ]; then echo "ERROR: key file is empty"; exit 1; fi
printf '%s' "$KEY" | wrangler secret put OPENROUTER_API_KEY
echo "OK: secret uploaded. Copilot should now respond."

#!/usr/bin/env bash
set -euo pipefail

# Simple wrapper to add, commit and push. Usage:
#   ./git-quick.sh -m "commit message"
#   ./git-quick.sh "commit message"
#   ./git-quick.sh          # uses default message "quick commit"

usage() {
  echo "Usage: $0 [-m \"message\"] [message]"
  exit 1
}

msg="quick commit"

# Parse -m option
while getopts ":m:h" opt; do
  case "$opt" in
    m) msg="$OPTARG" ;;
    h) usage ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage ;;
    :) echo "Option -$OPTARG requires an argument." >&2; usage ;;
  esac
done
shift $((OPTIND-1))

# If remaining positional args present, use them as the message
if [ "$#" -gt 0 ]; then
  msg="$*"
fi

# Ensure we're in a git repository
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Error: not a git repository." >&2
  exit 1
fi

echo "Staging changes..."
git add .

# If there are no staged changes, inform and skip commit
if git diff --cached --quiet; then
  echo "No changes to commit. Skipping commit."
else
  echo "Committing with message: $msg"
  git commit -m "$msg"
fi

# Push
echo "Pushing to remote..."
git push

echo "Done."

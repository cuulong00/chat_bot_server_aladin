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

# Check if we're on the correct branch
current_branch=$(git branch --show-current)
target_branch="tool-calling-improvements"

if [ "$current_branch" != "$target_branch" ]; then
  echo "Current branch: $current_branch"
  echo "Switching to branch: $target_branch"
  
  # Check if branch exists locally
  if git show-ref --verify --quiet refs/heads/$target_branch; then
    git checkout $target_branch
  else
    # Check if branch exists on remote
    if git ls-remote --heads origin $target_branch | grep -q $target_branch; then
      echo "Branch exists on remote, checking out..."
      git checkout -b $target_branch origin/$target_branch
    else
      echo "Creating new branch: $target_branch"
      git checkout -b $target_branch
    fi
  fi
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
echo "Pushing to branch: $target_branch"
if git ls-remote --heads origin $target_branch | grep -q $target_branch; then
  git push origin $target_branch
else
  echo "Setting upstream for new branch..."
  git push -u origin $target_branch
fi

echo "Done."

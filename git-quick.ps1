param(
    [string]$msg = "quick commit"
)

# Check if we're in a git repository
if (-not (Test-Path ".git")) {
    Write-Error "Error: not a git repository."
    exit 1
}

# Check current branch and switch to feature/tool-calling-improvements if needed
$currentBranch = git branch --show-current
$targetBranch = "feature/tool-calling-improvements"

if ($currentBranch -ne $targetBranch) {
    Write-Host "Current branch: $currentBranch"
    Write-Host "Switching to branch: $targetBranch"
    
    # Check if branch exists locally
    $localBranches = git branch --list $targetBranch
    if ($localBranches) {
        git checkout $targetBranch
    } else {
        # Check if branch exists on remote
        $remoteBranches = git ls-remote --heads origin $targetBranch
        if ($remoteBranches) {
            Write-Host "Branch exists on remote, checking out..."
            git checkout -b $targetBranch origin/$targetBranch
        } else {
            Write-Host "Creating new branch: $targetBranch"
            git checkout -b $targetBranch
        }
    }
}

Write-Host "Staging changes..."
git add .

# Check if there are staged changes
$stagedChanges = git diff --cached --name-only
if (-not $stagedChanges) {
    Write-Host "No changes to commit. Skipping commit."
} else {
    Write-Host "Committing with message: $msg"
    git commit -m "$msg"
}

# Push to the target branch
Write-Host "Pushing to branch: $targetBranch"
$remoteBranches = git ls-remote --heads origin $targetBranch
if ($remoteBranches) {
    git push origin $targetBranch
} else {
    Write-Host "Setting upstream for new branch..."
    git push -u origin $targetBranch
}

Write-Host "Done."
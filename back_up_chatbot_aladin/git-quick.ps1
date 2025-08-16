param(
    [string]$msg = "quick commit"
)

git add .
git commit -m "$msg"
git push
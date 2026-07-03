---
description: Stage, commit, push, open and merge a PR, then clean up the branch
argument-hint: [commit message — optional]
allowed-tools: Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git diff:*), Bash(git push:*), Bash(git checkout:*), Bash(git branch:*), Bash(gh pr:*)
---

Run the full commit-to-merge GitHub workflow. Commit message: $ARGUMENTS

If no commit message was given above, read the staged changes and
propose a clear, conventional commit message, then use it.

Work through these steps IN ORDER. Show output after each step and
STOP if any step fails — do not continue on error.

## Step 1 — Review what will be committed
- Run `git status` and `git diff HEAD` to see all pending changes.
- Confirm the current branch is the feature branch, NOT main.
- If we are on main, stop and warn me before doing anything.

## Step 2 — Stage and commit
- Stage everything: `git add .`
- Commit with the message from $ARGUMENTS (or the proposed one):
  `git commit -m "<message>"`
- Print the resulting commit hash and summary.

## Step 3 — Push the branch
- Capture the current branch name.
- Push it to origin: `git push origin <current-branch>`
- If it's the first push, set upstream with `-u`.

## Step 4 — Create and merge the PR
- Open a PR into main using the GitHub CLI:
  `gh pr create --base main --head <current-branch> --fill`
- Then merge it: `gh pr merge --merge --delete-branch`
- Report the PR number and URL.

## Step 5 — Clean up locally
- Switch back to main: `git checkout main`
- Pull the merged changes: `git pull origin main`
- Delete the local feature branch: `git branch -D <current-branch>`

## Final summary
- Confirm: committed, pushed, PR merged, on main, feature branch deleted.
- Report the merged PR URL and the current branch (should be main).
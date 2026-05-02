---
name: "github"
description: "Provides GitHub repository operations including commit, push, pull, branch management, PR creation and merging. Invoke when user wants to interact with GitHub or perform version control operations."
---

# GitHub Integration Skill

This skill provides GitHub repository operations using the `gh` CLI tool.

## Prerequisites

- `gh` CLI must be installed on the system
- User must be authenticated with GitHub via `gh auth login`

## Common Commands

### Authentication
```bash
gh auth login
gh auth status
```

### Repository Operations
```bash
# Clone a repository
gh repo clone <owner>/<repo>

# View repository info
gh repo view <owner>/<repo>
```

### Git Operations
```bash
# Check status
git status

# Add and commit
git add .
git commit -m "commit message"

# Push to remote
git push -u origin <branch-name>
git push --force-with-lease  # Safe force push

# Pull from remote
git pull origin <branch-name>
```

### Branch Management
```bash
# List branches
git branch -a

# Create and switch to new branch
git checkout -b <branch-name>

# Delete local branch
git branch -d <branch-name>

# Delete remote branch
git push origin --delete <branch-name>
```

### Pull Requests
```bash
# Create PR
gh pr create --title "PR Title" --body "PR Description"

# List PRs
gh pr list

# View PR
gh pr view <pr-number>

# Merge PR
gh pr merge <pr-number>

# Close PR
gh pr close <pr-number>
```

### Issues
```bash
# Create issue
gh issue create --title "Issue Title" --body "Issue Description"

# List issues
gh issue list

# View issue
gh issue view <issue-number>
```

## Usage Notes

1. **Always check git status before committing** to avoid unintended files
2. **Use `--force-with-lease` instead of `--force`** for safer force push
3. **Write clear commit messages** following conventional commit format
4. **Create PRs with descriptive titles and body** for better code review
5. **Ensure `gh` is authenticated** before performing any GitHub operations

## Error Handling

If authentication fails:
```bash
gh auth logout
gh auth login
```

If push fails due to remote changes:
```bash
git fetch origin
git rebase origin/<branch-name>
git push
```
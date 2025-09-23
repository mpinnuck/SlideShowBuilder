# Development Workflow

This document outlines the Git workflow for the Slideshow Builder project.

## Branch Strategy

### Main Branch
- `main`: Production-ready code
- Always deployable
- Protected branch (when using remote repository)

### Development Workflow

1. **Feature Development**
   ```bash
   git checkout -b feature/feature-name
   # Make changes
   git add .
   git commit -m "Add feature description"
   git checkout main
   git merge feature/feature-name
   git branch -d feature/feature-name
   ```

2. **Bug Fixes**
   ```bash
   git checkout -b fix/bug-description
   # Fix the bug
   git add .
   git commit -m "Fix: description of bug fix"
   git checkout main
   git merge fix/bug-description
   git branch -d fix/bug-description
   ```

3. **Quick Commits**
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```

## Commit Message Conventions

### Format
```
<type>: <description>

[optional body]

[optional footer]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples
```bash
git commit -m "feat: Add soundtrack integration to slideshow"
git commit -m "fix: Resolve aspect ratio distortion in video slides"
git commit -m "docs: Update README with installation instructions"
git commit -m "refactor: Separate GUI components into modules"
```

## Useful Git Commands

### Basic Operations
```bash
git status                    # Check repository status
git add .                     # Stage all changes
git add file.py              # Stage specific file
git commit -m "message"      # Commit with message
git log --oneline            # View commit history
```

### Branch Management
```bash
git branch                   # List branches
git checkout -b new-branch   # Create and switch to branch
git checkout main            # Switch to main branch
git merge feature-branch     # Merge branch into current
git branch -d branch-name    # Delete merged branch
```

### Undo Operations
```bash
git checkout -- file.py     # Discard changes to file
git reset HEAD file.py       # Unstage file
git reset --soft HEAD~1      # Undo last commit (keep changes)
git reset --hard HEAD~1      # Undo last commit (discard changes)
```

### Remote Repository (when ready)
```bash
git remote add origin <url>  # Add remote repository
git push -u origin main      # Push and set upstream
git push                     # Push changes
git pull                     # Pull changes from remote
```

## Pre-commit Checklist

Before each commit:

1. **Test the application**
   ```bash
   python slideshowbuilder.py
   ```

2. **Check for obvious issues**
   - Syntax errors
   - Import errors
   - Basic functionality

3. **Review changes**
   ```bash
   git diff                  # See unstaged changes
   git diff --staged         # See staged changes
   ```

4. **Commit with meaningful message**
   ```bash
   git commit -m "Clear description of what changed"
   ```

## Version Tagging

For releases:
```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git tag -a v1.1.0 -m "Release version 1.1.0 - Added soundtrack support"
git tag                      # List tags
```

## File Management

### What to Commit
- Source code (`.py` files)
- Configuration files
- Documentation (`.md` files)
- Requirements and setup files

### What NOT to Commit (already in .gitignore)
- Generated videos (`.mp4` files in output folders)
- Python cache files (`__pycache__/`)
- Virtual environment (`.venv/`)
- IDE settings (`.vscode/` except essential configs)
- Temporary files
- Large media files (consider Git LFS for sample media)

## Next Steps

1. **Set up remote repository** (GitHub, GitLab, etc.)
2. **Configure branch protection** for main branch
3. **Set up continuous integration** (optional)
4. **Add collaborators** if working in a team
# Commit Message Standard

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

## Types

| Type | Description |
|------|-------------|
| `feat` | New feature or functionality |
| `fix` | Bug fix |
| `refactor` | Code restructuring without changing behavior |
| `docs` | Documentation changes |
| `style` | Code style changes (formatting, whitespace) |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks, dependencies, configs |
| `ci` | CI/CD configuration changes |
| `perf` | Performance improvements |
| `build` | Build system or dependency changes |

## Scopes

Common scopes for this project:

| Scope | Description |
|-------|-------------|
| `api` | REST API endpoints and routes |
| `db` | Database models and migrations |
| `auth` | Authentication and authorization |
| `generation` | Code generation logic |
| `models` | Pydantic models and schemas |
| `config` | Configuration and settings |
| `deps` | Dependencies |

## Rules

1. **Subject line**
   - Use imperative mood ("Add feature" not "Added feature")
   - Start with lowercase letter
   - No trailing period
   - Maximum 72 characters

2. **Body** (optional)
   - Separate from subject with blank line
   - Explain *what* and *why*, not *how*
   - Wrap at 72 characters

3. **Breaking changes**
   - Add `!` after type/scope: `feat(api)!: remove deprecated endpoint`
   - Or add `BREAKING CHANGE:` in footer

## Examples

### Simple feature
```
feat(api): add namespace CRUD endpoints
```

### Bug fix with scope
```
fix(auth): resolve JWT token expiration handling
```

### Refactoring
```
refactor(models): rename api_craft to median_code_backend
```

### Documentation
```
docs: add commit message standard
```

### Breaking change
```
feat(api)!: change response envelope structure

BREAKING CHANGE: Response envelope now uses `data` instead of `result` field.
```

### Multi-line with body
```
feat(generation): add zip file streaming for code generation

The generate endpoint now streams the zip file directly to the client
instead of writing to disk first. This improves memory efficiency for
large generated projects.
```

## Co-authorship

Do NOT include any Co-Authored-By lines in commit messages.

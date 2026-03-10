# Frontend: Mutual Exclusivity — Database Generation vs Response Placeholders

> **For the frontend Claude instance.** The backend now enforces that `databaseEnabled` and `responsePlaceholders` cannot both be `true`. The frontend must prevent this at the UI level and handle backend rejections gracefully.

---

## Backend Behavior

- `POST /v1/apis/{api_id}/generate` accepts `GenerateOptions` with fields `databaseEnabled` (default `false`) and `responsePlaceholders` (default `true`).
- If both are `true`, the backend returns **422 Unprocessable Entity** with message: _"Response placeholders cannot be enabled when database generation is active."_

---

## Required UI Changes

### 1. When "Database Enabled" is toggled ON

- Set `responsePlaceholders` to `false`
- **Disable** the Response Placeholders checkbox (greyed out)
- Show tooltip on the disabled checkbox: _"Response placeholders are not available when database generation is enabled"_

### 2. When "Database Enabled" is toggled OFF

- **Re-enable** the Response Placeholders checkbox
- Restore to previous value or default (`true`)

### 3. Handle 422 from backend

- If the backend returns 422 with the mutual exclusivity message, show a user-friendly error (e.g. toast notification)
- This should be rare since the UI prevents the invalid state, but acts as a safety net

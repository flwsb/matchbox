# Matchbox — Next Steps

## Railway Persistence Issue

The app uses **SQLite** stored at `data/matchbox.db`. On Railway, the filesystem is **ephemeral** — all registered users, events, and sessions are lost on every deploy or restart.

**Options:**
1. **Attach a Railway Volume** to persist `data/` across deploys (simplest, keeps SQLite)
2. **Migrate to PostgreSQL** via Railway's managed Postgres (more robust for production)

---

## Remaining Implementation Phases

### Phase 2: Enhanced Event Features

- **Platonic event type** — friend matching, distinct from romantic/professional
- **Custom event slugs** — `/e/{slug}` instead of UUID URLs
- **QR code generation** — for join links (new dep: `segno`)
- **Guest receipts** — per-guest category percentile rankings after matching
- **Post-event reviews** — guests rate the match experience (1-5 stars + comment)
- **Custom question builder** — hosts can pick/customize questionnaire questions
- **Guest management between rounds** — add/remove guests, reopen registration

### Phase 3: Communication & Notifications

- **Contact sharing** — double opt-in phone number exchange between matched guests
- **Email notifications** — event invitations, match results, password reset (new dep: `aiosmtplib`)
- **WebSocket improvements** — exponential backoff reconnection, connection status indicator, full state replay on reconnect

### Phase 4: Analytics, Export & Polish

- **Analytics dashboard** — platform stats, trends, satisfaction metrics (Chart.js)
- **Data export** — CSV/JSON export of event results
- **Event templates** — save and reuse event configurations
- **Question bank management** — admin CRUD for the global question bank
- **Security hardening** — rate limiting (new dep: `slowapi`), CSRF tokens
- **Test suite** — pytest + httpx for auth, events, matching, admin (new deps: `pytest`, `pytest-asyncio`, `httpx`)

### Phase 5: Advanced Features

- **Compatible groups** — progressive mingling in shrinking groups before reveal
- **Public event discovery** — `/entdecken` page with public event grid
- **Multiple admins per event** — co-host and viewer roles
- **Test event feature** — auto-generate fake guests to preview the experience

---

## Full Plan Reference

See [.claude/plans/generic-crafting-beaver.md](/.claude/plans/generic-crafting-beaver.md) for the detailed implementation plan with file-level specifics, database schema changes, and architectural decisions.

# Authentication & RBAC

OpenDevOps supports optional password-based authentication with two roles: `admin` and `user`. Auth is disabled by default — set `JWT_SECRET` to enable it.

---

## Enabling auth

Add to your `.env`:

```bash
JWT_SECRET=your-secret-key-here   # any long random string
JWT_EXPIRE_MINUTES=1440            # optional, default 24h
```

Restart the server. The login page will appear on next browser load.

**Without `JWT_SECRET`:** the app runs in dev/open mode — no login required, all users treated as admin. Suitable for local development or single-user installs on a trusted network.

---

## First-time setup

The first user to register automatically gets the `admin` role. Subsequent registrations default to `user`.

> **Important for users upgrading from a pre-RBAC version:** if your database already had rows in the `users` table before running migration `004_users_rbac.sql`, those existing rows don't have passwords. The "first user" check (`count_users`) only counts rows with a `password_hash`, so the first person to register after the migration will correctly get admin.

---

## Roles

| Role | Can do |
|---|---|
| `admin` | Everything — chat, history, dashboard, settings, manage users |
| `user` | Chat, history, dashboard, settings — **cannot** access `/users` (Team page) |

Auth bypass (no `JWT_SECRET`): all requests are treated as admin regardless of role.

---

## API endpoints

### `GET /auth/status`
Returns whether auth is required. Called by the frontend on load.

```json
{ "required": true }
```

### `POST /auth/register`
Registers a new user. Body: `{ email, name, password }`. Returns a JWT.

The first user with a `password_hash` becomes `admin`; all subsequent registrations get `role = "user"`.

### `POST /auth/login`
Body: `{ email, password }`. Returns a JWT on success, `401` on bad credentials.

### `GET /auth/me`
Requires `Authorization: Bearer <token>`. Returns the current user's profile.

```json
{ "id": "uuid", "role": "admin", "name": "Ahmad Hammad", "auth_enabled": true }
```

---

## User management (admin only)

| Endpoint | Description |
|---|---|
| `GET /users` | List all users |
| `POST /users` | Create a user (`email`, `name`, `password`, `role`) |
| `PATCH /users/{id}` | Update name, role, or password |
| `DELETE /users/{id}` | Delete a user |

Non-admins receive `403 Forbidden` on all `/users` endpoints.

In the UI: navigate to **Team** in the sidebar (visible to admins only).

---

## JWT implementation

- Tokens are signed with `HS256` using `JWT_SECRET`
- Payload: `{ sub: user_id, role, exp }`
- Stored in `localStorage` as `auth-token`
- Sent as `Authorization: Bearer <token>` on every API request
- Expiry defaults to 24 hours (`JWT_EXPIRE_MINUTES=1440`)

---

## Migration

Run `migrations/004_users_rbac.sql` on your database:

```bash
psql $DATABASE_URL -f migrations/004_users_rbac.sql
```

This adds `password_hash` and `role` columns to `users`, and drops the unused `owner_key` column from `sessions`. Safe to re-run.

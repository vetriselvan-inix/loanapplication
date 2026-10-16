# ADR 0001: Use JWT bearer tokens instead of server-side sessions

## Status

Accepted (2026-10-16)

## Context

Every protected endpoint must know who is calling and whether they are an
`OFFICER` or a `CUSTOMER`. Clients are Swagger, Postman and, later, a frontend
and mobile apps. HTTP is stateless, so after login the caller needs a credential
to send on each request. The two common options are stateless JWT bearer tokens,
or server-side sessions stored in a table/Redis and referenced by a cookie.

## Decision

Use short-lived JWT access tokens. `POST /auth/login` checks the password hash
and returns a token signed with HS256 using `JWT_SECRET_KEY` from the
environment. The token carries `sub` (user id), `role`, `iat` and `exp`
(30 minutes). Clients send it as `Authorization: Bearer <token>`.
`get_current_user` verifies the signature and expiry, then reloads the user and
rejects missing or inactive accounts with 401.

**Alternative considered:** server-side sessions. They allow instant logout, but
need a session store and a lookup on every request, and cookies are awkward for
non-browser clients and bring CSRF risk. Rejected for now.

## Consequences

- **+** No session storage; any API instance can verify a token.
- **+** Works the same for browsers, mobile, Swagger and Postman; no CSRF exposure.
- **−** A token cannot be revoked before it expires. Mitigated by the 30-minute
  lifetime and by reloading the user on every request, so setting
  `is_active = False` blocks access immediately.
- **−** A role change takes effect only at the next login.
- **−** A leaked `JWT_SECRET_KEY` allows forged tokens; it lives only in the
  environment, never in code.
- Revisit (refresh tokens or sessions) if we need instant logout or
  "log out everywhere".

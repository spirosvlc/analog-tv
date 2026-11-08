# Analog TV HTTP API

The unauthenticated playback client uses only read-only routes:

- `GET /health`
- `GET /api/channels`
- `GET /api/channels/{id}/now`
- `GET /api/channels/media/{id}/{position}`
- `GET /api/weather/forecast`
- `GET /api/alerts/latest?after_id=0`

The following require a local Admin session:

- `POST /api/channels`, `POST /api/channels/{id}/scan`
- `DELETE /api/channels/{id}`, `POST /api/channels/select-folder`
- `GET /api/settings`, `PUT /api/settings`
- `POST /api/alerts`, `POST /api/alerts/test-weather`, `POST /api/alerts/{id}/dismiss`
- Weather location search, IP lookup, configuration and weather-channel creation
- YouTube connection, subscriptions, OAuth callback

For writes send `X-Analog-CSRF` with the `csrf_token` returned from the
session-authenticated `GET /auth/me`. Cross-origin requests are not authorized.
Only the configured local username and password are accepted. A browser session is valid for
up to eight hours. `POST /auth/logout` also requires the CSRF header.

Local authentication endpoints:

- `GET /auth/login` — branded login page
- `POST /auth/login` — submit username, password and login CSRF token
- `GET /auth/me` — admin identity and CSRF token
- `POST /auth/logout` — terminate admin session

`/docs` and `/openapi.json` are private to authenticated admins.

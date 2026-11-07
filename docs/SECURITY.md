# Analog TV security model

- Google OpenID Connect **Authorization Code + PKCE** authenticates the operator.
- Login state and nonce are checked. The Google ID token is verified using
  Google's published public keys (RSA), issuer, audience, expiry, and a verified
  Google email, then compared to `ANALOG_ADMIN_EMAIL`.
- Sessions are signed, short-lived (8 hours), `HttpOnly`, `SameSite=Lax`, and
  `Secure` by default. The session contains no OAuth access token.
- CSRF is required on all authenticated writes; same-origin checks apply when
  an Origin header is present.
- **No OAuth credentials means no Admin access**, not anonymous access.
- The TV player, public channel list, now-playing, media playback, weather
  forecast and alert polling remain accessible without authentication. Do not
  expose media endpoints publicly unless you intend viewers to access them.
- Location IP detection is performed by the server, **not** your Android TV;
  a VPN or reverse proxy may change the detected place. Explicit confirmation
  is required before storing location.
- Keep `/config/auth.env`, `.env`, database files and backups private. Google
  client secrets must not be published to GitHub.
- Google OAuth redirect URIs require **HTTPS** on real networks; plain HTTP
  IP addresses such as `http://192.168.x.x:8155` are not accepted. For local
  development, Google permits `http://localhost` loopback redirect URIs only.
- Use a hardened HTTPS reverse proxy, access control, rate limiting and ideally
  a VPN or identity-aware tunnel. Home Assistant's built-in HTTPS access or a
  reverse proxy must reach the Analog TV app, not only the HA dashboard.
- Restrict host-port 8155 to your trusted LAN if media is private.

The application is a hobby project; before exposing the admin to the Internet,
review proxy headers, TLS, logging, credential rotation and access control.

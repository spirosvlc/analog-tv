# Google Admin authentication

1. Choose a hostname backed by HTTPS, such as `https://tv.example.com`.
   Point it through a TLS reverse proxy or identity-aware tunnel to your
   Home Assistant host on port `8155` (internal application port `8080`).
2. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create/select a project. Configure the **Google Auth Platform / OAuth consent**
   screen. For a personal project in Testing mode, add your Google account to
   **Test users**. Enable appropriate scopes `openid`, `email`, `profile`.
3. Create an **OAuth Client ID**, type **Web application**, not Android.
   Add authorized redirect URI exactly:
   `https://tv.example.com/auth/google/callback`.
4. On Home Assistant, create the private file:
   `/addon_configs/local_analog_tv/auth.env`.
   Copy `auth.env.example` and replace the placeholders. On Docker/standalone,
   place the same values in a private `.env` instead.
5. Set `ANALOG_ADMIN_EMAIL` to your approved Google account,
   `ANALOG_GOOGLE_CLIENT_ID` and `ANALOG_GOOGLE_CLIENT_SECRET` to your web OAuth
   credentials, set both public URL fields, and generate a random session secret:

   ```sh
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
   ```

6. Leave `ANALOG_COOKIE_SECURE=true` for HTTPS. Restart the server (it only
   reads credentials on startup) and visit `https://tv.example.com/admin`.
   Sign in using the allowlisted account.
7. Visit `/admin` with an incognito window or unapproved account to confirm
   access is denied. Public TV should remain available at `/`.

## Testing on your computer

Google allows loopback development redirects, for example
`http://localhost:8080/auth/google/callback`; you may set
`ANALOG_COOKIE_SECURE=false` **only for this local development case**, never for
an Internet-facing URL. The Google Web OAuth redirect must exactly match.

## YouTube subscriptions OAuth

The YouTube Data API feature has its own client ID/secret settings and
`/api/youtube/callback`. Do not confuse that callback with the Admin Google
login `/auth/google/callback`. If you want to use the same Cloud project, you
must register **both** redirect URIs and enable YouTube Data API v3.

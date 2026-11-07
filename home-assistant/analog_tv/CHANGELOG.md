# Analog TV — Home Assistant release notes

## 2.1.0-ha.6
- New Home Assistant slug: `analog_tv`, with independent data directory.
- Database path: `/config/analog_tv.db` (host `/addon_configs/local_analog_tv/analog_tv.db`).
- Strict Google OpenID Connect sign-in protects Broadcast Control and write APIs.
- Green-phosphor login and Google-verified operator identity.
- Playback, weather television and guide remain accessible without login.
- Container port 8080, host port 8155.
- Legacy database can be copied using `docs/MIGRATION.md` instructions.

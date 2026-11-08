# Architecture

## Backend layers

### API layer

FastAPI routes convert HTTP requests into domain schemas and delegate work to services.

### Service layer

Services implement application behavior:

- `ChannelService`
- `AlertService`
- `SettingsService`
- `MediaScanner`
- `M3UImporter`

### Repository layer

Repositories isolate SQLAlchemy database operations from application logic.

### Integration layer

External systems are represented by classes:

- `TelegramBotWorker`
- `TelegramAlertCommand`
- `OpenMeteoClient`

## Runtime

```text
Browser player
      |
      v
FastAPI routes
      |
      v
Services
      |
      v
Repositories
      |
      v
SQLite
```

Telegram commands enter through the integration layer and create alerts through the same `AlertService` used by the HTTP API.

## Future broadcast engine

The next major component should be a `BroadcastScheduler` with:

- channel schedules
- item durations
- station IDs
- bumpers
- fillers
- advert blocks
- persistent virtual broadcast clocks

That will allow a channel to continue while the viewer watches another one.

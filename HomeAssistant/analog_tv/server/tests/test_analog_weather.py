import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from analog_tv.db.database import Base
from analog_tv.db import models
from analog_tv.services.weather_channel_service import WeatherChannelService


def test_location_is_explicit_and_saved_to_existing_settings_table():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        weather = WeatherChannelService(session)
        assert weather.get_location() is None
        loc = weather.save_location(37.9838, 23.7275, 'Athens', 'GR', 'postal')
        assert loc['city'] == 'Athens'
        assert weather.get_location()['latitude'] == 37.9838
        assert weather.settings.get_value('weather_refresh_minutes') == '60'


def test_hourly_weather_cache(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    calls = []
    sample = {
        'timezone': 'Europe/Athens',
        'current': {'temperature_2m': 24.3, 'weather_code': 2},
        'hourly': {'time': ['2026-11-07T12:00'], 'temperature_2m': [24]},
        'daily': {'time': ['2026-11-07'], 'temperature_2m_max': [27]},
    }

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return sample

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            calls.append(url)
            return Response()

    monkeypatch.setattr('analog_tv.services.weather_channel_service.httpx.AsyncClient', Client)
    WeatherChannelService._cache.clear()
    with Session(engine) as session:
        svc = WeatherChannelService(session)
        svc.save_location(37.9838, 23.7275, 'Athens', 'GR', 'postal')
        first = asyncio.run(svc.forecast())
        second = asyncio.run(svc.forecast())
        assert first['current']['temperature_2m'] == 24.3
        assert second['refresh_seconds'] == 3600
        assert len(calls) == 1

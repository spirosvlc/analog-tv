"""On-demand location setup and hourly cached forecasts for Analog TV.

The selected coordinates live in the existing settings table, retaining the
old database and existing Telegram/news/weather settings. The IP location
lookup is only performed after the user explicitly requests it.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from analog_tv.services.settings_service import SettingsService


class WeatherChannelService:
    CACHE_SECONDS = 3600
    _cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
    _lock: asyncio.Lock | None = None

    def __init__(self, session: Session):
        self.settings = SettingsService(session)

    async def locate_from_ip(self) -> dict[str, Any]:
        """Uses the server's outbound public IP, not its LAN address."""
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                'https://ipapi.co/json/',
                headers={'User-Agent': 'AnalogTV/1.0 (weather setup)'},
            )
            response.raise_for_status()
            result = response.json()
        lat, lon = result.get('latitude'), result.get('longitude')
        if lat is None or lon is None:
            raise ValueError('IP location lookup failed. Enter your postal code instead.')
        return {
            'latitude': float(lat), 'longitude': float(lon),
            'city': str(result.get('city') or 'Approximate location'),
            'region': str(result.get('region') or ''),
            'country': str(result.get('country_code') or ''),
            'postal_code': str(result.get('postal') or ''),
            'source': 'ip',
            'notice': 'Approximate IP-based location; confirm before saving.',
        }

    async def geocode(self, query: str, country_code: str = '') -> list[dict[str, Any]]:
        query = query.strip()
        if len(query) < 2 or len(query) > 100:
            raise ValueError('Enter a city or postal code (2–100 characters).')
        params: dict[str, Any] = {'name': query, 'count': 10, 'language': 'en'}
        if country_code.strip():
            params['countryCode'] = country_code.strip().upper()[:2]
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                'https://geocoding-api.open-meteo.com/v1/search', params=params,
            )
            response.raise_for_status()
            data = response.json()
        return [
            {
                'latitude': float(place['latitude']),
                'longitude': float(place['longitude']),
                'city': str(place.get('name') or ''),
                'region': str(place.get('admin1') or ''),
                'country': str(place.get('country_code') or ''),
                'postal_code': query,
                'timezone': str(place.get('timezone') or ''),
                'source': 'postal',
            }
            for place in (data.get('results') or [])
            if place.get('latitude') is not None and place.get('longitude') is not None
        ]

    def save_location(self, latitude: float, longitude: float, city: str, country: str, source: str) -> dict[str, Any]:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError('Invalid latitude or longitude.')
        self.settings.set_value('weather_latitude', str(latitude))
        self.settings.set_value('weather_longitude', str(longitude))
        self.settings.set_value('weather_location_city', city.strip()[:120])
        self.settings.set_value('weather_location_country', country.strip()[:3])
        self.settings.set_value('weather_location_source', source.strip()[:15])
        self.settings.set_value('weather_refresh_minutes', '60')
        return {'latitude': latitude, 'longitude': longitude, 'city': city, 'country': country, 'source': source}

    def get_location(self) -> dict[str, Any] | None:
        lat = self.settings.get_value('weather_latitude', '')
        lon = self.settings.get_value('weather_longitude', '')
        if not lat or not lon:
            return None
        try:
            return {
                'latitude': float(lat), 'longitude': float(lon),
                'city': self.settings.get_value('weather_location_city', 'Your location'),
                'country': self.settings.get_value('weather_location_country', ''),
                'source': self.settings.get_value('weather_location_source', 'manual'),
            }
        except ValueError:
            return None

    async def forecast(self) -> dict[str, Any]:
        location = self.get_location()
        if location is None:
            raise ValueError('Configure a location in Analog TV Admin first.')
        coords = (location['latitude'], location['longitude'])
        cached = self._cache.get(coords)
        if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
            return {**cached[1], 'location': location}

        if self.__class__._lock is None:
            self.__class__._lock = asyncio.Lock()
        async with self.__class__._lock:
            cached = self._cache.get(coords)
            if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
                return {**cached[1], 'location': location}
            params = {
                'latitude': coords[0], 'longitude': coords[1],
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m',
                'hourly': 'temperature_2m,precipitation_probability,weather_code',
                'daily': 'temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum',
                'timezone': 'auto', 'forecast_days': 4,
            }
            try:
                async with httpx.AsyncClient(timeout=18) as client:
                    response = await client.get('https://api.open-meteo.com/v1/forecast', params=params)
                    response.raise_for_status()
                    data = response.json()
            except (httpx.HTTPError, ValueError):
                if cached:  # Keep the weather channel on screen during outages.
                    return {**cached[1], 'location': location, 'stale': True}
                raise
            result = {
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'timezone': data.get('timezone', 'UTC'),
                'current': data.get('current', {}),
                'hourly': data.get('hourly', {}),
                'daily': data.get('daily', {}),
                'refresh_seconds': 3600,
                'stale': False,
            }
            self._cache[coords] = (time.monotonic(), result)
            return {**result, 'location': location}

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class WeatherSnapshot:
    temperature_celsius: float | None
    weather_code: int | None


class OpenMeteoClient:
    """Minimal weather client used as a foundation for weather alerts."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    async def current_weather(
        self,
        latitude: float,
        longitude: float,
    ) -> WeatherSnapshot:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            payload = response.json()

        current = payload.get("current", {})
        return WeatherSnapshot(
            temperature_celsius=current.get("temperature_2m"),
            weather_code=current.get("weather_code"),
        )

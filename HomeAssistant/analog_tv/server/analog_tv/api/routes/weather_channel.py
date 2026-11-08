"""Analog TV weather channel and opt-in location configuration."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from analog_tv.api.dependencies import DatabaseSession
from analog_tv.db.models import ChannelModel
from analog_tv.services.weather_channel_service import WeatherChannelService
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime

router = APIRouter(prefix='/weather', tags=['weather'])


class LocationSelection(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(default='', max_length=3)
    source: Literal['ip', 'postal', 'manual'] = 'manual'


class WeatherChannelSelection(BaseModel):
    number: int = Field(default=90, ge=1, le=999)


@router.get('/location')
def location(session: DatabaseSession):
    return {'location': WeatherChannelService(session).get_location()}


@router.get('/detect-ip')
async def detect_ip(session: DatabaseSession):
    try:
        return await WeatherChannelService(session).locate_from_ip()
    except Exception as exc:
        raise HTTPException(502, f'IP location unavailable: {exc}') from exc


@router.get('/search')
async def search(query: str, session: DatabaseSession, country: str = ''):
    try:
        return {'results': await WeatherChannelService(session).geocode(query, country)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f'Location search unavailable: {exc}') from exc


@router.put('/location')
def save_location(selection: LocationSelection, session: DatabaseSession):
    return WeatherChannelService(session).save_location(**selection.model_dump())


@router.get('/forecast')
async def forecast(session: DatabaseSession):
    try:
        return await WeatherChannelService(session).forecast()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f'Weather provider unavailable: {exc}') from exc


@router.post('/channel')
def create_weather_channel(selection: WeatherChannelSelection, session: DatabaseSession):
    existing = session.scalar(select(ChannelModel).where(ChannelModel.number == selection.number))
    if existing:
        if existing.source_type == 'weather':
            return {'id': existing.id, 'number': existing.number, 'created': False}
        raise HTTPException(409, f'Channel {selection.number} is already in use.')
    channel = ChannelModel(
        number=selection.number, name='ANALOG WEATHER',
        source_type='weather', source='analog-weather',
        logo_url=None, enabled=True, broadcast_epoch=datetime.utcnow(),
    )
    session.add(channel)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'This channel number is already in use.') from exc
    session.refresh(channel)
    return {'id': channel.id, 'number': channel.number, 'created': True}

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from analog_tv.domain.enums import AlertLevel, ChannelSourceType

class ChannelCreate(BaseModel):
    number:int=Field(ge=1,le=999); name:str=Field(min_length=1,max_length=120)
    source_type:ChannelSourceType; source:str=Field(min_length=1); logo_url:str|None=None; enabled:bool=True

class ChannelItemResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; title:str; media_url:str; position:int; duration_seconds:float=0; media_kind:str="video"; provider_id:str|None=None; thumbnail_url:str|None=None

class ChannelResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; number:int; name:str; source_type:ChannelSourceType; source:str; logo_url:str|None; enabled:bool; broadcast_epoch:datetime|None=None; items:list[ChannelItemResponse]

class ChannelCreatedResponse(BaseModel):
    id:int
    items_imported:int
    channels_created:int=1

class NowPlayingResponse(BaseModel):
    channel_id:int; channel_number:int; channel_name:str; item:ChannelItemResponse|None; offset_seconds:float=0; live:bool=False

class AlertCreate(BaseModel):
    level:AlertLevel; message:str=Field(min_length=1,max_length=4000)
class AlertResponse(BaseModel): id:int; level:AlertLevel; message:str; created_at:str

class SettingsUpdate(BaseModel):
    telegram_enabled:bool|None=None; telegram_token:str|None=None; telegram_chat_id:str|None=None
    weather_provider:str|None=None; weather_latitude:str|None=None; weather_longitude:str|None=None; weather_refresh_minutes:int|None=Field(default=None,ge=5,le=1440)
    news_enabled:bool|None=None; news_rss_url:str|None=None; news_interval_minutes:int|None=Field(default=None,ge=15,le=1440); news_headlines:int|None=Field(default=None,ge=1,le=15)
    emy_enabled:bool|None=None; emy_warnings_url:str|None=None; emy_region:str|None=None; emy_interval_minutes:int|None=Field(default=None,ge=5,le=1440); emy_repeat_minutes:int|None=Field(default=None,ge=15,le=1440)
    youtube_client_id:str|None=None; youtube_client_secret:str|None=None; youtube_redirect_uri:str|None=None; youtube_videos_per_creator:int|None=Field(default=None,ge=1,le=10)

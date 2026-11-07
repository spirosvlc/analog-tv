import base64, hashlib, json, re, secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode
import httpx
from sqlalchemy.orm import Session
from analog_tv.services.settings_service import SettingsService

class YouTubeClient:
    AUTH='https://accounts.google.com/o/oauth2/v2/auth'; TOKEN='https://oauth2.googleapis.com/token'; API='https://www.googleapis.com/youtube/v3'
    SCOPE='https://www.googleapis.com/auth/youtube.readonly'
    def __init__(self, session:Session): self.settings=SettingsService(session)
    def auth_url(self):
        client_id=self.settings.get_value('youtube_client_id'); redirect=self.settings.get_value('youtube_redirect_uri','https://tv.example.com/api/youtube/callback')
        if not client_id: raise ValueError('Set YouTube client ID first.')
        state=secrets.token_urlsafe(24); self.settings.set_value('youtube_oauth_state',state)
        return self.AUTH+'?'+urlencode({'client_id':client_id,'redirect_uri':redirect,'response_type':'code','scope':self.SCOPE,'access_type':'offline','prompt':'consent','state':state})
    async def exchange_code(self, code:str, state:str):
        if state != self.settings.get_value('youtube_oauth_state'): raise ValueError('Invalid OAuth state.')
        data={'code':code,'client_id':self.settings.get_value('youtube_client_id'),'client_secret':self.settings.get_value('youtube_client_secret'),'redirect_uri':self.settings.get_value('youtube_redirect_uri','https://tv.example.com/api/youtube/callback'),'grant_type':'authorization_code'}
        async with httpx.AsyncClient(timeout=20) as c: r=await c.post(self.TOKEN,data=data); r.raise_for_status(); payload=r.json()
        self._store_tokens(payload)
    def _store_tokens(self,payload):
        if payload.get('access_token'): self.settings.set_value('youtube_access_token',payload['access_token'])
        if payload.get('refresh_token'): self.settings.set_value('youtube_refresh_token',payload['refresh_token'])
        expires=int(payload.get('expires_in',3600)); self.settings.set_value('youtube_token_expires_at',(datetime.utcnow()+timedelta(seconds=expires-60)).isoformat())
    async def access_token(self):
        token=self.settings.get_value('youtube_access_token'); expiry=self.settings.get_value('youtube_token_expires_at')
        if token and expiry:
            try:
                if datetime.utcnow() < datetime.fromisoformat(expiry): return token
            except ValueError: pass
        refresh=self.settings.get_value('youtube_refresh_token')
        if not refresh: raise ValueError('YouTube account is not connected.')
        data={'client_id':self.settings.get_value('youtube_client_id'),'client_secret':self.settings.get_value('youtube_client_secret'),'refresh_token':refresh,'grant_type':'refresh_token'}
        async with httpx.AsyncClient(timeout=20) as c: r=await c.post(self.TOKEN,data=data); r.raise_for_status(); payload=r.json()
        self._store_tokens(payload); return payload['access_token']
    async def _get(self,path,params):
        token=await self.access_token(); headers={'Authorization':f'Bearer {token}'}
        async with httpx.AsyncClient(timeout=25) as c: r=await c.get(self.API+path,params=params,headers=headers); r.raise_for_status(); return r.json()
    async def subscriptions(self):
        items=[]; page=None
        while True:
            p={'part':'snippet','mine':'true','maxResults':50}
            if page:p['pageToken']=page
            data=await self._get('/subscriptions',p); items.extend(data.get('items',[])); page=data.get('nextPageToken')
            if not page: break
        return [{'channel_id':x['snippet']['resourceId']['channelId'],'title':x['snippet']['title'],'thumbnail':(x['snippet'].get('thumbnails',{}).get('default',{}) or {}).get('url')} for x in items]
    async def latest_videos(self, channel_ids:list[str], per_creator:int=3):
        if not channel_ids:return []
        results=[]
        # channel uploads playlists can be fetched in batches
        for start in range(0,len(channel_ids),50):
            ids=channel_ids[start:start+50]
            data=await self._get('/channels',{'part':'snippet,contentDetails','id':','.join(ids),'maxResults':50})
            for ch in data.get('items',[]):
                uploads=ch['contentDetails']['relatedPlaylists']['uploads']; creator=ch['snippet']['title']
                p=await self._get('/playlistItems',{'part':'snippet,contentDetails','playlistId':uploads,'maxResults':per_creator})
                for it in p.get('items',[]):
                    vid=it.get('contentDetails',{}).get('videoId') or it['snippet']['resourceId']['videoId']
                    results.append({'video_id':vid,'title':it['snippet']['title'],'creator':creator,'thumbnail':(it['snippet'].get('thumbnails',{}).get('medium',{}) or {}).get('url')})
        # retrieve durations
        by_id={x['video_id']:x for x in results}
        ids=list(by_id)
        for start in range(0,len(ids),50):
            data=await self._get('/videos',{'part':'contentDetails','id':','.join(ids[start:start+50])})
            for v in data.get('items',[]): by_id[v['id']]['duration_seconds']=self.parse_duration(v['contentDetails'].get('duration','PT0S'))
        return list(by_id.values())
    @staticmethod
    def parse_duration(value):
        m=re.fullmatch(r'P(?:(?P<d>\d+)D)?T?(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?',value or '')
        if not m:return 0
        g={k:int(v or 0) for k,v in m.groupdict().items()}; return g['d']*86400+g['h']*3600+g['m']*60+g['s']

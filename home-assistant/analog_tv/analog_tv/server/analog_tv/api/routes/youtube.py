import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from analog_tv.api.dependencies import DatabaseSession
from analog_tv.integrations.youtube import YouTubeClient
router=APIRouter(prefix='/youtube',tags=['youtube'])
@router.get('/auth-url')
def auth_url(session:DatabaseSession):
    try:return {'url':YouTubeClient(session).auth_url()}
    except ValueError as e:raise HTTPException(400,str(e))
@router.get('/callback')
async def callback(session:DatabaseSession,code:str=Query(...),state:str=Query(...)):
    try:await YouTubeClient(session).exchange_code(code,state)
    except Exception as e:raise HTTPException(400,f'YouTube OAuth failed: {e}')
    return RedirectResponse('/admin?youtube=connected')
@router.get('/subscriptions')
async def subscriptions(session:DatabaseSession):
    try:return await YouTubeClient(session).subscriptions()
    except Exception as e:raise HTTPException(400,str(e))

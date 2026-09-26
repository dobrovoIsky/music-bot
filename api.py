from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from pydantic import BaseModel
from typing import List, Optional

from database import get_session
from models import QueueItem, QueueStatus, Settings, Song, User

router = APIRouter(prefix="/api")

class SongSchema(BaseModel):
    id: int
    title: str
    artist: str
    cover_url: Optional[str]
    youtube_id: Optional[str]

class QueueItemSchema(BaseModel):
    id: int
    status: str
    song: SongSchema

class QueueResponse(BaseModel):
    playing: Optional[QueueItemSchema]
    queue: List[QueueItemSchema]
    total_users: int
    total_songs: int
    accepting: bool

@router.get("/queue", response_model=QueueResponse)
async def get_queue(session: AsyncSession = Depends(get_session)):
    # Get playing
    playing_res = await session.execute(
        select(QueueItem).where(QueueItem.status == QueueStatus.PLAYING).order_by(QueueItem.id.asc()).limit(1)
    )
    playing = playing_res.scalar_one_or_none()
    
    # Get pending queue
    queue_res = await session.execute(
        select(QueueItem).where(QueueItem.status == QueueStatus.PENDING).order_by(QueueItem.id.asc()).limit(20)
    )
    queue = queue_res.scalars().all()
    
    # Get stats
    total_users_res = await session.execute(
        select(func.count(func.distinct(QueueItem.user_id))).where(QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]))
    )
    total_users = total_users_res.scalar() or 0
    
    total_songs_res = await session.execute(
        select(func.count(QueueItem.id)).where(QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]))
    )
    total_songs = total_songs_res.scalar() or 0
    
    # Get settings
    setting_res = await session.execute(select(Settings).where(Settings.key == "accepting_new_songs"))
    setting = setting_res.scalar_one_or_none()
    accepting = True
    if setting and setting.value == "false":
        accepting = False
        
    def format_item(item):
        return {
            "id": item.id,
            "status": item.status,
            "song": {
                "id": item.song.id,
                "title": item.song.title,
                "artist": item.song.artist,
                "cover_url": item.song.cover_url,
                "youtube_id": item.song.youtube_id
            }
        }
        
    for item in queue:
        await session.refresh(item, ['song'])
        
    if playing:
        await session.refresh(playing, ['song'])
        
    return {
        "playing": format_item(playing) if playing else None,
        "queue": [format_item(i) for i in queue],
        "total_users": total_users,
        "total_songs": total_songs,
        "accepting": accepting
    }

@router.post("/next")
async def next_song(session: AsyncSession = Depends(get_session)):
    # Mark playing as played
    playing_res = await session.execute(
        select(QueueItem).where(QueueItem.status == QueueStatus.PLAYING)
    )
    for p in playing_res.scalars():
        p.status = QueueStatus.PLAYED
        
    # Get next pending
    next_res = await session.execute(
        select(QueueItem).where(QueueItem.status == QueueStatus.PENDING).order_by(QueueItem.id.asc()).limit(1)
    )
    next_item = next_res.scalar_one_or_none()
    
    if next_item:
        next_item.status = QueueStatus.PLAYING
        
    await session.commit()
    return {"status": "ok"}

@router.post("/pause")
async def pause_song(session: AsyncSession = Depends(get_session)):
    # For MVP (Variant A), we just return OK. "Pause" in variant A might just mean stopping the queue from advancing.
    # We could implement a PAUSED status, but driver controls music themselves.
    return {"status": "ok"}

@router.post("/clear")
async def clear_queue(session: AsyncSession = Depends(get_session)):
    items_res = await session.execute(
        select(QueueItem).where(QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]))
    )
    for i in items_res.scalars():
        i.status = QueueStatus.SKIPPED
    await session.commit()
    return {"status": "ok"}

@router.post("/toggle_accepting")
async def toggle_accepting(session: AsyncSession = Depends(get_session)):
    setting_res = await session.execute(select(Settings).where(Settings.key == "accepting_new_songs"))
    setting = setting_res.scalar_one_or_none()
    
    if not setting:
        setting = Settings(key="accepting_new_songs", value="false")
        session.add(setting)
    else:
        setting.value = "true" if setting.value == "false" else "false"
        
    await session.commit()
    return {"accepting": setting.value == "true"}

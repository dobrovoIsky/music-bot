from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import AsyncSessionLocal, User, Song, QueueItem, QueueStatus, Settings
from sqlalchemy import select, func, and_
from itunes import search_song
import json

router = Router()

class SearchState(StatesGroup):
    waiting_for_query = State()

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Найти песню", callback_data="find_song")],
        [InlineKeyboardButton(text="📋 Очередь", callback_data="show_queue")],
        [InlineKeyboardButton(text="❌ Убрать свою песню", callback_data="remove_song")]
    ])

async def get_or_create_user(session, telegram_id: int, name: str) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, name=name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def is_accepting_songs(session) -> bool:
    result = await session.execute(select(Settings).where(Settings.key == "accepting_new_songs"))
    setting = result.scalar_one_or_none()
    if setting and setting.value == "false":
        return False
    return True

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.full_name)
        
    text = (
        "🎵 <b>TAXI MUSIC</b>\n\n"
        "Привет! Вы можете добавить музыку в очередь водителя."
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "find_song")
async def process_find_song(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        if not await is_accepting_songs(session):
            await callback.answer("⚠️ Водитель временно не принимает новые песни.", show_alert=True)
            return
            
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.full_name)
        # Check limit (max 3 pending/playing songs per user)
        active_count = await session.scalar(
            select(func.count(QueueItem.id)).where(
                and_(QueueItem.user_id == user.id, QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]))
            )
        )
        if active_count >= 3:
            await callback.answer("Вы уже добавили 3 песни. Дождитесь их воспроизведения!", show_alert=True)
            return

    await state.set_state(SearchState.waiting_for_query)
    text = (
        "Напиши название песни или исполнителя:\n\n"
        "<i>Например:\nThe Weeknd Starboy</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel_search")]]))

@router.callback_query(F.data == "cancel_search")
async def cancel_search(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🎵 <b>TAXI MUSIC</b>\n\n"
        "Привет! Вы можете добавить музыку в очередь водителя."
    )
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

@router.message(SearchState.waiting_for_query)
async def process_search_query(message: Message, state: FSMContext):
    query = message.text
    if not query:
        return
        
    msg = await message.answer("🔍 Ищу песню...")
    results = await search_song(query)
    
    if not results:
        await msg.edit_text("Ничего не найдено 😔. Попробуйте другой запрос.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    text = "🎵 <b>Результаты:</b>\n\n"
    keyboard = []
    
    for i, res in enumerate(results):
        text += f"{i+1}. {res['artist']} — {res['title']}\n"
        callback_data = json.dumps({"action": "add", "idx": i})
        keyboard.append(InlineKeyboardButton(text=f"➕ {i+1}", callback_data=callback_data))

    # Store results in state to retrieve when user clicks
    await state.update_data(search_results=results)
    
    # Split keyboard into rows of 3
    rows = [keyboard[i:i+3] for i in range(0, len(keyboard), 3)]
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_search")])
    
    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@router.callback_query(F.data.startswith('{"action": "add"'))
async def add_to_queue(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    results = data.get("search_results", [])
    
    cb_data = json.loads(callback.data)
    idx = cb_data.get("idx")
    
    if idx is None or idx >= len(results):
        await callback.answer("Ошибка, попробуйте снова.", show_alert=True)
        return
        
    selected_song = results[idx]
    
    async with AsyncSessionLocal() as session:
        if not await is_accepting_songs(session):
            await callback.answer("⚠️ Водитель временно не принимает новые песни.", show_alert=True)
            return

        # Check total queue limit (max 20)
        total_pending = await session.scalar(
            select(func.count(QueueItem.id)).where(QueueItem.status == QueueStatus.PENDING)
        )
        if total_pending >= 20:
            await callback.answer("Очередь переполнена (максимум 20). Попробуйте позже.", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.full_name)
        
        active_count = await session.scalar(
            select(func.count(QueueItem.id)).where(
                and_(QueueItem.user_id == user.id, QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]))
            )
        )
        if active_count >= 3:
            await callback.answer("Вы уже добавили 3 песни. Дождитесь их воспроизведения!", show_alert=True)
            return

        # Check for duplicates in queue
        existing_song = await session.execute(
            select(Song).join(QueueItem).where(
                and_(Song.itunes_id == selected_song['itunes_id'], QueueItem.status == QueueStatus.PENDING)
            )
        )
        if existing_song.first():
            await callback.answer("Эта песня уже есть в очереди!", show_alert=True)
            return

        # Add song
        song_result = await session.execute(select(Song).where(Song.itunes_id == selected_song['itunes_id']))
        song = song_result.scalar_one_or_none()
        if not song:
            song = Song(
                title=selected_song['title'],
                artist=selected_song['artist'],
                cover_url=selected_song['cover_url'],
                itunes_id=selected_song['itunes_id']
            )
            session.add(song)
            await session.commit()
            await session.refresh(song)
            
        queue_item = QueueItem(user_id=user.id, song_id=song.id, status=QueueStatus.PENDING)
        session.add(queue_item)
        await session.commit()
        
        # Determine position
        position = await session.scalar(
            select(func.count(QueueItem.id)).where(
                and_(QueueItem.status == QueueStatus.PENDING, QueueItem.id <= queue_item.id)
            )
        )
        playing_count = await session.scalar(select(func.count(QueueItem.id)).where(QueueItem.status == QueueStatus.PLAYING))
        position += playing_count
    
    await state.clear()
    
    text = (
        f"✅ <b>Добавлено в очередь!</b>\n\n"
        f"{selected_song['artist']} — {selected_song['title']}\n\n"
        f"Позиция: #{position}\n"
        f"Перед вами: {position - 1} песен."
    )
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "show_queue")
async def show_queue(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        playing_items = await session.execute(
            select(QueueItem).where(QueueItem.status == QueueStatus.PLAYING).order_by(QueueItem.id.asc()).limit(1)
        )
        playing = playing_items.scalar_one_or_none()
        
        pending_items = await session.execute(
            select(QueueItem).where(QueueItem.status == QueueStatus.PENDING).order_by(QueueItem.id.asc()).limit(10)
        )
        pending = pending_items.scalars().all()
        
        text = ""
        if playing:
            await session.refresh(playing, ['song'])
            text += f"📋 <b>СЕЙЧАС</b>\n▶️ {playing.song.artist} — {playing.song.title}\n\n"
        else:
            text += "📋 <b>СЕЙЧАС</b>\nНичего не играет\n\n"
            
        text += "📋 <b>ОЧЕРЕДЬ</b>\n"
        if pending:
            for i, item in enumerate(pending):
                await session.refresh(item, ['song'])
                text += f"{i+1}. {item.song.artist} — {item.song.title}\n"
        else:
            text += "Очередь пуста.\n"
            
        await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "remove_song")
async def start_remove_song(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.full_name)
        
        items = await session.execute(
            select(QueueItem).where(
                and_(QueueItem.user_id == user.id, QueueItem.status == QueueStatus.PENDING)
            ).order_by(QueueItem.id.asc())
        )
        items = items.scalars().all()
        
        if not items:
            await callback.answer("У вас нет песен в очереди.", show_alert=True)
            return
            
        text = "Выберите песню для удаления:\n\n"
        keyboard = []
        for i, item in enumerate(items):
            await session.refresh(item, ['song'])
            text += f"{i+1}. {item.song.artist} — {item.song.title}\n"
            keyboard.append([InlineKeyboardButton(text=f"🗑 Удалить {i+1}", callback_data=f"del_{item.id}")])
            
        keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_search")])
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("del_"))
async def process_remove_song(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.full_name)
        
        result = await session.execute(
            select(QueueItem).where(
                and_(QueueItem.id == item_id, QueueItem.user_id == user.id, QueueItem.status == QueueStatus.PENDING)
            )
        )
        item = result.scalar_one_or_none()
        
        if item:
            await session.delete(item)
            await session.commit()
            await callback.answer("Песня удалена из очереди!", show_alert=True)
        else:
            await callback.answer("Песня не найдена или уже играет.", show_alert=True)
            
        # Back to main
        text = (
            "🎵 <b>TAXI MUSIC</b>\n\n"
            "Привет! Вы можете добавить музыку в очередь водителя."
        )
        await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

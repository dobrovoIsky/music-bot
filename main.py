import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from database import init_db
from api import router as api_router
from bot import bot, dp
from handlers import router as bot_router
import os

dp.include_router(bot_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup database
    await init_db()
    
    # Start bot polling in background
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    yield
    
    # Teardown
    await bot.session.close()
    bot_task.cancel()

app = FastAPI(lifespan=lifespan)

# Static files for frontend
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# API routes
app.include_router(api_router)

@app.get("/")
async def serve_panel():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

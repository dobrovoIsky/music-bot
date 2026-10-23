import asyncio
import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager

from database import init_db
from api import router as api_router
from bot import bot, dp
from handlers import router as bot_router
import os

KEEP_ALIVE_INTERVAL = 10 * 60  # 10 minutes

async def self_ping_task():
    """Ping our own /health endpoint every 10 min to prevent Render from sleeping."""
    # Give the server a moment to fully start
    await asyncio.sleep(30)
    # Determine the URL to ping
    base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
    health_url = f"{base_url}/health"
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(health_url)
                print(f"[keep-alive] GET {health_url} -> {resp.status_code}")
        except Exception as e:
            print(f"[keep-alive] ping failed: {e}")
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)

dp.include_router(bot_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup database
    await init_db()
    
    # Start bot polling in background
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    # Start self-ping keep-alive task
    ping_task = asyncio.create_task(self_ping_task())
    
    yield
    
    # Teardown
    ping_task.cancel()
    await bot.session.close()
    bot_task.cancel()

app = FastAPI(lifespan=lifespan)

# Static files for frontend
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# API routes
app.include_router(api_router)

@app.get("/health")
async def health_check():
    """Health check endpoint — used by keep-alive pings and external monitors."""
    return JSONResponse({"status": "ok"})

@app.get("/")
async def serve_panel():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

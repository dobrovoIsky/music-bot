from ytmusicapi import YTMusic
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ytmusicapi is synchronous, so we run it in a threadpool to not block the async event loop
ytmusic = YTMusic()
executor = ThreadPoolExecutor(max_workers=3)

async def search_song(query: str, limit: int = 3):
    loop = asyncio.get_event_loop()
    try:
        # We search for songs in YouTube Music
        results = await loop.run_in_executor(executor, lambda: ytmusic.search(query, filter="songs", limit=limit))
        
        formatted_results = []
        for item in results:
            if item.get("resultType") != "song" or not item.get("videoId"):
                continue
                
            title = item.get("title", "Unknown")
            # Extract artist name
            artists = item.get("artists", [])
            artist = artists[0]["name"] if artists else "Unknown"
            
            # Extract best thumbnail
            thumbnails = item.get("thumbnails", [])
            cover_url = thumbnails[-1]["url"] if thumbnails else ""
            
            formatted_results.append({
                "title": title,
                "artist": artist,
                "cover_url": cover_url,
                "youtube_id": item["videoId"]
            })
            
            if len(formatted_results) >= limit:
                break
                
        return formatted_results
    except Exception as e:
        print(f"YouTube Search Error: {e}")
        return []

import httpx
import urllib.parse

async def search_song(query: str, limit: int = 3):
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit={limit}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("trackName", "Unknown"),
                    "artist": item.get("artistName", "Unknown"),
                    "cover_url": item.get("artworkUrl100", ""),
                    "itunes_id": str(item.get("trackId", ""))
                })
            return results
        except Exception as e:
            print(f"iTunes API Error: {e}")
            return []

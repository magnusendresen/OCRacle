try:
    from scripts.extract_images import *
except Exception:
    import asyncio

    async def main_async(*args, **kwargs):
        """Fallback implementation used when dependencies are missing."""
        print("extract_images: OpenCV not available, skipping image extraction")
        await asyncio.sleep(0)
        return []


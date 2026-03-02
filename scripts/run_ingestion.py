"""Manually trigger ingestion for one or all sources (no Celery needed)."""

import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

from backend.ingestion.connector_registry import get_connector, CONNECTORS


async def run_source(source: str):
    print(f"\n🔄 Running connector: {source}")
    connector = get_connector(source)
    try:
        tenders = await connector.fetch_tenders()
        print(f"   ✅ Fetched {len(tenders)} tenders from {source}")
        for t in tenders[:3]:
            print(f"      - {t.title[:80]}")
        if len(tenders) > 3:
            print(f"      ... and {len(tenders) - 3} more")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        await connector.close()


async def main():
    sources = sys.argv[1:] if len(sys.argv) > 1 else list(CONNECTORS.keys())
    print(f"🏛️ Tender Ingestion — Sources: {', '.join(sources)}")
    
    for source in sources:
        if source not in CONNECTORS:
            print(f"⚠️ Unknown source: {source}")
            continue
        await run_source(source)
    
    print("\n✅ Done")


if __name__ == "__main__":
    asyncio.run(main())

"""
crawl4ai_debug.py
Voir ce que Crawl4AI récupère vraiment
"""
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def debug_ah():
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=['--disable-blink-features=AutomationControlled']
    )
    
    crawl_config = CrawlerRunConfig(
        wait_until="networkidle",
        page_timeout=60000,
        delay_before_return_html=8.0,  # Attendre plus longtemps
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url='https://www.alternatehistory.com/forum/forums/finished-timelines.72/',
            config=crawl_config
        )
        
        # Sauvegarder le HTML pour inspection
        with open('/app/debug_page.html', 'w', encoding='utf-8') as f:
            f.write(result.html)
        
        print(f"HTML sauvegardé: /app/debug_page.html ({len(result.html)} bytes)")
        print("\nPremiers 2000 caractères:")
        print(result.html[:2000])

asyncio.run(debug_ah())

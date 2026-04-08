"""
crawl4ai_test.py
Test avec Crawl4AI (anti-détection avancé)
"""
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup

async def test_ah():
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-web-security',
        ]
    )
    
    crawl_config = CrawlerRunConfig(
        wait_until="networkidle",
        page_timeout=60000,
        delay_before_return_html=5.0,  # Attendre 5s
    )
    
    print("Test Crawl4AI sur AlternateHistory.com...")
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url='https://www.alternatehistory.com/forum/forums/finished-timelines.72/',
            config=crawl_config
        )
        
        if not result.success:
            print(f"❌ Échec: {result.error_message}")
            return
        
        print(f"✓ Success: {result.success}")
        print(f"  HTML size: {len(result.html)//1024} KB")
        
        # Parser
        soup = BeautifulSoup(result.html, 'lxml')
        
        # Vérifier Cloudflare
        if 'cloudflare' in result.html.lower() and 'blocked' in result.html.lower():
            print("❌ Bloqué par Cloudflare")
            return
        
        # Chercher threads
        threads = soup.select('div.structItem--thread')
        print(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            print("✅ CRAWL4AI FONCTIONNE!")
            for i, thread in enumerate(threads[:5], 1):
                title = thread.select_one('div.structItem-title a')
                if title:
                    print(f"  [{i}] {title.get_text(strip=True)}")

asyncio.run(test_ah())

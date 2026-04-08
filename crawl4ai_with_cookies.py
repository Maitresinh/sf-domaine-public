"""
crawl4ai_with_cookies.py
Crawl4AI avec cookies via page context
"""
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup

async def scrape_with_cookies():
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=['--disable-blink-features=AutomationControlled']
    )
    
    # Cookies à injecter
    cookies = [
        {
            'name': 'xf_user',
            'value': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
            'domain': '.alternatehistory.com',
            'path': '/',
            'secure': True,
            'httpOnly': True
        },
        {
            'name': 'xf_session',
            'value': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN',
            'domain': '.alternatehistory.com',
            'path': '/',
            'secure': True,
            'httpOnly': True
        }
    ]
    
    crawl_config = CrawlerRunConfig(
        wait_until="networkidle",
        delay_before_return_html=3.0,
        js_code=f"""
        // Injecter les cookies
        const cookies = {str(cookies).replace("'", '"')};
        for (const cookie of cookies) {{
            document.cookie = `${{cookie.name}}=${{cookie.value}}; domain=${{cookie.domain}}; path=${{cookie.path}}`;
        }}
        """
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        print("🔐 Scraping avec authentification...")
        
        result = await crawler.arun(
            url='https://www.alternatehistory.com/forum/forums/finished-timelines.72/',
            config=crawl_config
        )
        
        if not result.success:
            print(f"❌ Échec: {result.error_message}")
            return
        
        print(f"✓ HTML récupéré: {len(result.html)//1024} KB")
        
        # Vérifier connexion
        if 'Maitresinh' in result.html or 'maitresinh' in result.html.lower():
            print("✅ CONNECTÉ en tant que Maitresinh!")
        else:
            print("⚠️ Connexion incertaine")
        
        soup = BeautifulSoup(result.html, 'lxml')
        threads = soup.select('div.structItem--thread')
        print(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            print("\n✅ ÇA MARCHE!")
            for i, thread in enumerate(threads[:5], 1):
                title = thread.select_one('div.structItem-title a')
                if title:
                    print(f"  [{i}] {title.get_text(strip=True)}")
        else:
            print("Debug: sauvegarde HTML")
            with open('/app/debug_logged.html', 'w', encoding='utf-8') as f:
                f.write(result.html[:5000])
            print("Premiers 1000 caractères:")
            print(result.html[:1000])

asyncio.run(scrape_with_cookies())

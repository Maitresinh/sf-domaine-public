"""
playwright_cookies.py
Playwright direct avec cookies
"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def scrape_with_playwright():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Créer contexte avec cookies
        context = await browser.new_context()
        
        # Ajouter les cookies
        await context.add_cookies([
            {
                'name': 'xf_user',
                'value': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
                'domain': '.alternatehistory.com',
                'path': '/'
            },
            {
                'name': 'xf_session',
                'value': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN',
                'domain': '.alternatehistory.com',
                'path': '/'
            }
        ])
        
        page = await context.new_page()
        
        print("🔐 Navigation avec cookies...")
        await page.goto('https://www.alternatehistory.com/forum/forums/finished-timelines.72/', 
                       wait_until='networkidle')
        
        # Attendre un peu
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        
        print(f"✓ HTML: {len(html)//1024} KB")
        
        # Vérifier connexion
        if 'Maitresinh' in html:
            print("✅ CONNECTÉ!")
        elif 'data-logged-in="true"' in html:
            print("✅ Connecté (détecté par attribut)")
        else:
            print("❌ Pas connecté")
            print("data-logged-in:", 'true' if 'data-logged-in="true"' in html else 'false')
        
        soup = BeautifulSoup(html, 'lxml')
        threads = soup.select('div.structItem--thread')
        
        print(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            print("\n✅ SUCCESS!")
            for i, thread in enumerate(threads[:5], 1):
                title = thread.select_one('div.structItem-title a')
                if title:
                    print(f"  [{i}] {title.get_text(strip=True)}")
        else:
            print("\nPremiers 1500 caractères:")
            print(html[:1500])
        
        await browser.close()

asyncio.run(scrape_with_playwright())

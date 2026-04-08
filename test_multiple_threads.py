"""
Tester plusieurs threads différents
"""
import asyncio
from camoufox.async_api import AsyncCamoufox
from bs4 import BeautifulSoup

# Tester 3 threads différents
TEST_THREADS = [
    ("README/FAQ", "https://www.alternatehistory.com/forum/threads/readme-faq-how-the-timelines-and-scenarios-forum-works.26647/"),
    ("Kentucky Fried Politics", "https://www.alternatehistory.com/forum/threads/kentucky-fried-politics-a-colonel-sanders-timeline.383920/"),
    ("Keynes Cruisers", "https://www.alternatehistory.com/forum/threads/keynes-cruisers.391114/"),
]

async def test_threads():
    print("🧪 Test accès multiple threads...\n")
    
    async with AsyncCamoufox(headless=True, humanize=True) as browser:
        page = await browser.new_page()
        
        # Login
        print("🔐 Login...")
        await page.goto('https://www.alternatehistory.com/forum/login/')
        await page.wait_for_load_state('networkidle')
        await page.fill('input[name="login"]', 'Maitresinh')
        await page.fill('input[name="password"]', 'Roger333,')
        await page.click('form[action*="login"] button[type="submit"]')
        await page.wait_for_load_state('networkidle')
        print("✓ Connecté\n")
        
        # Tester chaque thread
        for name, url in TEST_THREADS:
            print(f"📖 Test: {name}")
            print(f"   URL: {url}")
            
            await page.goto(url)
            await page.wait_for_load_state('networkidle')
            
            html = await page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # Vérifier erreur
            if 'Oops! We ran into some problems' in html:
                print(f"   ❌ Page d'erreur XenForo")
                # Extraire le message d'erreur
                error_div = soup.select_one('div.blockMessage')
                if error_div:
                    print(f"   Message: {error_div.get_text(strip=True)}")
            else:
                posts = soup.select('article.message')
                print(f"   ✅ {len(posts)} posts trouvés")
                if posts:
                    author = posts[0].select_one('h4.message-name a.username')
                    if author:
                        print(f"   Auteur: {author.get_text(strip=True)}")
            
            print()
            await asyncio.sleep(5)  # Délai entre threads

asyncio.run(test_threads())

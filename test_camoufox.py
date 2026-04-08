"""
test_camoufox.py
Tester Camoufox pour scraper un thread
"""
import asyncio
from camoufox.async_api import AsyncCamoufox
from bs4 import BeautifulSoup

async def test_thread_with_camoufox():
    print("🦊 Lancement Camoufox...")
    
    # Configuration Camoufox
    async with AsyncCamoufox(
        headless=True,
        humanize=True,  # Comportement humain
        geoip=False
    ) as browser:
        
        page = await browser.new_page()
        
        print("🔐 Connexion au forum...")
        await page.goto('https://www.alternatehistory.com/forum/login/')
        await page.wait_for_load_state('networkidle')
        
        # Remplir formulaire login
        await page.fill('input[name="login"]', 'Maitresinh')
        await page.fill('input[name="password"]', 'Roger333,')
        
        # Soumettre
        await page.click('button[type="submit"]')
        await page.wait_for_load_state('networkidle')
        
        print("✓ Connecté")
        
        # Aller sur un thread
        thread_url = 'https://www.alternatehistory.com/forum/threads/keynes-cruisers.391114/'
        print(f"\n📖 Accès thread: {thread_url}")
        
        await page.goto(thread_url)
        await page.wait_for_load_state('networkidle')
        
        # Récupérer HTML
        html = await page.content()
        
        print(f"✓ HTML: {len(html)//1024} KB")
        
        # Parser
        soup = BeautifulSoup(html, 'lxml')
        
        # Vérifier si bloqué
        if 'blocked' in html.lower() and 'cloudflare' in html.lower():
            print("❌ Toujours bloqué Cloudflare")
            return
        
        # Chercher posts
        posts = soup.select('article.message')
        print(f"✓ {len(posts)} posts trouvés")
        
        if posts:
            print("\n✅ SUCCESS! Camoufox bypass Cloudflare + XenForo!")
            
            # Premier post
            first = posts[0]
            author = first.select_one('h4.message-name a.username')
            content = first.select_one('div.bbWrapper')
            
            if author:
                print(f"\nPremier post par: {author.get_text(strip=True)}")
            if content:
                text = content.get_text(strip=True)
                print(f"Contenu ({len(text.split())} mots):")
                print(f"{text[:300]}...")
            
            # Sauvegarder
            with open('/app/camoufox_success.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("\n💾 HTML sauvegardé: /app/camoufox_success.html")
            
        else:
            print("⚠️ Aucun post trouvé")
            print("Début HTML:")
            print(html[:1000])

asyncio.run(test_thread_with_camoufox())

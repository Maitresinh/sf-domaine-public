"""
Camoufox avec bon sélecteur
"""
import asyncio
from camoufox.async_api import AsyncCamoufox
from bs4 import BeautifulSoup

async def test_camoufox():
    print("🦊 Camoufox...")
    
    async with AsyncCamoufox(
        headless=True,
        humanize=True
    ) as browser:
        
        page = await browser.new_page()
        
        print("🔐 Login...")
        await page.goto('https://www.alternatehistory.com/forum/login/')
        await page.wait_for_load_state('networkidle')
        
        # Remplir
        await page.fill('input[name="login"]', 'Maitresinh')
        await page.fill('input[name="password"]', 'Roger333,')
        
        # BON sélecteur : bouton dans le formulaire de login
        await page.click('form[action*="login"] button[type="submit"]')
        await page.wait_for_load_state('networkidle')
        
        print("✓ Login soumis")
        
        # Vérifier connexion
        content = await page.content()
        if 'Maitresinh' in content or 'maitresinh' in content.lower():
            print("✅ CONNECTÉ!")
        else:
            print("⚠️ Connexion incertaine")
        
        # Thread
        url = 'https://www.alternatehistory.com/forum/threads/keynes-cruisers.391114/'
        print(f"\n📖 Accès thread: {url}")
        
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        
        html = await page.content()
        print(f"HTML: {len(html)//1024} KB")
        
        # Parser
        soup = BeautifulSoup(html, 'lxml')
        posts = soup.select('article.message')
        
        print(f"✓ {len(posts)} posts trouvés")
        
        if posts:
            print("\n🎉 SUCCESS COMPLET! Camoufox bypass tout!")
            
            # Premier post
            first = posts[0]
            author = first.select_one('h4.message-name a.username')
            content_elem = first.select_one('div.bbWrapper')
            
            if author:
                print(f"\nPremier post par: {author.get_text(strip=True)}")
            if content_elem:
                text = content_elem.get_text(strip=True)
                print(f"Contenu: {len(text.split())} mots")
                print(f"{text[:300]}...")
            
            # Sauvegarder
            with open('/app/camoufox_thread_success.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("\n💾 HTML sauvegardé")
            
        else:
            print("\n⚠️ Aucun post")
            print("Début HTML:")
            print(html[:1000])

asyncio.run(test_camoufox())

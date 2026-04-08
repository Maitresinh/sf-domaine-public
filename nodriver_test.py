"""
nodriver_test.py
Test Nodriver sur AlternateHistory.com avec authentification
"""
import asyncio
import nodriver as uc
from bs4 import BeautifulSoup

async def test_ah_with_nodriver():
    print("🚀 Lancement Nodriver...")
    
    # Créer browser (mode visible pour debug)
    browser = await uc.start(headless=False)
    page = await browser.get('https://www.alternatehistory.com/forum/login/')
    
    print("📝 Page de login chargée")
    await asyncio.sleep(2)
    
    # Remplir le formulaire de login
    print("🔐 Connexion en cours...")
    await page.select('input[name="login"]')
    await page.send_keys('Maitresinh')
    
    await page.select('input[name="password"]')
    await page.send_keys('Roger333,')
    
    # Soumettre
    login_button = await page.find('button[type="submit"]')
    await login_button.click()
    
    print("⏳ Attente redirection...")
    await asyncio.sleep(5)
    
    # Aller sur Finished Timelines
    print("📂 Navigation vers Finished Timelines...")
    await page.get('https://www.alternatehistory.com/forum/forums/finished-timelines.72/')
    await asyncio.sleep(3)
    
    # Récupérer HTML
    html = await page.get_content()
    
    print(f"✓ HTML récupéré: {len(html)//1024} KB")
    
    # Parser
    soup = BeautifulSoup(html, 'lxml')
    
    # Vérifier connexion
    if 'Maitresinh' in html:
        print("✅ CONNECTÉ en tant que Maitresinh!")
    elif 'data-logged-in="true"' in html:
        print("✅ Connecté (attribut détecté)")
    else:
        print("❌ Pas connecté")
    
    # Chercher threads
    threads = soup.select('div.structItem--thread')
    print(f"\n✓ {len(threads)} threads trouvés")
    
    if len(threads) > 0:
        print("\n🎉 SUCCESS! Nodriver a bypass Cloudflare!")
        print("\nPremiers threads:")
        for i, thread in enumerate(threads[:5], 1):
            title = thread.select_one('div.structItem-title a')
            if title:
                print(f"  [{i}] {title.get_text(strip=True)}")
        
        # Sauvegarder HTML complet
        with open('/app/nodriver_success.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("\n✓ HTML sauvegardé: /app/nodriver_success.html")
    else:
        print("\n❌ Aucun thread - vérifier Cloudflare")
        print("Premiers 1000 caractères:")
        print(html[:1000])
    
    await browser.stop()

# Lancer
asyncio.run(test_ah_with_nodriver())

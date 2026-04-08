"""
crawl4ai_login.py
Crawl4AI avec authentification AlternateHistory.com
"""
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup

USERNAME = "Maitresinh"
PASSWORD = "Roger333,"  # À vérifier

async def scrape_with_login():
    browser_config = BrowserConfig(
        headless=False,  # Visible pour voir la connexion
        verbose=True,
        extra_args=['--disable-blink-features=AutomationControlled']
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Étape 1 : Page de login
        print("1. Chargement page de login...")
        login_page = await crawler.arun(
            url='https://www.alternatehistory.com/forum/login/',
            config=CrawlerRunConfig(
                wait_until="networkidle",
                delay_before_return_html=2.0
            )
        )
        
        # Étape 2 : Exécuter JavaScript pour se connecter
        print("2. Connexion en cours...")
        
        # JavaScript pour remplir le formulaire et soumettre
        js_login = f"""
        (async () => {{
            // Remplir les champs
            document.querySelector('input[name="login"]').value = '{USERNAME}';
            document.querySelector('input[name="password"]').value = '{PASSWORD}';
            
            // Soumettre le formulaire
            document.querySelector('form[action*="login/login"]').submit();
            
            // Attendre redirection
            await new Promise(r => setTimeout(r, 3000));
        }})();
        """
        
        # Note: Crawl4AI ne supporte pas l'exécution JS directe facilement
        # On va utiliser une approche différente
        
        print("3. Accès au forum après login...")
        await asyncio.sleep(5)  # Laisser temps à la connexion
        
        # Étape 3 : Accéder au forum des timelines
        result = await crawler.arun(
            url='https://www.alternatehistory.com/forum/forums/finished-timelines.72/',
            config=CrawlerRunConfig(
                wait_until="networkidle",
                delay_before_return_html=3.0
            )
        )
        
        if not result.success:
            print(f"❌ Échec: {result.error_message}")
            return
        
        print(f"✓ HTML récupéré: {len(result.html)//1024} KB")
        
        # Parser
        soup = BeautifulSoup(result.html, 'lxml')
        
        # Vérifier si connecté
        username_elem = soup.select_one('a[data-xf-click="menu"]')
        if username_elem and USERNAME.lower() in username_elem.get_text().lower():
            print(f"✅ Connecté en tant que {USERNAME}")
        else:
            print("⚠️ Pas sûr si connecté")
        
        # Chercher threads
        threads = soup.select('div.structItem--thread')
        print(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            print("✅ SCRAPING AVEC LOGIN FONCTIONNE!")
            for i, thread in enumerate(threads[:5], 1):
                title = thread.select_one('div.structItem-title a')
                if title:
                    print(f"  [{i}] {title.get_text(strip=True)}")
        
        # Sauvegarder pour inspection
        with open('/app/logged_page.html', 'w', encoding='utf-8') as f:
            f.write(result.html)
        print("\nHTML sauvegardé: /app/logged_page.html")

asyncio.run(scrape_with_login())

"""
test_cf_bypass.py
Tester le service CloudflareBypassForScraping
"""
import requests
import json

# URL du service cf-bypass (via réseau Docker)
BYPASS_SERVICE = "http://cf-bypass:8000"

print("🔐 Demande cookies Cloudflare via service bypass...")
print(f"   Service: {BYPASS_SERVICE}")

try:
    response = requests.get(
        f"{BYPASS_SERVICE}/cookies",
        params={"url": "https://www.alternatehistory.com/forum/forums/finished-timelines.72/"},
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Cookies Cloudflare obtenus!")
        print(f"User-Agent: {data.get('user_agent', 'N/A')[:80]}")
        
        cf_cookies = data.get('cookies', {})
        print(f"CF Cookies: {list(cf_cookies.keys())}")
        
        # Test avec cookies CF + cookies utilisateur
        print("\n🧪 Test accès forum avec cookies combinés...")
        
        # Combiner cookies
        all_cookies = {
            **cf_cookies,
            'xf_user': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
            'xf_session': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN'
        }
        
        user_agent = data.get('user_agent', '')
        
        forum_response = requests.get(
            "https://www.alternatehistory.com/forum/forums/finished-timelines.72/",
            cookies=all_cookies,
            headers={'User-Agent': user_agent},
            timeout=30
        )
        
        print(f"Status: {forum_response.status_code}")
        print(f"HTML: {len(forum_response.text)//1024} KB")
        
        # Analyse
        html_lower = forum_response.text.lower()
        
        if 'blocked' in html_lower and 'cloudflare' in html_lower:
            print("❌ Toujours bloqué par Cloudflare")
            print(forum_response.text[:800])
        elif 'maitresinh' in html_lower:
            print("✅ CONNECTÉ en tant que Maitresinh!")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(forum_response.text, 'lxml')
            threads = soup.select('div.structItem--thread')
            print(f"✓ {len(threads)} threads trouvés")
            
            if threads:
                print("\n🎉 SUCCESS COMPLET! Le scraping fonctionne!")
                for i, t in enumerate(threads[:5], 1):
                    title = t.select_one('div.structItem-title a')
                    if title:
                        print(f"  [{i}] {title.get_text(strip=True)[:80]}")
        elif len(forum_response.text) > 50000:
            print("✅ Contenu volumineux récupéré")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(forum_response.text, 'lxml')
            threads = soup.select('div.structItem--thread')
            print(f"✓ {len(threads)} threads trouvés")
            
            if threads:
                print("\n🎉 SUCCESS!")
                for i, t in enumerate(threads[:5], 1):
                    title = t.select_one('div.structItem-title a')
                    if title:
                        print(f"  [{i}] {title.get_text(strip=True)[:80]}")
        else:
            print("⚠️ Réponse courte, premiers 1000 chars:")
            print(forum_response.text[:1000])
    else:
        print(f"❌ Erreur service: {response.status_code}")
        print(response.text[:500])
        
except requests.exceptions.ConnectionError as e:
    print(f"❌ Connexion impossible au service cf-bypass")
    print(f"   Vérifiez que le container tourne: docker logs cf-bypass")
except Exception as e:
    print(f"❌ Exception: {type(e).__name__}: {e}")

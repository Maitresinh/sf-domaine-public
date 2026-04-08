"""
Test avec la bonne URL du forum Finished Timelines
"""
import requests
from bs4 import BeautifulSoup

BYPASS_SERVICE = "http://cf-bypass:8000"

print("🔐 Obtention cookies CF...")

# Obtenir cookies CF
resp = requests.get(
    f"{BYPASS_SERVICE}/cookies",
    params={"url": "https://www.alternatehistory.com/forum/"},
    timeout=120
)

cf_cookies = resp.json().get('cookies', {})
user_agent = resp.json().get('user_agent', '')

all_cookies = {
    **cf_cookies,
    'xf_user': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
    'xf_session': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN'
}

print("✓ Cookies obtenus")
print(f"\n📂 Accès Finished Timelines and Scenarios...")

# LA BONNE URL
url = "https://www.alternatehistory.com/forum/forums/finished-timelines-and-scenarios.18/"

r = requests.get(url, cookies=all_cookies, headers={'User-Agent': user_agent}, timeout=30)

print(f"Status: {r.status_code}")
print(f"HTML: {len(r.text)//1024} KB")

if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'lxml')
    
    # Chercher threads
    threads = soup.select('div.structItem--thread')
    print(f"\n✓ {len(threads)} threads trouvés")
    
    if threads:
        print("\n🎉 SUCCESS COMPLET! Le scraping fonctionne!")
        print("\nPremiers 10 threads:")
        
        for i, t in enumerate(threads[:10], 1):
            title_elem = t.select_one('div.structItem-title a')
            author_elem = t.select_one('div.structItem-cell--meta a.username')
            replies_elem = t.select_one('dl.pairs--justified dd')
            
            if title_elem:
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                author = author_elem.get_text(strip=True) if author_elem else 'N/A'
                replies = replies_elem.get_text(strip=True) if replies_elem else '0'
                
                print(f"\n  [{i}] {title[:80]}")
                print(f"      Auteur: {author} | Réponses: {replies}")
                print(f"      URL: https://www.alternatehistory.com{url}")
        
        # Sauvegarder pour analyse
        with open('/app/finished_timelines.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        print("\n✓ HTML sauvegardé: /app/finished_timelines.html")
        
        print("\n✅ VALIDATION: Le bypass Cloudflare + authentification fonctionne!")
        print("   Prêt pour le scraping complet!")
    else:
        print("⚠️ Aucun thread trouvé")
        print("Début HTML:")
        print(r.text[:1000])
else:
    print(f"❌ Erreur {r.status_code}")

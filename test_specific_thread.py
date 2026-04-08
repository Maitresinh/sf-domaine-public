"""
Test avec URL de thread spécifique
"""
import requests
from bs4 import BeautifulSoup

BYPASS_SERVICE = "http://cf-bypass:8000"

print("🔍 Test plusieurs URLs...")

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

# Test plusieurs URLs
urls = [
    "https://www.alternatehistory.com/forum/",
    "https://www.alternatehistory.com/forum/forums/finished-timelines.72/",
    "https://www.alternatehistory.com/forum/forums/finished-timelines.72/page-1",
]

for url in urls:
    print(f"\n📍 Test: {url}")
    r = requests.get(url, cookies=all_cookies, headers={'User-Agent': user_agent}, timeout=30)
    print(f"   Status: {r.status_code} | Size: {len(r.text)//1024} KB")
    
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'lxml')
        
        # Chercher threads
        threads = soup.select('div.structItem--thread')
        print(f"   ✓ {len(threads)} threads")
        
        if threads:
            print("   🎉 SUCCESS! Voici les threads:")
            for i, t in enumerate(threads[:5], 1):
                title = t.select_one('div.structItem-title a')
                if title:
                    print(f"     [{i}] {title.get_text(strip=True)[:80]}")
            break
        
        # Sauvegarder HTML pour inspection
        with open(f'/app/debug_{r.status_code}.html', 'w') as f:
            f.write(r.text)
        print(f"   HTML sauvegardé: /app/debug_{r.status_code}.html")
        
        # Afficher début HTML
        print(f"   Début HTML:\n{r.text[:500]}")

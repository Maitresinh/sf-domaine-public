"""
Scraper avec comportement très humain
Délais longs + requêtes espacées
"""
import requests
from bs4 import BeautifulSoup
import time
import random

BYPASS_SERVICE = "http://cf-bypass:8000"
BASE_URL = "https://www.alternatehistory.com"

def get_session():
    """Nouvelle session avec cookies frais"""
    print("   🔄 Renouvellement cookies...")
    resp = requests.get(
        f"{BYPASS_SERVICE}/cookies",
        params={"url": f"{BASE_URL}/forum/"},
        timeout=120
    )
    data = resp.json()
    return {
        **data.get('cookies', {}),
        'xf_user': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
        'xf_session': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN'
    }, data.get('user_agent', '')

print("🐢 Scraper ultra-lent (comportement humain)")

# Délai initial
wait = random.randint(15, 25)
print(f"⏳ Attente initiale {wait}s...")
time.sleep(wait)

# Obtenir cookies
cookies, ua = get_session()

# Attendre encore
time.sleep(10)

# Tester thread
url = "https://www.alternatehistory.com/forum/threads/keynes-cruisers.391114/"
print(f"\n📖 Accès: {url}")

r = requests.get(url, cookies=cookies, headers={'User-Agent': ua}, timeout=30)

print(f"Status: {r.status_code}")
print(f"Size: {len(r.text)//1024} KB")

if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'lxml')
    posts = soup.select('article.message')
    print(f"✓ {len(posts)} posts trouvés")
    
    if posts:
        print("\n✅ SUCCESS avec délais ultra-longs!")
        print("   → On peut scraper les 307 timelines avec ce rythme")
        print(f"   → Temps estimé: ~{307 * 30 / 3600:.1f}h pour tout")
    else:
        print("⚠️ Pas de posts, HTML sauvegardé")
        with open('/app/human_test.html', 'w') as f:
            f.write(r.text[:5000])
else:
    print(f"❌ Échec {r.status_code}")
    print(r.text[:800])

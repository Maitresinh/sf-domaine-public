"""
Debug thread scraping
"""
import requests
from bs4 import BeautifulSoup

BYPASS_SERVICE = "http://cf-bypass:8000"
BASE_URL = "https://www.alternatehistory.com"
TEST_THREAD_URL = f"{BASE_URL}/forum/threads/keynes-cruisers.391114/"

def get_cf_cookies():
    resp = requests.get(
        f"{BYPASS_SERVICE}/cookies",
        params={"url": f"{BASE_URL}/forum/"},
        timeout=120
    )
    return resp.json()

print("🔍 Debug du scraping thread...")

# Cookies
cf_data = get_cf_cookies()
all_cookies = {
    **cf_data.get('cookies', {}),
    'xf_user': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
    'xf_session': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN'
}
user_agent = cf_data.get('user_agent', '')

print(f"📖 Test URL: {TEST_THREAD_URL}")

# Tenter d'accéder
r = requests.get(TEST_THREAD_URL, cookies=all_cookies, headers={'User-Agent': user_agent}, timeout=30)

print(f"Status: {r.status_code}")
print(f"HTML size: {len(r.text)//1024} KB")

if r.status_code != 200:
    print(f"\n❌ Erreur {r.status_code}")
    print("Premiers 1000 caractères:")
    print(r.text[:1000])
else:
    soup = BeautifulSoup(r.text, 'lxml')
    
    # Chercher posts
    posts = soup.select('article.message')
    print(f"\n✓ {len(posts)} posts trouvés")
    
    if posts:
        print("\nPremier post:")
        first = posts[0]
        author = first.select_one('h4.message-name a.username')
        content = first.select_one('div.bbWrapper')
        
        if author:
            print(f"  Auteur: {author.get_text(strip=True)}")
        if content:
            print(f"  Contenu (extrait): {content.get_text(strip=True)[:200]}...")
    else:
        print("\n⚠️ Aucun post - vérifier les sélecteurs")
        print("Structure HTML:")
        print(r.text[:2000])
    
    # Sauvegarder HTML pour inspection
    with open('/app/thread_debug.html', 'w', encoding='utf-8') as f:
        f.write(r.text)
    print("\n💾 HTML sauvegardé: /app/thread_debug.html")

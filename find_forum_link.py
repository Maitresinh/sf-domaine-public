"""
Trouver le vrai lien vers Finished Timelines
"""
import requests
from bs4 import BeautifulSoup

BYPASS_SERVICE = "http://cf-bypass:8000"

print("🔍 Recherche du lien Finished Timelines...")

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

# Charger page d'accueil
r = requests.get(
    "https://www.alternatehistory.com/forum/",
    cookies=all_cookies,
    headers={'User-Agent': user_agent},
    timeout=30
)

print(f"Status: {r.status_code}")

if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'lxml')
    
    # Chercher tous les liens contenant "timeline" ou "finished"
    print("\n📂 Liens contenant 'timeline' ou 'finished':")
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if 'timeline' in text.lower() or 'finished' in text.lower():
            print(f"  • {text[:60]}")
            print(f"    → {href}")
    
    # Chercher structure des forums
    print("\n📋 Tous les forums disponibles:")
    
    forums = soup.select('div.node--forum, div.node--category')
    for forum in forums[:20]:
        title = forum.select_one('a.node-title, h3.node-title a')
        if title:
            href = title.get('href', '')
            text = title.get_text(strip=True)
            print(f"  • {text[:60]}")
            print(f"    → {href}")
    
    # Sauvegarder HTML complet
    with open('/app/homepage.html', 'w', encoding='utf-8') as f:
        f.write(r.text)
    print("\n✓ HTML complet sauvegardé: /app/homepage.html")
    
else:
    print(f"❌ Erreur: {r.status_code}")

"""
scrape_timeline_metadata.py
Scraper complet avec métadonnées pour évaluation
"""
import requests
from bs4 import BeautifulSoup
import json
import time

BYPASS_SERVICE = "http://cf-bypass:8000"
BASE_URL = "https://www.alternatehistory.com"

def get_cf_cookies():
    """Obtenir cookies Cloudflare"""
    resp = requests.get(
        f"{BYPASS_SERVICE}/cookies",
        params={"url": f"{BASE_URL}/forum/"},
        timeout=120
    )
    return resp.json()

def scrape_forum_page(url, cookies, user_agent):
    """Scraper une page du forum"""
    r = requests.get(url, cookies=cookies, headers={'User-Agent': user_agent}, timeout=30)
    
    if r.status_code != 200:
        return None
    
    soup = BeautifulSoup(r.text, 'lxml')
    threads = soup.select('div.structItem--thread')
    
    timeline_list = []
    
    for thread in threads:
        # Titre et URL
        title_elem = thread.select_one('div.structItem-title a')
        if not title_elem:
            continue
        
        title = title_elem.get_text(strip=True)
        thread_url = title_elem.get('href', '')
        thread_id = thread_url.split('.')[-2] if '.' in thread_url else None
        
        # Auteur
        author_elem = thread.select_one('a.username')
        author = author_elem.get_text(strip=True) if author_elem else 'Unknown'
        
        # Métadonnées
        replies_elem = thread.select_one('dl.pairs--justified dd')
        replies = replies_elem.get_text(strip=True) if replies_elem else '0'
        
        views_elem = thread.select_one('dl.pairs--justified:nth-of-type(2) dd')
        views = views_elem.get_text(strip=True) if views_elem else '0'
        
        # Date de dernier post
        last_post_elem = thread.select_one('time')
        last_post_date = last_post_elem.get('datetime', '') if last_post_elem else ''
        last_post_relative = last_post_elem.get_text(strip=True) if last_post_elem else ''
        
        # Statut (sticky, locked, etc.)
        is_sticky = 'is-sticky' in thread.get('class', [])
        is_locked = thread.select_one('.structItem-status--locked') is not None
        
        # Préfixe (ex: DBWI, Map Game, etc.)
        prefix_elem = thread.select_one('span.label--prefix')
        prefix = prefix_elem.get_text(strip=True) if prefix_elem else None
        
        timeline_data = {
            'thread_id': thread_id,
            'title': title,
            'url': f"{BASE_URL}{thread_url}",
            'author': author,
            'replies': int(replies.replace(',', '')) if replies.replace(',', '').isdigit() else 0,
            'views': int(views.replace(',', '')) if views.replace(',', '').isdigit() else 0,
            'last_post_date': last_post_date,
            'last_post_relative': last_post_relative,
            'is_sticky': is_sticky,
            'is_locked': is_locked,
            'prefix': prefix,
            # Score d'intérêt (simple pour l'instant)
            'interest_score': 0  # Calculé après
        }
        
        # Calcul score d'intérêt simple
        # Plus de réponses + plus de vues = plus intéressant
        timeline_data['interest_score'] = (
            timeline_data['replies'] * 2 +  # Réponses comptent double
            timeline_data['views'] / 100      # Vues divisées par 100
        )
        
        timeline_list.append(timeline_data)
    
    return timeline_list

def main():
    print("🚀 Scraping Finished Timelines avec métadonnées...")
    
    # Obtenir cookies CF
    print("🔐 Obtention cookies Cloudflare...")
    cf_data = get_cf_cookies()
    
    all_cookies = {
        **cf_data.get('cookies', {}),
        'xf_user': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
        'xf_session': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN'
    }
    user_agent = cf_data.get('user_agent', '')
    
    print("✓ Cookies obtenus")
    
    # Scraper première page
    url = f"{BASE_URL}/forum/forums/finished-timelines-and-scenarios.18/"
    print(f"\n📂 Scraping: {url}")
    
    timelines = scrape_forum_page(url, all_cookies, user_agent)
    
    if not timelines:
        print("❌ Aucune timeline récupérée")
        return
    
    print(f"✓ {len(timelines)} timelines récupérées")
    
    # Trier par score d'intérêt
    timelines_sorted = sorted(timelines, key=lambda x: x['interest_score'], reverse=True)
    
    # Afficher top 10
    print("\n🏆 TOP 10 par score d'intérêt:")
    for i, t in enumerate(timelines_sorted[:10], 1):
        print(f"\n  [{i}] {t['title'][:70]}")
        print(f"      Auteur: {t['author']}")
        print(f"      Réponses: {t['replies']:,} | Vues: {t['views']:,}")
        print(f"      Score intérêt: {t['interest_score']:.1f}")
        print(f"      Dernier post: {t['last_post_relative']}")
        if t['prefix']:
            print(f"      Type: {t['prefix']}")
    
    # Sauvegarder en JSON
    output_file = '/app/timelines_metadata.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(timelines_sorted, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Données sauvegardées: {output_file}")
    print(f"   Total: {len(timelines)} timelines")
    
    # Stats
    total_replies = sum(t['replies'] for t in timelines)
    total_views = sum(t['views'] for t in timelines)
    
    print(f"\n📊 Statistiques:")
    print(f"   Total réponses: {total_replies:,}")
    print(f"   Total vues: {total_views:,}")
    print(f"   Moyenne réponses/timeline: {total_replies/len(timelines):.1f}")
    print(f"   Moyenne vues/timeline: {total_views/len(timelines):.1f}")

if __name__ == '__main__':
    main()

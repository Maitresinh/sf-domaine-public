"""
scrape_all_timelines.py
Scraper TOUTES les timelines avec sauvegarde progressive
"""
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

BYPASS_SERVICE = "http://cf-bypass:8000"
BASE_URL = "https://www.alternatehistory.com"
FORUM_URL = f"{BASE_URL}/forum/forums/finished-timelines-and-scenarios.18/"
CHECKPOINT_FILE = "/app/scraping_checkpoint.json"
FINAL_OUTPUT = "/app/all_timelines_metadata.json"

def get_cf_cookies():
    """Obtenir cookies Cloudflare"""
    resp = requests.get(
        f"{BYPASS_SERVICE}/cookies",
        params={"url": f"{BASE_URL}/forum/"},
        timeout=120
    )
    return resp.json()

def parse_number(text):
    """Parser nombre avec virgules/points"""
    if not text:
        return 0
    clean = re.sub(r'[^\d]', '', text)
    return int(clean) if clean.isdigit() else 0

def get_total_pages(soup):
    """Extraire le nombre total de pages"""
    # Chercher "Page X of Y"
    page_info = soup.select_one('li.pageNav-page')
    if page_info:
        text = page_info.get_text(strip=True)
        match = re.search(r'of\s+(\d+)', text)
        if match:
            return int(match.group(1))
    return None

def scrape_forum_page(url, cookies, user_agent):
    """Scraper une page du forum"""
    r = requests.get(url, cookies=cookies, headers={'User-Agent': user_agent}, timeout=30)
    
    if r.status_code != 200:
        return None, None, None
    
    soup = BeautifulSoup(r.text, 'lxml')
    
    # Nombre total de pages (première fois)
    total_pages = get_total_pages(soup)
    
    threads = soup.select('div.structItem--thread')
    timeline_list = []
    
    for thread in threads:
        title_elem = thread.select_one('div.structItem-title a')
        if not title_elem:
            continue
        
        title = title_elem.get_text(strip=True)
        thread_url = title_elem.get('href', '')
        
        match = re.search(r'threads/[^/]+\.(\d+)', thread_url)
        thread_id = match.group(1) if match else None
        
        author_elem = thread.select_one('a.username')
        author = author_elem.get_text(strip=True) if author_elem else 'Unknown'
        
        stats = thread.select('dl.pairs--justified')
        replies = 0
        views = 0
        
        if len(stats) >= 1:
            replies_text = stats[0].select_one('dd')
            if replies_text:
                replies = parse_number(replies_text.get_text())
        
        if len(stats) >= 2:
            views_text = stats[1].select_one('dd')
            if views_text:
                views = parse_number(views_text.get_text())
        
        time_elem = thread.select_one('time')
        last_post_date = time_elem.get('datetime', '') if time_elem else ''
        last_post_relative = time_elem.get_text(strip=True) if time_elem else ''
        
        is_sticky = 'is-sticky' in thread.get('class', [])
        is_locked = thread.select_one('.structItem-status--locked') is not None
        
        prefix_elem = thread.select_one('span.label--prefix')
        prefix = prefix_elem.get_text(strip=True) if prefix_elem else None
        
        timeline_data = {
            'thread_id': thread_id,
            'title': title,
            'url': f"{BASE_URL}{thread_url}" if thread_url.startswith('/') else thread_url,
            'author': author,
            'replies': replies,
            'views': views,
            'last_post_date': last_post_date,
            'last_post_relative': last_post_relative,
            'is_sticky': is_sticky,
            'is_locked': is_locked,
            'prefix': prefix,
            'interest_score': replies * 2 + views / 100
        }
        
        timeline_list.append(timeline_data)
    
    # Next page
    next_link = soup.select_one('a.pageNav-jump--next')
    next_url = None
    if next_link:
        href = next_link.get('href')
        if href:
            next_url = f"{BASE_URL}{href}" if href.startswith('/') else href
    
    return timeline_list, next_url, total_pages

def save_checkpoint(timelines, page_num):
    """Sauvegarde intermédiaire"""
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'page': page_num,
            'count': len(timelines),
            'timelines': timelines
        }, f, indent=2, ensure_ascii=False)

def load_checkpoint():
    """Charger checkpoint si existe"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"📂 Checkpoint trouvé: {data['count']} timelines, page {data['page']}")
            return data['timelines'], data['page']
    return [], 1

def main():
    print("🚀 Scraping TOUTES les Finished Timelines (avec sauvegardes)")
    
    # Charger checkpoint si existe
    all_timelines, start_page = load_checkpoint()
    
    # Cookies
    print("🔐 Obtention cookies...")
    cf_data = get_cf_cookies()
    
    all_cookies = {
        **cf_data.get('cookies', {}),
        'xf_user': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
        'xf_session': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN'
    }
    user_agent = cf_data.get('user_agent', '')
    print("✓ Cookies obtenus\n")
    
    # Première page pour connaître le total
    if start_page == 1:
        print("📊 Détection du nombre total de pages...")
        _, _, total_pages = scrape_forum_page(FORUM_URL, all_cookies, user_agent)
        if total_pages:
            print(f"✓ Total estimé: {total_pages} pages (~{total_pages * 30} timelines)")
            print(f"⏱️ Temps estimé: ~{total_pages * 2 / 60:.1f} minutes\n")
        else:
            print("⚠️ Impossible de détecter le nombre de pages\n")
    
    # Scraping
    current_url = FORUM_URL if start_page == 1 else f"{FORUM_URL}page-{start_page}"
    page_num = start_page
    
    while current_url:
        print(f"📄 Page {page_num}...")
        
        timelines, next_url, _ = scrape_forum_page(current_url, all_cookies, user_agent)
        
        if not timelines:
            print(f"   ⚠️ Aucune timeline")
            break
        
        print(f"   ✓ {len(timelines)} timelines | Total: {len(all_timelines) + len(timelines)}")
        all_timelines.extend(timelines)
        
        # Sauvegarde tous les 10 pages
        if page_num % 10 == 0:
            save_checkpoint(all_timelines, page_num)
            print(f"   💾 Checkpoint sauvegardé")
        
        if not next_url:
            print("   ℹ️ Dernière page")
            break
        
        current_url = next_url
        page_num += 1
        
        time.sleep(2)  # Respect du site
    
    print(f"\n✅ Scraping terminé: {len(all_timelines)} timelines sur {page_num} pages")
    
    # Tri
    all_timelines.sort(key=lambda x: x['interest_score'], reverse=True)
    
    # Top 20
    print("\n🏆 TOP 20 par score d'intérêt:")
    for i, t in enumerate(all_timelines[:20], 1):
        print(f"  [{i}] {t['title'][:60]}")
        print(f"      {t['author']} | R:{t['replies']:,} V:{t['views']:,} | Score:{t['interest_score']:.0f}")
    
    # Sauvegarde finale
    with open(FINAL_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(all_timelines, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Sauvegarde finale: {FINAL_OUTPUT}")
    
    # Stats
    print(f"\n📊 Statistiques:")
    print(f"   Timelines: {len(all_timelines)}")
    print(f"   Réponses totales: {sum(t['replies'] for t in all_timelines):,}")
    print(f"   Vues totales: {sum(t['views'] for t in all_timelines):,}")
    
    # Nettoyer checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

if __name__ == '__main__':
    main()

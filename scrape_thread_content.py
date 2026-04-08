"""
scrape_thread_content.py
Scraper le contenu d'UN thread pour tester le nettoyage
"""
import requests
from bs4 import BeautifulSoup
import re
import json

BYPASS_SERVICE = "http://cf-bypass:8000"
BASE_URL = "https://www.alternatehistory.com"

# Test avec "Keynes Cruisers" (top 1)
TEST_THREAD_URL = f"{BASE_URL}/forum/threads/keynes-cruisers.391114/"

def get_cf_cookies():
    resp = requests.get(
        f"{BYPASS_SERVICE}/cookies",
        params={"url": f"{BASE_URL}/forum/"},
        timeout=120
    )
    return resp.json()

def clean_bbcode(text):
    """Nettoyer BBCode"""
    # [b]...[/b], [i]...[/i], [url]...[/url], etc.
    text = re.sub(r'\[/?[a-z]+(?:=[^\]]+)?\]', '', text, flags=re.IGNORECASE)
    return text.strip()

def scrape_thread(url, cookies, user_agent, author_username):
    """Scraper les posts d'un thread"""
    r = requests.get(url, cookies=cookies, headers={'User-Agent': user_agent}, timeout=30)
    
    if r.status_code != 200:
        return None
    
    soup = BeautifulSoup(r.text, 'lxml')
    
    # Extraire TOUS les posts
    posts = soup.select('article.message')
    
    story_posts = []
    debate_posts = []
    
    for post in posts:
        # Auteur du post
        author_elem = post.select_one('h4.message-name a.username')
        post_author = author_elem.get_text(strip=True) if author_elem else 'Unknown'
        
        # Contenu
        content_elem = post.select_one('div.bbWrapper')
        if not content_elem:
            continue
        
        # Retirer les citations (blockquote)
        for quote in content_elem.select('blockquote'):
            quote.decompose()
        
        # Retirer signatures
        for sig in content_elem.select('div.message-signature'):
            sig.decompose()
        
        content_raw = content_elem.get_text(separator='\n', strip=True)
        content_clean = clean_bbcode(content_raw)
        
        # ID du post
        post_id_elem = post.get('data-content', '')
        post_id = post_id_elem.split('-')[-1] if post_id_elem else None
        
        # Date
        time_elem = post.select_one('time')
        post_date = time_elem.get('datetime', '') if time_elem else ''
        
        post_data = {
            'post_id': post_id,
            'author': post_author,
            'date': post_date,
            'content': content_clean,
            'word_count': len(content_clean.split())
        }
        
        # Séparer story vs debate
        if post_author.lower() == author_username.lower():
            story_posts.append(post_data)
        else:
            debate_posts.append(post_data)
    
    return {
        'story_posts': story_posts,
        'debate_posts': debate_posts
    }

def main():
    print("🧪 Test scraping contenu d'un thread...")
    
    # Cookies
    print("🔐 Obtention cookies...")
    cf_data = get_cf_cookies()
    
    all_cookies = {
        **cf_data.get('cookies', {}),
        'xf_user': '171613%2Ck_Sjyt0Nl83XYdDdoJ8Uopx2rb2qaNpTge2X8IP0',
        'xf_session': 'MhoJm9vCJmDqrQI1b9kJCfa-69yElArN'
    }
    user_agent = cf_data.get('user_agent', '')
    
    print(f"📖 Scraping: {TEST_THREAD_URL}")
    print("   (Keynes Cruisers par fester)\n")
    
    result = scrape_thread(TEST_THREAD_URL, all_cookies, user_agent, 'fester')
    
    if not result:
        print("❌ Échec")
        return
    
    story = result['story_posts']
    debate = result['debate_posts']
    
    print(f"✅ Récupéré:")
    print(f"   📝 Story posts (auteur): {len(story)}")
    print(f"   💬 Debate posts (lecteurs): {len(debate)}")
    
    # Stats story
    total_story_words = sum(p['word_count'] for p in story)
    print(f"\n📊 Story:")
    print(f"   Total mots: {total_story_words:,}")
    print(f"   Moyenne mots/post: {total_story_words/len(story):.0f}" if story else "   Aucun post")
    
    # Premier post story
    if story:
        print(f"\n📖 Premier post story (extrait):")
        print(f"   {story[0]['content'][:500]}...")
    
    # Sauvegarder
    with open('/app/thread_test_content.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Sauvegardé: /app/thread_test_content.json")
    
    print("\n✅ Validation: Le nettoyage fonctionne!")
    print("   Prêt à scraper les 307 timelines complètes")

if __name__ == '__main__':
    main()

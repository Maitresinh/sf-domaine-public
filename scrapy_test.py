"""
scrapy_test.py
Test Scrapy sur AlternateHistory.com
"""
import scrapy
from scrapy.crawler import CrawlerProcess

class AHTestSpider(scrapy.Spider):
    name = 'ah_test'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': True,
        'REDIRECT_ENABLED': True,
    }
    
    start_urls = ['https://www.alternatehistory.com/forum/forums/finished-timelines.72/']
    
    def parse(self, response):
        self.logger.info(f"Status: {response.status}")
        self.logger.info(f"URL: {response.url}")
        
        # Vérifier si Cloudflare bloque
        if 'cloudflare' in response.text.lower() and 'blocked' in response.text.lower():
            self.logger.error("❌ BLOQUÉ par Cloudflare")
            return
        
        # Chercher les threads
        threads = response.css('div.structItem--thread')
        self.logger.info(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            self.logger.info("✅ SCRAPY FONCTIONNE!")
            
            # Afficher 3 premiers threads
            for i, thread in enumerate(threads[:3], 1):
                title = thread.css('div.structItem-title a::text').get()
                url = thread.css('div.structItem-title a::attr(href)').get()
                self.logger.info(f"  [{i}] {title}")
                self.logger.info(f"      {url}")
        else:
            self.logger.warning("⚠️ Aucun thread trouvé")

if __name__ == '__main__':
    process = CrawlerProcess()
    process.crawl(AHTestSpider)
    process.start()

"""
scrapy_cloudscraper_test.py
Scrapy + CloudScraper pour contourner Cloudflare
"""
import scrapy
from scrapy.crawler import CrawlerProcess
import cloudscraper

class CloudScraperDownloaderMiddleware:
    """Middleware pour utiliser cloudscraper au lieu de requests"""
    
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
    
    def process_request(self, request, spider):
        response = self.scraper.get(request.url)
        return scrapy.http.HtmlResponse(
            url=request.url,
            body=response.content,
            encoding='utf-8',
            request=request
        )

class AHCloudSpider(scrapy.Spider):
    name = 'ah_cloud'
    
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            '__main__.CloudScraperDownloaderMiddleware': 585,
        },
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
        'ROBOTSTXT_OBEY': False,  # CloudScraper gère ça
    }
    
    start_urls = ['https://www.alternatehistory.com/forum/forums/finished-timelines.72/']
    
    def parse(self, response):
        self.logger.info(f"✓ Status: {response.status}")
        
        # Vérifier contenu
        if 'cloudflare' in response.text.lower() and 'blocked' in response.text.lower():
            self.logger.error("❌ Toujours bloqué")
            return
        
        threads = response.css('div.structItem--thread')
        self.logger.info(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            self.logger.info("✅ CLOUDSCRAPER FONCTIONNE!")
            for i, thread in enumerate(threads[:3], 1):
                title = thread.css('div.structItem-title a::text').get()
                self.logger.info(f"  [{i}] {title}")

if __name__ == '__main__':
    process = CrawlerProcess()
    process.crawl(AHCloudSpider)
    process.start()

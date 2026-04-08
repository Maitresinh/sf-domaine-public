"""
scrapy_playwright_test.py
Scrapy + Playwright (navigateur réel)
"""
import scrapy
from scrapy.crawler import CrawlerProcess

class AHPlaywrightSpider(scrapy.Spider):
    name = 'ah_playwright'
    
    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'TWISTED_REACTOR': "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
    }
    
    start_urls = ['https://www.alternatehistory.com/forum/forums/finished-timelines.72/']
    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                }
            )
    
    async def parse(self, response):
        page = response.meta['playwright_page']
        await page.close()
        
        self.logger.info(f"✓ Status: {response.status}")
        
        # Vérifier si Cloudflare bloque
        if 'cloudflare' in response.text.lower() and 'blocked' in response.text.lower():
            self.logger.error("❌ Toujours bloqué")
            return
        
        threads = response.css('div.structItem--thread')
        self.logger.info(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            self.logger.info("✅ PLAYWRIGHT FONCTIONNE!")
            for i, thread in enumerate(threads[:5], 1):
                title = thread.css('div.structItem-title a::text').get()
                self.logger.info(f"  [{i}] {title}")

if __name__ == '__main__':
    process = CrawlerProcess()
    process.crawl(AHPlaywrightSpider)
    process.start()

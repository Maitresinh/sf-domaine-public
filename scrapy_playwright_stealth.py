"""
scrapy_playwright_stealth.py
Playwright avec attente du challenge Cloudflare
"""
import scrapy
from scrapy.crawler import CrawlerProcess

class AHStealthSpider(scrapy.Spider):
    name = 'ah_stealth'
    
    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'TWISTED_REACTOR': "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 5,
    }
    
    def start_requests(self):
        yield scrapy.Request(
            'https://www.alternatehistory.com/forum/forums/finished-timelines.72/',
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_goto_kwargs': {
                    'wait_until': 'networkidle',
                    'timeout': 30000,
                },
            }
        )
    
    async def parse(self, response):
        page = response.meta['playwright_page']
        
        # Attendre que Cloudflare finisse son challenge
        self.logger.info("Attente challenge Cloudflare...")
        await page.wait_for_timeout(10000)  # 10 secondes
        
        # Récupérer le contenu final
        content = await page.content()
        await page.close()
        
        self.logger.info(f"✓ Status: {response.status}")
        
        # Vérifier blocage
        if 'cloudflare' in content.lower() and 'blocked' in content.lower():
            self.logger.error("❌ Toujours bloqué après attente")
            self.logger.info(content[:500])  # Debug
            return
        
        # Parser avec le contenu final
        from scrapy import Selector
        sel = Selector(text=content)
        threads = sel.css('div.structItem--thread')
        
        self.logger.info(f"✓ {len(threads)} threads trouvés")
        
        if len(threads) > 0:
            self.logger.info("✅ PLAYWRIGHT STEALTH FONCTIONNE!")
            for i, thread in enumerate(threads[:5], 1):
                title = thread.css('div.structItem-title a::text').get()
                self.logger.info(f"  [{i}] {title}")
        else:
            self.logger.warning("⚠️ Aucun thread - structure différente?")

if __name__ == '__main__':
    process = CrawlerProcess()
    process.crawl(AHStealthSpider)
    process.start()

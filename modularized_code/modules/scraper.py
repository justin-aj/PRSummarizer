"""
Web scraping module for PR Summarizer application.
"""
import asyncio
import logging
import re
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from utils.helpers import print_with_timestamp

logger = logging.getLogger(__name__)


class TimestampRetainingFilter(PruningContentFilter):
    """
    Custom filter that retains timestamps in web content.
    """
    TIMESTAMP_PATTERNS = [
        r'\b\d{4}-\d{2}-\d{2}\b',  # 2025-05-20
        r'\b[A-Za-z]+ \d{1,2}, \d{4}\b',  # May 20, 2025
        r'\b\d{1,2} [A-Za-z]+ \d{4}\b',  # 20 May 2025
    ]

    def should_retain(self, node):
        # Text content of the node
        text = node.text_content()
        # Check if the text matches any timestamp pattern
        for pattern in self.TIMESTAMP_PATTERNS:
            if re.search(pattern, text):
                return True
        # If no timestamp is found, use the default pruning logic
        return super().should_retain(node)


async def async_scrape_url(url):
    """
    Scrape content from a URL asynchronously.

    Args:
        url (str): URL to scrape

    Returns:
        str: Markdown content from the URL or None if scraping failed
    """
    logger.info(f"Starting URL scrape: {url}")
    print_with_timestamp(f"Starting URL scrape: {url}")

    try:
        # Step 1: Create a custom pruning filter that retains timestamps
        prune_filter = TimestampRetainingFilter(
            threshold=0.3,  # Lower → more content retained, higher → more content pruned
            threshold_type="dynamic",  # "fixed" or "dynamic"
            min_word_threshold=5
        )

        # Step 2: Insert it into a Markdown Generator
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

        # Step 3: Pass it to CrawlerRunConfig
        config = CrawlerRunConfig(
            markdown_generator=md_generator
        )

        async with AsyncWebCrawler() as crawler:
            print_with_timestamp(f"AsyncWebCrawler initialized for URL: {url}")
            result = await crawler.arun(url=url, config=config)
            logger.info(f"Successfully scraped URL: {url}")
            print_with_timestamp(
                f"Successfully scraped URL: {url}, content length: {len(result.markdown) if result.markdown else 0}")
            return result.markdown.fit_markdown
    except Exception as e:
        logger.error(f"Scraping error for {url}: {str(e)}")
        print_with_timestamp(f"ERROR: Scraping error for {url}: {str(e)}")
        return None


def sync_scrape_url(url):
    """
    Synchronous wrapper for async_scrape_url.

    Args:
        url (str): URL to scrape

    Returns:
        str: Markdown content from the URL or None if scraping failed
    """
    print_with_timestamp(f"Running synchronous URL scrape for: {url}")
    return asyncio.run(async_scrape_url(url))
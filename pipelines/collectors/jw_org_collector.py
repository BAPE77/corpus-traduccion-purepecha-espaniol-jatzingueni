"""
JW.org Web Scraper for Purépecha-Spanish Parallel Corpus Collection

This script collects parallel articles from JW.org website in Purépecha (tsz)
and Spanish (es) languages.

Usage:
    python jw_org_collector.py --language tsz --max-articles 100
"""

import re
import time
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from loguru import logger

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_corpus_db, PipelineRunTracker, get_db_connection


class JWOrgCollector:
    """Collector for JW.org parallel articles"""
    
    BASE_URLS = {
        'tsz': 'https://www.jw.org/tsz/',  # Purépecha
        'es': 'https://www.jw.org/es/',    # Spanish
    }
    
    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize JW.org collector
        
        Args:
            rate_limit: Minimum seconds between requests (default 1.0)
        """
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (J\'atzingueni Corpus Research Project)',
            'Accept-Language': 'tsz,es,en'
        })
        
        self.db = get_corpus_db()
    
    def _rate_limited_request(self, url: str) -> Optional[requests.Response]:
        """
        Make rate-limited HTTP request
        
        Args:
            url: URL to request
        
        Returns:
            Response object or None if failed
        """
        # Enforce rate limit
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        
        try:
            response = self.session.get(url, timeout=30)
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                return response
            else:
                logger.warning(f"Request failed with status {response.status_code}: {url}")
                return None
        
        except Exception as e:
            logger.error(f"Request exception for {url}: {e}")
            return None
    
    def discover_article_urls(
        self,
        language: str,
        category: str = 'bible-teachings',
        max_articles: int = 100
    ) -> List[str]:
        """
        Discover article URLs from JW.org
        
        Args:
            language: Language code (tsz or es)
            category: Article category
            max_articles: Maximum number of articles to discover
        
        Returns:
            List of article URLs
        """
        base_url = self.BASE_URLS.get(language)
        if not base_url:
            logger.error(f"Unsupported language: {language}")
            return []
        
        # Note: This is a simplified example. Actual implementation would need
        # to navigate JW.org's site structure, which may require more sophisticated
        # scraping or use of their API if available.
        
        category_url = urljoin(base_url, category)
        logger.info(f"Discovering articles from {category_url}")
        
        response = self._rate_limited_request(category_url)
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find article links (this selector may need adjustment based on actual site structure)
        article_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Filter for article-like URLs
            if '/article/' in href or '/library/' in href:
                full_url = urljoin(base_url, href)
                if full_url not in article_links:
                    article_links.append(full_url)
                
                if len(article_links) >= max_articles:
                    break
        
        logger.info(f"Discovered {len(article_links)} article URLs")
        return article_links[:max_articles]
    
    def extract_article_content(
        self,
        url: str,
        language: str
    ) -> Optional[Dict[str, any]]:
        """
        Extract article content from URL
        
        Args:
            url: Article URL
            language: Language code
        
        Returns:
            Dictionary with article data or None
        """
        response = self._rate_limited_request(url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract article metadata (selectors may need adjustment)
        title = soup.find('h1')
        title_text = title.get_text(strip=True) if title else "Untitled"
        
        # Extract article identifier from URL
        article_id = self._extract_article_id(url)
        
        # Extract paragraphs
        content_div = soup.find('div', {'id': 'article'}) or soup.find('article')
        if not content_div:
            logger.warning(f"Could not find article content in {url}")
            return None
        
        paragraphs = []
        for p in content_div.find_all('p'):
            text = p.get_text(strip=True)
            if text and len(text) > 10:  # Filter out very short paragraphs
                paragraphs.append(text)
        
        if not paragraphs:
            logger.warning(f"No paragraphs found in {url}")
            return None
        
        return {
            'url': url,
            'article_id': article_id,
            'title': title_text,
            'language': language,
            'paragraphs': paragraphs,
            'paragraph_count': len(paragraphs)
        }
    
    def _extract_article_id(self, url: str) -> str:
        """Extract article identifier from URL"""
        # Example: https://www.jw.org/tsz/library/article/12345/
        # Extract: article_12345
        
        match = re.search(r'/article/([^/]+)', url)
        if match:
            return f"article_{match.group(1)}"
        
        # Fallback: use hash of URL
        return f"article_{abs(hash(url))}"
    
    def segment_sentences(self, paragraphs: List[str]) -> List[str]:
        """
        Segment paragraphs into sentences
        
        Args:
            paragraphs: List of paragraph texts
        
        Returns:
            List of sentences
        """
        sentences = []
        
        # Simple sentence segmentation (can be improved with NLTK)
        sentence_endings = re.compile(r'[.!?¿¡]+[\s"]')
        
        for para in paragraphs:
            # Split by sentence endings
            parts = sentence_endings.split(para)
            
            for part in parts:
                part = part.strip()
                if part and len(part) > 5:  # Filter very short segments
                    sentences.append(part)
        
        return sentences
    
    def collect_parallel_article(
        self,
        article_id: str,
        source_id: uuid.UUID,
        pipeline_run_id: uuid.UUID
    ) -> Tuple[int, int]:
        """
        Collect a parallel article in both Purépecha and Spanish
        
        Args:
            article_id: Article identifier
            source_id: UUID of the source
            pipeline_run_id: UUID of the pipeline run
        
        Returns:
            Tuple of (sentences_collected, sentences_failed)
        """
        logger.info(f"Collecting parallel article: {article_id}")
        
        # Construct URLs (this is simplified - actual URLs may differ)
        tsz_url = f"{self.BASE_URLS['tsz']}/library/{article_id}/"
        es_url = f"{self.BASE_URLS['es']}/library/{article_id}/"
        
        # Extract content for both languages
        tsz_content = self.extract_article_content(tsz_url, 'tsz')
        es_content = self.extract_article_content(es_url, 'es')
        
        if not tsz_content or not es_content:
            logger.warning(f"Could not extract parallel content for {article_id}")
            return 0, 1
        
        # Segment into sentences
        tsz_sentences = self.segment_sentences(tsz_content['paragraphs'])
        es_sentences = self.segment_sentences(es_content['paragraphs'])
        
        logger.info(f"  Purépecha sentences: {len(tsz_sentences)}")
        logger.info(f"  Spanish sentences: {len(es_sentences)}")
        
        # Create documents in database
        tsz_doc_id = self.db.insert_document(
            source_id=source_id,
            document_identifier=article_id,
            title=tsz_content['title'],
            language='tsz',
            metadata={'url': tsz_url, 'collected_at': datetime.now().isoformat()}
        )
        
        es_doc_id = self.db.insert_document(
            source_id=source_id,
            document_identifier=article_id,
            title=es_content['title'],
            language='es',
            metadata={'url': es_url, 'collected_at': datetime.now().isoformat()}
        )
        
        # Insert sentences
        sentences_collected = 0
        
        # Insert Purépecha sentences
        for i, sentence in enumerate(tsz_sentences):
            try:
                self.db.insert_sentence(
                    document_id=tsz_doc_id,
                    sentence_order=i,
                    language='tsz',
                    text=sentence
                )
                sentences_collected += 1
            except Exception as e:
                logger.error(f"Failed to insert Purépecha sentence {i}: {e}")
        
        # Insert Spanish sentences
        for i, sentence in enumerate(es_sentences):
            try:
                self.db.insert_sentence(
                    document_id=es_doc_id,
                    sentence_order=i,
                    language='es',
                    text=sentence
                )
                sentences_collected += 1
            except Exception as e:
                logger.error(f"Failed to insert Spanish sentence {i}: {e}")
        
        logger.info(f"  ✓ Collected {sentences_collected} sentences")
        return sentences_collected, 0
    
    def run_collection(
        self,
        max_articles: int = 10,
        category: str = 'bible-teachings'
    ):
        """
        Run complete collection pipeline
        
        Args:
            max_articles: Maximum number of articles to collect
            category: Article category to collect from
        """
        logger.info(f"Starting JW.org collection pipeline")
        logger.info(f"  Max articles: {max_articles}")
        logger.info(f"  Category: {category}")
        
        # Create or get source
        source_id = self.db.insert_source(
            source_name='JW.org Purépecha-Spanish',
            source_type='jw_org',
            source_url='https://www.jw.org',
            description='Parallel articles from JW.org website',
            metadata={'category': category}
        )
        
        # Start pipeline run tracking
        db_conn = get_db_connection()
        tracker = PipelineRunTracker(db_conn)
        
        run_id = tracker.start_run(
            run_name=f'JW.org Collection - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            pipeline_type='collection',
            configuration={
                'source': 'jw_org',
                'max_articles': max_articles,
                'category': category,
                'rate_limit': self.rate_limit
            }
        )
        
        logger.info(f"Pipeline run ID: {run_id}")
        
        # Discover article URLs (Purépecha)
        article_urls = self.discover_article_urls('tsz', category, max_articles)
        
        if not article_urls:
            logger.error("No articles discovered")
            tracker.complete_run(status='failed', error_message='No articles discovered')
            return
        
        # Extract article IDs
        article_ids = [self._extract_article_id(url) for url in article_urls]
        
        # Collect articles
        total_sentences = 0
        total_failed = 0
        
        for i, article_id in enumerate(article_ids, 1):
            logger.info(f"Processing article {i}/{len(article_ids)}: {article_id}")
            
            try:
                sentences, failed = self.collect_parallel_article(
                    article_id, source_id, run_id
                )
                total_sentences += sentences
                total_failed += failed
                
                # Update progress
                tracker.update_progress(
                    items_processed=i,
                    items_succeeded=i - total_failed,
                    items_failed=total_failed
                )
                
            except Exception as e:
                logger.error(f"Failed to collect article {article_id}: {e}")
                total_failed += 1
        
        # Complete pipeline run
        tracker.complete_run(status='completed')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Collection complete!")
        logger.info(f"  Articles processed: {len(article_ids)}")
        logger.info(f"  Total sentences collected: {total_sentences}")
        logger.info(f"  Failed articles: {total_failed}")
        logger.info(f"{'='*60}\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Collect parallel articles from JW.org'
    )
    parser.add_argument(
        '--max-articles',
        type=int,
        default=10,
        help='Maximum number of articles to collect (default: 10)'
    )
    parser.add_argument(
        '--category',
        type=str,
        default='bible-teachings',
        help='Article category to collect (default: bible-teachings)'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=1.0,
        help='Minimum seconds between requests (default: 1.0)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level=args.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    logger.add(
        f"logs/collection_{datetime.now().strftime('%Y%m%d')}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
    )
    
    # Run collector
    collector = JWOrgCollector(rate_limit=args.rate_limit)
    
    try:
        collector.run_collection(
            max_articles=args.max_articles,
            category=args.category
        )
    except KeyboardInterrupt:
        logger.warning("Collection interrupted by user")
    except Exception as e:
        logger.exception(f"Collection failed: {e}")
    finally:
        # Close database connections
        get_db_connection().close_all_connections()


if __name__ == '__main__':
    main()

"""
Simple JW.org Web Scraper for Purépecha-Spanish Parallel Corpus

This script collects parallel articles from JW.org in Purépecha (tsz) and Spanish (es).
Results are saved to CSV files for easy analysis.

Requirements:
    pip install requests beautifulsoup4

Usage:
    python simple_jw_scraper.py --max-articles 10
"""

import re
import csv
import json
import time
import argparse
from datetime import datetime
from urllib.parse import urljoin
from pathlib import Path

import requests
from bs4 import BeautifulSoup


class SimpleJWScraper:
    """Simple scraper for JW.org parallel articles"""
    
    BASE_URLS = {
        'tsz': 'https://www.jw.org/tsz/',  # Purépecha
        'es': 'https://www.jw.org/es/',    # Spanish
    }
    
    def __init__(self, rate_limit=2.0, output_dir='outputs/jw'):
        """
        Initialize scraper
        
        Args:
            rate_limit: Seconds to wait between requests (default: 2.0)
            output_dir: Directory to save output files
        """
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Setup session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Research Project)',
            'Accept-Language': 'tsz,es,en'
        })
        
        print(f"  Scraper initialized")
        print(f"  Output directory: {self.output_dir}")
        print(f"  Rate limit: {rate_limit}s between requests")
    
    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
    
    def _make_request(self, url):
        """
        Make HTTP request with rate limiting and error handling
        
        Args:
            url: URL to request
        
        Returns:
            Response object or None if failed
        """
        self._wait_for_rate_limit()
        
        try:
            response = self.session.get(url, timeout=30)
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                return response
            else:
                print(f"  Request failed ({response.status_code}): {url}")
                return None
        
        except requests.exceptions.RequestException as e:
            print(f"  Request error: {e}")
            return None
    
    def discover_articles(self, language='tsz', category='bibliaeri-jorhenguarhikuecha', max_articles=10):
        """
        Discover article URLs from a category page
        
        Args:
            language: Language code (tsz or es)
            category: Category path
            max_articles: Maximum articles to discover
        
        Returns:
            List of article URLs
        """
        base_url = self.BASE_URLS.get(language, self.BASE_URLS['tsz'])
        category_url = urljoin(base_url, category)
        
        print(f"\n  Discovering articles from: {category_url}")
        
        response = self._make_request(category_url)
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find article links
        article_urls = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Look for article URLs (adjust patterns as needed)
            if any(pattern in href for pattern in ['/library/', '/article/', '/magazine/']):
                full_url = urljoin(base_url, href)
                
                # Avoid duplicates
                if full_url not in article_urls:
                    article_urls.append(full_url)
                
                if len(article_urls) >= max_articles:
                    break
        
        print(f"  Found {len(article_urls)} article URLs")
        return article_urls
    
    def extract_article(self, url, language):
        """
        Extract article content from URL
        
        Args:
            url: Article URL
            language: Language code
        
        Returns:
            Dictionary with article data or None
        """
        response = self._make_request(url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "No Title"
        
        # Extract article ID from URL
        article_id = self._extract_id_from_url(url)
        
        # Find article content (try multiple selectors)
        content = None
        for selector in ['article', {'id': 'article'}, {'class': 'article'}]:
            content = soup.find(selector)
            if content:
                break
        
        if not content:
            print(f"  Could not find content in: {url}")
            return None
        
        # Extract paragraphs
        paragraphs = []
        for p in content.find_all('p'):
            text = p.get_text(strip=True)
            if text and len(text) > 20:  # Filter very short paragraphs
                paragraphs.append(text)
        
        if not paragraphs:
            print(f"  No paragraphs found in: {url}")
            return None
        
        return {
            'article_id': article_id,
            'url': url,
            'title': title,
            'language': language,
            'paragraphs': paragraphs,
            'paragraph_count': len(paragraphs),
            'collected_at': datetime.now().isoformat()
        }
    
    def _extract_id_from_url(self, url):
        """Extract a unique identifier from URL"""
        # Try to find numeric ID in URL
        match = re.search(r'/(\d+)/', url)
        if match:
            return match.group(1)
        
        # Fallback: use last part of path
        parts = url.rstrip('/').split('/')
        if parts:
            return parts[-1]
        
        return str(abs(hash(url)))[:8]
    
    def segment_sentences(self, paragraphs):
        """
        Simple sentence segmentation
        
        Args:
            paragraphs: List of paragraph texts
        
        Returns:
            List of sentences
        """
        sentences = []
        
        # Simple regex for sentence endings
        sentence_pattern = re.compile(r'[.!?]+\s+')
        
        for para in paragraphs:
            # Split by sentence endings
            parts = sentence_pattern.split(para)
            
            for part in parts:
                part = part.strip()
                if part and len(part) > 10:  # Filter very short segments
                    sentences.append(part)
        
        return sentences
    
    def scrape_parallel_article(self, article_id, tsz_url=None, es_url=None):
        """
        Scrape parallel article in both languages
        
        Args:
            article_id: Article identifier
            tsz_url: Purépecha URL (optional)
            es_url: Spanish URL (optional)
        
        Returns:
            Dictionary with parallel data or None
        """
        print(f"\n  Scraping article: {article_id}")
        
        # Construct URLs if not provided
        if not tsz_url:
            tsz_url = f"{self.BASE_URLS['tsz']}library/{article_id}/"
        if not es_url:
            es_url = f"{self.BASE_URLS['es']}library/{article_id}/"
        
        # Extract both language versions
        print(f"  → Fetching Purépecha version...")
        tsz_article = self.extract_article(tsz_url, 'tsz')
        
        print(f"  → Fetching Spanish version...")
        es_article = self.extract_article(es_url, 'es')
        
        if not tsz_article or not es_article:
            print(f"  Failed to get both language versions")
            return None
        
        # Segment into sentences
        tsz_sentences = self.segment_sentences(tsz_article['paragraphs'])
        es_sentences = self.segment_sentences(es_article['paragraphs'])
        
        print(f"  Purépecha: {len(tsz_sentences)} sentences")
        print(f"  Spanish: {len(es_sentences)} sentences")
        
        return {
            'article_id': article_id,
            'tsz': tsz_article,
            'es': es_article,
            'tsz_sentences': tsz_sentences,
            'es_sentences': es_sentences
        }
    
    def save_to_csv(self, articles):
        """
        Save collected articles to CSV files
        
        Args:
            articles: List of parallel article dictionaries
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save sentences to CSV
        sentences_file = self.output_dir / f'sentences_{timestamp}.csv'
        
        print(f"\n  Saving to CSV: {sentences_file}")
        
        with open(sentences_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'article_id', 'sentence_number', 
                'purepecha', 'spanish'
            ])
            
            for article in articles:
                if not article:
                    continue
                
                article_id = article['article_id']
                tsz_sentences = article['tsz_sentences']
                es_sentences = article['es_sentences']
                
                # Write sentence pairs (simple alignment by position)
                max_len = max(len(tsz_sentences), len(es_sentences))
                
                for i in range(max_len):
                    tsz_sent = tsz_sentences[i] if i < len(tsz_sentences) else ''
                    es_sent = es_sentences[i] if i < len(es_sentences) else ''
                    
                    writer.writerow([article_id, i + 1, tsz_sent, es_sent])
        
        print(f"  Saved sentences to CSV")
        
        # Save metadata to JSON
        metadata_file = self.output_dir / f'metadata_{timestamp}.json'
        
        metadata = []
        for article in articles:
            if article:
                metadata.append({
                    'article_id': article['article_id'],
                    'tsz_title': article['tsz']['title'],
                    'es_title': article['es']['title'],
                    'tsz_url': article['tsz']['url'],
                    'es_url': article['es']['url'],
                    'tsz_sentence_count': len(article['tsz_sentences']),
                    'es_sentence_count': len(article['es_sentences']),
                    'collected_at': article['tsz']['collected_at']
                })
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"  Saved metadata to JSON")
    
    def run(self, max_articles=10, category='bible-teachings'):
        """
        Run complete scraping process
        
        Args:
            max_articles: Maximum number of articles to scrape
            category: Category to scrape from
        """
        print("=" * 60)
        print("  Starting JW.org Scraper")
        print(f"   Max articles: {max_articles}")
        print(f"   Category: {category}")
        print("=" * 60)
        
        # Discover article URLs
        article_urls = self.discover_articles(
            language='tsz',
            category=category,
            max_articles=max_articles
        )
        
        if not article_urls:
            print("\n✗ No articles found. Try a different category or check the URL.")
            return
        
        # Extract article IDs
        article_ids = [self._extract_id_from_url(url) for url in article_urls]
        
        # Scrape articles
        collected_articles = []
        successful = 0
        failed = 0
        
        for i, (article_id, url) in enumerate(zip(article_ids, article_urls), 1):
            print(f"\n[{i}/{len(article_ids)}]", end=" ")
            
            try:
                article = self.scrape_parallel_article(article_id)
                
                if article:
                    collected_articles.append(article)
                    successful += 1
                else:
                    failed += 1
            
            except Exception as e:
                print(f"  ✗ Error: {e}")
                failed += 1
        
        # Save results
        if collected_articles:
            self.save_to_csv(collected_articles)
        
        # Print summary
        print("\n" + "=" * 60)
        print("  Scraping Complete!")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Output directory: {self.output_dir}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Simple scraper for JW.org parallel articles'
    )
    parser.add_argument(
        '--max-articles',
        type=int,
        default=10,
        help='Maximum number of articles to scrape (default: 10)'
    )
    parser.add_argument(
        '--category',
        type=str,
        default='bible-teachings',
        help='Category to scrape (default: bible-teachings)'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=2.0,
        help='Seconds between requests (default: 2.0)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory (default: output)'
    )
    
    args = parser.parse_args()
    
    # Create and run scraper
    scraper = SimpleJWScraper(
        rate_limit=args.rate_limit,
        output_dir=args.output_dir
    )
    
    try:
        scraper.run(
            max_articles=args.max_articles,
            category=args.category
        )
    
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
    
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
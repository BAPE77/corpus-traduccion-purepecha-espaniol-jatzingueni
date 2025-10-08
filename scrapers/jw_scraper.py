import argparse
import requests
import time
import re
import csv
import json
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime

class JWScraper:
    BASE_URL = 'https://www.jw.org/tsz/'

    CATEGORIES = {
        'magazines': 'publikasionicha/rebistecha',
        'news': 'notisia/mandani-paisi-jimbo/interu-parhakpini-anapu',
    }

    def __init__(self, rateLimit=1.0, outputDir='outputs/jw'):
        self.rateLimit = rateLimit
        self.lastRequestTime = 0
        self.outputDir = Path('outputs')
        self.outputDir.mkdir(exist_ok=True)
        self.outputDir = Path(outputDir)
        self.outputDir.mkdir(exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (J\'atzingueni Corpus Research Project)',
            'Accept-Language': 'tsz,es,en'
        })

        print(f"Directorio de salida: {self.outputDir}")
        print(f"Rate Limit: {self.rateLimit}")

    def _waitForRateLimit(self):
        elapsed = time.time() - self.lastRequestTime
        if elapsed < self.rateLimit:
            time.sleep(self.rateLimit - elapsed)

    def _makeRequest(self, url):
        self._waitForRateLimit()
        try:
            response = self.session.get(url, timeout=30)
            self.lastRequestTime = time.time()
            if response.status_code == 200:
                return response
            else:
                print(f"Solicitud Fallida ({response.status_code}): {url}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error de Solicitud: {e}")
            return None

    def discoverArticles(self, category='magazines', maxArticles=10):
        baseURL = self.BASE_URL
        categoryURL = self.CATEGORIES.get(category, self.CATEGORIES['magazines'])
        joinedURL = urljoin(baseURL, categoryURL)
        
        response = self._makeRequest(joinedURL)
        if not response:
            return []
        soup = BeautifulSoup(response.content, 'html.parser')

        magazineURLs = []
        
        # Patron y busqueda de articulos especificos de revistas
        pattern = r"(.)+/rebistecha/(.)+"
        for link in soup.find_all('a', href=True):
            href = link['href']
            if re.match(pattern=pattern, string=href):
                fullURL = urljoin(baseURL, href)
                if fullURL not in magazineURLs:
                    magazineURLs.append(fullURL)

        articleURLs = []

        for magazineURL in magazineURLs:
            if len(articleURLs) >= maxArticles:
                break
            magResponse = self._makeRequest(magazineURL)
            if magResponse:
                soup = BeautifulSoup(magResponse.content, 'html.parser')
                magPattern = f'{magazineURL}(.)+'
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    fullURL = urljoin(magazineURL, href)
                    if re.match(pattern=magPattern, string=fullURL) and fullURL not in articleURLs:
                        articleURLs.append(fullURL)
                    if len(articleURLs) >= maxArticles:
                        break
        
        print(f"{len(articleURLs)} URLs de articulos encontradas")
        return articleURLs

    def extractArticle(self, url, id, lang):
        response = self._makeRequest(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        titleTag = soup.find('h1')
        title = titleTag.get_text(strip=True) if titleTag else "No Title"
        
        content = soup.find('div', class_='contentBody')
        
        if not content:
            return None
        
        paragraphs = []
        for p in content.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)
        
        if not paragraphs:
            return None
        
        return {
            'article_id': id,
            'url': url,
            'title': title,
            'language': lang,
            'paragraphs': paragraphs,
            'p_count': len(paragraphs),
            'collected_at': datetime.now().isoformat()
        }

    def findESURL(self, tszURL):
        response = self._makeRequest(tszURL)
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        languageLink = soup.find('a', href=True, class_='jsChooseSiteLanguage')
        href = languageLink['href']
        id = re.match('.*?([0-9]+)$', href).group(1)
        
        languajeURL = urljoin(self.BASE_URL, href)
        response = self._makeRequest(languajeURL)
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        esLink = soup.find('div', class_='optionLabel', lang='es').parent
        esURL = esLink['href']
        return esURL, id

    def segmentSentences(self, paragraphs):
        sentences = []
        sentencePattern = re.compile(r'[.!?:¿\d]+\s*')
        
        for p in paragraphs:
            parts = sentencePattern.split(p)
            for part in parts:
                part = part.strip()
                if part and len(part) > 10:
                    sentences.append(part)
        
        return sentences

    def saveCSV(self, articles):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sentencesFile = self.outputDir / f'sentences_{timestamp}.csv'
        with open(sentencesFile, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'article_id', 'sentence_number',
                'purepecha', 'spanish'
            ])

            for article in articles:
                if not article:
                    continue

                articleID = article['article_id']
                tszSentences = article['tsz_sentences']
                esSentences = article['es_sentences']

                maxLen = max(len(tszSentences), len(esSentences))

                for i in range(maxLen):
                    tszSent = tszSentences[i] if i < len(tszSentences) else ''
                    esSent = esSentences[i] if i < len(esSentences) else ''
                    writer.writerow([articleID, i + 1, tszSent, esSent])
        
        metadataFile = self.outputDir / f'metadata_{timestamp}.json'
        metadata = []
        for article in articles:
            if article:
                metadata.append({
                    'article_id': article['article_id'],
                    'tsz_title': article['tsz']['title'],
                    'es_title': article['es']['title'],
                    'tsz_title': article['tsz']['url'],
                    'es_title': article['es']['url'],
                    'tsz_sentence_count': len(article['tsz_sentences']),
                    'es_sentence_count': len(article['es_sentences']),
                    'collected_at': article['tsz']['collected_at']
                })
        with open(metadataFile, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def scrapeParallelArticle(self, tszURL):
        esURL, docID = self.findESURL(tszURL)
        tszArt = self.extractArticle(tszURL, docID, lang='tsz')
        esArt = self.extractArticle(esURL, docID, lang='es')
        
        if not tszArt or not esArt:
            return None
        
        tszSentences = self.segmentSentences(tszArt['paragraphs'])
        esSentences = self.segmentSentences(esArt['paragraphs'])
        return {
            'article_id': docID,
            'tsz': tszArt,
            'es': esArt,
            'tsz_sentences': tszSentences,
            'es_sentences': esSentences,
        }

    def run(self, maxArticles=10, category='magazines'):
        print(f"Articulos Maximos: {maxArticles}")
        print(f"Categoria: {category}")
        articleURLs = self.discoverArticles(
            category=category,
            maxArticles=maxArticles
        )
        if not articleURLs:
            print(f'No se encontraron articulos')
            return
        
        scrapedArticles = []
        successful = 0
        failed = 0

        for url in articleURLs:
            try:
                article = self.scrapeParallelArticle(url)
                if article:
                    scrapedArticles.append(article)
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Error: {e}")
                failed += 1
        
        if scrapedArticles:
            self.saveCSV(scrapedArticles)

        print("\nScraping Complete")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Output directory: {self.outputDir}")

def main():
    parser = argparse.ArgumentParser(
        description='Scraper de articulos de JW.org'
    )
    parser.add_argument(
        '--max-articles',
        type=int,
        default=10,
        help='Cantidad maxima de articulos a recolectar (10 por defecto)'
    )
    parser.add_argument(
        '--category',
        type=str,
        default='magazines',
        help='Categoria de articulos a recoger (bible-teachings por defecto)'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=1.0,
        help='Segundos entre solicitudes (2.0 por defecto)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='outputs/jw',
        help='Directorio de salida (outputs/jw por defecto)'
    )

    args = parser.parse_args()

    scraper = JWScraper(
        rateLimit=args.rate_limit,
        outputDir=args.output_dir
    )

    try:
        scraper.run(
            maxArticles=args.max_articles,
            category=args.category
        )
    except KeyboardInterrupt:
        print("\nDetenido por el usuario")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
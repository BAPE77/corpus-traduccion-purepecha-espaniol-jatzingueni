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

    def segmentSentences(self, paragraph):
        """
        Segmenta UN pÃ¡rrafo en oraciones individuales de manera mÃ¡s robusta.
        """
        if not paragraph or not paragraph.strip():
            return []
        
        text = paragraph.strip()
        
        # Limpiar caracteres especiales problemÃ¡ticos
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        text = text.replace('â€¦', '...')
        
        # Remover referencias bÃ­blicas entre parÃ©ntesis
        text = re.sub(r'\([^\)]*\d+[:]\d+[^\)]*\)', '', text)
        
        # Remover nÃºmeros iniciales de pÃ¡rrafo
        text = re.sub(r'^\s*\d+\s+', '', text)
        
        # Patrones para dividir oraciones
        # Busca puntos, signos de exclamaciÃ³n o interrogaciÃ³n seguidos de espacio y mayÃºscula
        sentence_endings = re.compile(
            r'([.!?]+)\s+(?=[A-ZÃÃ‰ÃÃ“ÃšÃ‘Ã„Ã‹ÃÃ–ÃœÂ¿Â¡])',
            re.UNICODE
        )
        
        # Dividir en oraciones preliminares
        parts = sentence_endings.split(text)
        
        sentences = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and parts[i+1] in ['.', '!', '?', '..', '...', '!!', '??', '.!', '!?', '?.']:
                # Combinar texto con su puntuaciÃ³n
                sentence = (parts[i] + parts[i+1]).strip()
                i += 2
            else:
                sentence = parts[i].strip()
                i += 1
            
            if sentence:
                # Limpiar la oraciÃ³n
                sentence = sentence.strip(' \'"()[]{}')
                
                # Remover caracteres de apertura huÃ©rfanos
                sentence = re.sub(r'^[Â¿Â¡]+\s*', '', sentence)
                
                # Remover enumeraciones al inicio (a), b), 1), etc.)
                sentence = re.sub(r'^[a-zA-Z0-9]+[.)]\s*', '', sentence)
                
                # Remover comillas huÃ©rfanas
                sentence = sentence.replace('"', '').replace("'", '')
                
                # Normalizar espacios antes de puntuaciÃ³n
                sentence = re.sub(r'\s+([?.!,;:])', r'\1', sentence)
                
                # Solo guardar si la oraciÃ³n tiene contenido significativo
                # Debe tener al menos 10 caracteres y contener letras
                if len(sentence) >= 10 and re.search(r'[a-zÃ¡Ã©Ã­Ã³ÃºÃ±A-ZÃÃ‰ÃÃ“ÃšÃ‘]', sentence):
                    sentences.append(sentence)
        
        return sentences

    def calculateSimilarity(self, text1, text2):
        """
        Calcula similitud bÃ¡sica entre dos textos basada en longitud.
        Retorna un score de 0 a 1.
        """
        if not text1 or not text2:
            return 0.0
        
        len1 = len(text1)
        len2 = len(text2)
        
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Ratio de longitud (cuÃ¡n similares son en tamaÃ±o)
        ratio = min(len1, len2) / max(len1, len2)
        return ratio

    def alignParagraphs(self, tszParagraphs, esParagraphs):
        """
        Alinea pÃ¡rrafos entre dos idiomas basÃ¡ndose en similitud de longitud.
        Retorna lista de tuplas (tszPara, esPara, confidence).
        """
        aligned = []
        
        # Si tienen la misma cantidad, asumir alineaciÃ³n 1:1
        if len(tszParagraphs) == len(esParagraphs):
            for i in range(len(tszParagraphs)):
                similarity = self.calculateSimilarity(tszParagraphs[i], esParagraphs[i])
                aligned.append((tszParagraphs[i], esParagraphs[i], similarity))
            return aligned
        
        # Si son diferentes, intentar alinear por similitud de longitud
        usedEs = set()
        
        for tszPara in tszParagraphs:
            bestMatch = None
            bestScore = 0.0
            bestIdx = -1
            
            for idx, esPara in enumerate(esParagraphs):
                if idx in usedEs:
                    continue
                
                score = self.calculateSimilarity(tszPara, esPara)
                if score > bestScore:
                    bestScore = score
                    bestMatch = esPara
                    bestIdx = idx
            
            if bestMatch and bestScore > 0.3:  # Umbral mÃ­nimo de similitud
                aligned.append((tszPara, bestMatch, bestScore))
                usedEs.add(bestIdx)
            else:
                # Sin buena coincidencia, agregar con pÃ¡rrafo vacÃ­o
                aligned.append((tszPara, '', 0.0))
        
        return aligned

    def saveCSV(self, articles):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sentencesFile = self.outputDir / f'sentences_{timestamp}.csv'
        
        with open(sentencesFile, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'article_id', 'paragraph_number', 'sentence_number',
                'purepecha', 'spanish', 'alignment_confidence'
            ])

            for article in articles:
                if not article:
                    continue

                articleID = article['article_id']
                
                # Iterar por cada pÃ¡rrafo alineado
                for paragraphIdx, paragraphData in enumerate(article['paragraph_pairs'], start=1):
                    tszSentences = paragraphData['tsz_sentences']
                    esSentences = paragraphData['es_sentences']
                    confidence = paragraphData['confidence']
                    
                    # Solo procesar si hay contenido en al menos un idioma
                    if not tszSentences and not esSentences:
                        continue
                    
                    maxLen = max(len(tszSentences), len(esSentences))
                    
                    # Alinear oraciones dentro de cada pÃ¡rrafo
                    for sentIdx in range(maxLen):
                        tszSent = tszSentences[sentIdx] if sentIdx < len(tszSentences) else ''
                        esSent = esSentences[sentIdx] if sentIdx < len(esSentences) else ''
                        
                        # Solo escribir si hay contenido en al menos uno de los idiomas
                        if tszSent or esSent:
                            writer.writerow([
                                articleID, 
                                paragraphIdx, 
                                sentIdx + 1, 
                                tszSent, 
                                esSent,
                                f"{confidence:.2f}"
                            ])
        
        metadataFile = self.outputDir / f'metadata_{timestamp}.json'
        metadata = []
        for article in articles:
            if article:
                totalTszSentences = sum(len(p['tsz_sentences']) for p in article['paragraph_pairs'])
                totalEsSentences = sum(len(p['es_sentences']) for p in article['paragraph_pairs'])
                avgConfidence = sum(p['confidence'] for p in article['paragraph_pairs']) / len(article['paragraph_pairs'])
                
                metadata.append({
                    'article_id': article['article_id'],
                    'tsz_title': article['tsz']['title'],
                    'es_title': article['es']['title'],
                    'tsz_url': article['tsz']['url'],
                    'es_url': article['es']['url'],
                    'paragraph_count': len(article['paragraph_pairs']),
                    'tsz_sentence_count': totalTszSentences,
                    'es_sentence_count': totalEsSentences,
                    'avg_alignment_confidence': round(avgConfidence, 2),
                    'collected_at': article['tsz']['collected_at']
                })
        with open(metadataFile, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"\nArchivos guardados:")
        print(f"  - {sentencesFile}")
        print(f"  - {metadataFile}")

    def scrapeParallelArticle(self, tszURL):
        esURL, docID = self.findESURL(tszURL)
        tszArt = self.extractArticle(tszURL, docID, lang='tsz')
        esArt = self.extractArticle(esURL, docID, lang='es')
        
        if not tszArt or not esArt:
            return None
        
        # Alinear pÃ¡rrafos primero
        alignedParagraphs = self.alignParagraphs(
            tszArt['paragraphs'], 
            esArt['paragraphs']
        )
        
        # Procesar cada par de pÃ¡rrafos alineados
        paragraphPairs = []
        
        for i, (tszPara, esPara, confidence) in enumerate(alignedParagraphs, start=1):
            # Segmentar cada pÃ¡rrafo en oraciones
            tszSentences = self.segmentSentences(tszPara) if tszPara else []
            esSentences = self.segmentSentences(esPara) if esPara else []
            
            paragraphPairs.append({
                'paragraph_number': i,
                'tsz_sentences': tszSentences,
                'es_sentences': esSentences,
                'confidence': confidence
            })
        
        return {
            'article_id': docID,
            'tsz': tszArt,
            'es': esArt,
            'paragraph_pairs': paragraphPairs
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
                    avgConf = sum(p['confidence'] for p in article['paragraph_pairs']) / len(article['paragraph_pairs'])
                    print(f"âœ“ ArtÃ­culo {article['article_id']} - {len(article['paragraph_pairs'])} pÃ¡rrafos (confianza: {avgConf:.2f})")
                else:
                    failed += 1
                    print(f"âœ— Fallo al extraer artÃ­culo")
            except Exception as e:
                print(f"âœ— Error: {e}")
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
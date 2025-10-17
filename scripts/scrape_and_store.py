"""
Wrapper sobre jw_scraper.py que guarda directamente en PostgreSQL
Mantiene la funcionalidad de generar CSVs pero también persiste en BD

Uso:
    python scripts/scrape_and_store.py --max-articles 10 --category magazines
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / 'scrapers'))

# Import jw_scraper
from jw_scraper import JWScraper

# Import database utilities
from utils.database import get_db_connection, CorpusDB


class JWScraperWithDB(JWScraper):
    """Extended JWScraper that also saves to PostgreSQL"""
    
    def __init__(self, rateLimit=1.0, outputDir='outputs/jw', save_to_db=True):
        """
        Initialize scraper with database support
        
        Args:
            rateLimit: Rate limit for requests
            outputDir: Output directory for CSVs
            save_to_db: Whether to save to database
        """
        super().__init__(rateLimit=rateLimit, outputDir=outputDir)
        
        self.save_to_db = save_to_db
        self.db = None
        self.source_id = None
        
        if save_to_db:
            print("\n[PostgreSQL] Conectando a base de datos...")
            try:
                db_conn = get_db_connection()
                db_conn.connect()
                self.db = CorpusDB(db_conn)
                
                # Create or get source
                self.source_id = self.db.insert_source(
                    name='JW.org Purépecha-Spanish',
                    author='Testigos de Jehová',
                    publisher='Watch Tower Bible and Tract Society',
                    licence='Fair Use - Research/Educational',
                    url='https://www.jw.org'
                )
                
                print(f"[PostgreSQL] ✓ Conectado (Source ID: {self.source_id})")
            except Exception as e:
                print(f"[PostgreSQL] ✗ Error conectando: {e}")
                print("[PostgreSQL] Continuando solo con CSVs...")
                self.save_to_db = False
                self.db = None
    
    def scrapeParallelArticle(self, tszURL):
        """
        Override to add database saving
        
        This method calls the parent scrapeParallelArticle and then
        saves the results to PostgreSQL
        """
        # Call parent method to scrape article
        article = super().scrapeParallelArticle(tszURL)
        
        if not article:
            return None
        
        # Save to database if enabled
        if self.save_to_db and self.db and self.source_id:
            try:
                self._saveArticleToDB(article)
            except Exception as e:
                print(f"[PostgreSQL] ⚠️  Error guardando artículo {article['article_id']}: {e}")
        
        return article
    
    def _saveArticleToDB(self, article):
        """
        Save article to PostgreSQL
        
        Args:
            article: Article dictionary from scraper
        """
        article_id = article['article_id']
        
        print(f"[PostgreSQL] Guardando artículo {article_id}...")
        
        # Create Purépecha document
        tsz_doc_id = self.db.insert_document(
            source_id=self.source_id,
            title=article['tsz']['title'],
            lang='tsz',
            genre='religious',
            tsz_dialect='lacustre',
            metadata={
                'article_id': article_id,
                'url': article['tsz']['url'],
                'paragraph_count': article['tsz']['p_count'],
                'sentence_count': len(article['tsz_sentences']),
                'collected_at': article['tsz']['collected_at'],
                'source': 'jw_scraper.py',
                'scraper_version': '1.0'
            }
        )
        
        # Create Spanish document
        es_doc_id = self.db.insert_document(
            source_id=self.source_id,
            title=article['es']['title'],
            lang='es',
            genre='religious',
            metadata={
                'article_id': article_id,
                'url': article['es']['url'],
                'paragraph_count': article['es']['p_count'],
                'sentence_count': len(article['es_sentences']),
                'collected_at': article['es']['collected_at'],
                'source': 'jw_scraper.py',
                'scraper_version': '1.0'
            }
        )
        
        # Insert sentences
        tsz_sent_ids = []
        es_sent_ids = []
        
        for i, tsz_text in enumerate(article['tsz_sentences']):
            if tsz_text.strip():
                try:
                    sent_id = self.db.insert_sentence(
                        document_id=tsz_doc_id,
                        text=tsz_text,
                        lang='tsz',
                        sibling_pos=i + 1,
                        tsz_dialect='lacustre',
                        metadata={'sentence_number': i + 1}
                    )
                    if sent_id:
                        tsz_sent_ids.append(sent_id)
                except Exception as e:
                    print(f"  ⚠️  Error insertando sentencia tsz #{i+1}: {e}")
        
        for i, es_text in enumerate(article['es_sentences']):
            if es_text.strip():
                try:
                    sent_id = self.db.insert_sentence(
                        document_id=es_doc_id,
                        text=es_text,
                        lang='es',
                        sibling_pos=i + 1,
                        metadata={'sentence_number': i + 1}
                    )
                    if sent_id:
                        es_sent_ids.append(sent_id)
                except Exception as e:
                    print(f"  ⚠️  Error insertando sentencia es #{i+1}: {e}")
        
        # Create alignments
        min_len = min(len(tsz_sent_ids), len(es_sent_ids))
        alignments_created = 0
        
        for i in range(min_len):
            try:
                align_id = self.db.insert_alignment(
                    tsz_sentence_id=tsz_sent_ids[i],
                    es_sentence_id=es_sent_ids[i],
                    alignment_method='manual',  # From parallel corpus
                    confidence=1.0,
                    quality=0.8
                )
                if align_id:
                    alignments_created += 1
            except Exception as e:
                print(f"  ⚠️  Error creando alineamiento #{i+1}: {e}")
        
        print(f"[PostgreSQL]   ✓ Docs: tsz={tsz_doc_id}, es={es_doc_id}")
        print(f"[PostgreSQL]   ✓ Sentencias: {len(tsz_sent_ids)} tsz, {len(es_sent_ids)} es")
        print(f"[PostgreSQL]   ✓ Alineamientos: {alignments_created}")
        
        # Commit the transaction to persist changes
        self.db.db.commit()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Scraper de JW.org con guardado en PostgreSQL'
    )
    parser.add_argument(
        '--max-articles',
        type=int,
        default=10,
        help='Cantidad máxima de artículos a recolectar (10 por defecto)'
    )
    parser.add_argument(
        '--category',
        type=str,
        default='magazines',
        help='Categoría de artículos a recoger (magazines por defecto)'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=1.0,
        help='Segundos entre solicitudes (1.0 por defecto)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='outputs/jw',
        help='Directorio de salida para CSVs (outputs/jw por defecto)'
    )
    parser.add_argument(
        '--no-db',
        action='store_true',
        help='No guardar en base de datos (solo CSVs)'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"J'atzingueni - Scraper JW.org → PostgreSQL")
    print(f"{'='*60}\n")
    print(f"Artículos máximos: {args.max_articles}")
    print(f"Categoría: {args.category}")
    print(f"Rate limit: {args.rate_limit}s")
    print(f"Directorio salida: {args.output_dir}")
    print(f"Guardar en BD: {'No' if args.no_db else 'Sí'}")
    
    # Create scraper instance
    scraper = JWScraperWithDB(
        rateLimit=args.rate_limit,
        outputDir=args.output_dir,
        save_to_db=not args.no_db
    )
    
    # Run scraping
    try:
        scraper.run(
            maxArticles=args.max_articles,
            category=args.category
        )
        
        # Show final statistics if database was used
        if scraper.save_to_db and scraper.db:
            print(f"\n{'='*60}")
            print(f"Estadísticas del Corpus")
            print(f"{'='*60}\n")
            
            stats = scraper.db.get_corpus_stats()
            print(f"Fuentes: {stats.get('total_sources', 0)}")
            print(f"Documentos por idioma: {stats.get('documents_by_language', {})}")
            print(f"Sentencias por idioma: {stats.get('sentences_by_language', {})}")
            print(f"Alineamientos totales: {stats.get('total_alignments', 0)}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Detenido por el usuario")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close database connection
        if scraper.db:
            print("\n[PostgreSQL] Cerrando conexión...")
            scraper.db.db.close()
    
    print(f"\n{'='*60}")
    print(f"✓ Proceso completado")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

"""
Migración de CSVs existentes a PostgreSQL
Lee los archivos CSV generados por jw_scraper.py y los inserta en la base de datos

Uso:
    python scripts/migrate_csv_to_db.py [--csv-dir outputs/jw] [--dry-run]
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.database import get_db_connection, CorpusDB


def load_metadata(metadata_file: Path) -> List[Dict]:
    """Load metadata from JSON file"""
    if not metadata_file.exists():
        print(f"⚠️  Metadata file not found: {metadata_file}")
        return []
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_csv_sentences(csv_file: Path) -> List[Dict]:
    """Load sentences from CSV file"""
    if not csv_file.exists():
        print(f"⚠️  CSV file not found: {csv_file}")
        return []
    
    sentences = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sentences.append({
                'article_id': row['article_id'],
                'sentence_number': int(row['sentence_number']),
                'purepecha': row['purepecha'],
                'spanish': row['spanish']
            })
    
    return sentences


def group_sentences_by_article(sentences: List[Dict]) -> Dict[str, List[Dict]]:
    """Group sentences by article_id"""
    grouped = {}
    for sent in sentences:
        article_id = sent['article_id']
        if article_id not in grouped:
            grouped[article_id] = []
        grouped[article_id].append(sent)
    
    return grouped


def migrate_csv_to_db(
    csv_file: Path,
    metadata_file: Path,
    db: CorpusDB,
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """
    Migrate CSV and metadata to database
    
    Args:
        csv_file: Path to CSV file
        metadata_file: Path to metadata JSON file
        db: CorpusDB instance
        dry_run: If True, don't actually insert data
    
    Returns:
        Tuple of (documents_inserted, sentences_inserted, alignments_inserted)
    """
    print(f"\n{'='*60}")
    print(f"Migrando: {csv_file.name}")
    print(f"{'='*60}\n")
    
    # Load data
    print("Cargando datos...")
    metadata_list = load_metadata(metadata_file)
    sentences = load_csv_sentences(csv_file)
    
    if not sentences:
        print("⚠️  No hay sentencias para migrar")
        return 0, 0, 0
    
    print(f"  ✓ {len(metadata_list)} artículos en metadata")
    print(f"  ✓ {len(sentences)} pares de sentencias en CSV")
    
    # Group sentences by article
    grouped_sentences = group_sentences_by_article(sentences)
    print(f"  ✓ {len(grouped_sentences)} artículos únicos en CSV")
    
    if dry_run:
        print("\n[DRY RUN] No se insertarán datos reales\n")
        return 0, 0, 0
    
    # Create or get source
    print("\nCreando fuente...")
    source_id = db.insert_source(
        name='JW.org Purépecha-Spanish',
        author='Testigos de Jehová',
        publisher='Watch Tower Bible and Tract Society',
        licence='Fair Use - Research/Educational',
        url='https://www.jw.org'
    )
    print(f"  ✓ Source ID: {source_id}")
    
    # Process each article
    docs_inserted = 0
    sents_inserted = 0
    aligns_inserted = 0
    
    for article_id, article_sentences in grouped_sentences.items():
        print(f"\n  Procesando artículo {article_id}...")
        
        # Find metadata for this article
        article_meta = next(
            (m for m in metadata_list if str(m['article_id']) == str(article_id)),
            None
        )
        
        if not article_meta:
            print(f"    ⚠️  Metadata no encontrado para {article_id}, usando valores por defecto")
            article_meta = {
                'tsz_title': f'Article {article_id}',
                'es_title': f'Artículo {article_id}',
                'tsz_sentence_count': 0,
                'es_sentence_count': 0
            }
        
        # Create Purépecha document
        tsz_doc_id = db.insert_document(
            source_id=source_id,
            title=article_meta.get('tsz_title', f'Article {article_id}'),
            lang='tsz',
            genre='religious',
            tsz_dialect='lacustre',  # Assuming lacustre dialect
            metadata={
                'article_id': article_id,
                'url': article_meta.get('tsz_url', ''),
                'sentence_count': article_meta.get('tsz_sentence_count', 0),
                'collected_at': article_meta.get('collected_at', datetime.now().isoformat()),
                'source': 'jw_scraper.py'
            }
        )
        
        # Create Spanish document
        es_doc_id = db.insert_document(
            source_id=source_id,
            title=article_meta.get('es_title', f'Artículo {article_id}'),
            lang='es',
            genre='religious',
            metadata={
                'article_id': article_id,
                'url': article_meta.get('es_url', ''),
                'sentence_count': article_meta.get('es_sentence_count', 0),
                'collected_at': article_meta.get('collected_at', datetime.now().isoformat()),
                'source': 'jw_scraper.py'
            }
        )
        
        docs_inserted += 2
        print(f"    ✓ Documentos creados: tsz={tsz_doc_id}, es={es_doc_id}")
        
        # Insert sentences and create alignments
        tsz_sent_ids = []
        es_sent_ids = []
        
        for sent_data in article_sentences:
            sent_num = sent_data['sentence_number']
            tsz_text = sent_data['purepecha']
            es_text = sent_data['spanish']
            
            # Insert Purépecha sentence
            if tsz_text.strip():
                try:
                    tsz_id = db.insert_sentence(
                        document_id=tsz_doc_id,
                        text=tsz_text,
                        lang='tsz',
                        sibling_pos=sent_num,
                        tsz_dialect='lacustre',
                        metadata={'sentence_number': sent_num}
                    )
                    if tsz_id:
                        tsz_sent_ids.append(tsz_id)
                        sents_inserted += 1
                except Exception as e:
                    print(f"Error insertando sentencia: {e}")
            
            # Insert Spanish sentence
            if es_text.strip():
                try:
                    es_id = db.insert_sentence(
                        document_id=es_doc_id,
                        text=es_text,
                        lang='es',
                        sibling_pos=sent_num,
                        metadata={'sentence_number': sent_num}
                    )
                    if es_id:
                        es_sent_ids.append(es_id)
                        sents_inserted += 1
                except Exception as e:
                    print(f"Error insertando sentencia: {e}")
        
        # Create alignments (only if both sentences exist)
        min_len = min(len(tsz_sent_ids), len(es_sent_ids))
        for i in range(min_len):
            try:
                align_id = db.insert_alignment(
                    tsz_sentence_id=tsz_sent_ids[i],
                    es_sentence_id=es_sent_ids[i],
                    alignment_method='manual',  # From CSV, assumed manual
                    confidence=1.0,  # Perfect confidence since it's from source
                    quality=0.8  # Good quality, but needs review
                )
                if align_id:
                    aligns_inserted += 1
            except Exception as e:
                print(f"      ⚠️  Error creando alineamiento: {e}")
        
        print(f"    ✓ Sentencias: {len(tsz_sent_ids)} tsz, {len(es_sent_ids)} es")
        print(f"    ✓ Alineamientos: {min_len}")
    
    return docs_inserted, sents_inserted, aligns_inserted


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Migrar CSVs de jw_scraper.py a PostgreSQL'
    )
    parser.add_argument(
        '--csv-dir',
        type=str,
        default='outputs/jw',
        help='Directorio con archivos CSV (default: outputs/jw)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular migración sin insertar datos'
    )
    parser.add_argument(
        '--csv-file',
        type=str,
        help='Migrar solo un archivo CSV específico'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"J'atzingueni Corpus - Migración CSV → PostgreSQL")
    print(f"{'='*60}\n")
    
    # Initialize database connection
    print("Conectando a base de datos...")
    db_conn = get_db_connection()
    db_conn.connect()
    corpus_db = CorpusDB(db_conn)
    print("✓ Conexión establecida")
    
    # Get CSV files
    script_dir = Path(__file__).parent.parent
    csv_dir = script_dir / args.csv_dir
    
    if not csv_dir.exists():
        print(f"✗ Directorio no encontrado: {csv_dir}")
        sys.exit(1)
    
    if args.csv_file:
        # Single file migration
        csv_files = [csv_dir / args.csv_file]
    else:
        # Find all CSV files (excluding corrected_ files)
        csv_files = [
            f for f in csv_dir.glob('sentences_*.csv')
            if not f.name.startswith('corrected_')
        ]
    
    if not csv_files:
        print(f"✗ No se encontraron archivos CSV en {csv_dir}")
        sys.exit(1)
    
    csv_files = sorted(csv_files)
    print(f"\nArchivos CSV encontrados: {len(csv_files)}")
    for f in csv_files:
        print(f"  - {f.name}")
    
    # Migrate each CSV
    total_docs = 0
    total_sents = 0
    total_aligns = 0
    
    for csv_file in csv_files:
        # Find corresponding metadata file
        timestamp = csv_file.stem.replace('sentences_', '')
        metadata_file = csv_dir / f'metadata_{timestamp}.json'
        
        try:
            docs, sents, aligns = migrate_csv_to_db(
                csv_file,
                metadata_file,
                corpus_db,
                args.dry_run
            )
            
            # Commit after successful migration of each file
            if not args.dry_run:
                db_conn.commit()
                print(f"  ✓ Cambios guardados en base de datos")
            
            total_docs += docs
            total_sents += sents
            total_aligns += aligns
            
        except Exception as e:
            print(f"\n✗ Error migrando {csv_file.name}: {e}")
            import traceback
            traceback.print_exc()
            # Rollback on error
            db_conn.rollback()
            print(f"  ✗ Cambios revertidos")
            continue
    
    # Show summary
    print(f"\n{'='*60}")
    print(f"Resumen de Migración")
    print(f"{'='*60}\n")
    print(f"Archivos procesados: {len(csv_files)}")
    print(f"Documentos insertados: {total_docs}")
    print(f"Sentencias insertadas: {total_sents}")
    print(f"Alineamientos creados: {total_aligns}")
    
    if not args.dry_run:
        # Show corpus statistics
        print(f"\n{'='*60}")
        print(f"Estadísticas del Corpus")
        print(f"{'='*60}\n")
        
        stats = corpus_db.get_corpus_stats()
        print(f"Fuentes: {stats.get('total_sources', 0)}")
        print(f"Documentos por idioma: {stats.get('documents_by_language', {})}")
        print(f"Sentencias por idioma: {stats.get('sentences_by_language', {})}")
        print(f"Alineamientos totales: {stats.get('total_alignments', 0)}")
    
    print(f"\n{'='*60}")
    print(f"✓ Migración completada")
    print(f"{'='*60}\n")
    
    # Close connection
    db_conn.close()


if __name__ == '__main__':
    main()

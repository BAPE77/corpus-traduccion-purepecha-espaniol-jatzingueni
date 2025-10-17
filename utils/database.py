"""
Database utilities for J'atzingueni Corpus
Provides connection management and CRUD operations for PostgreSQL
"""

import os
import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

import psycopg2
from psycopg2 import sql, extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DBConnection:
    """PostgreSQL database connection manager"""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None
    ):
        """
        Initialize database connection
        
        Args:
            host: Database host (default: from env DB_HOST)
            port: Database port (default: from env DB_PORT)
            database: Database name (default: from env DB_NAME)
            user: Database user (default: from env DB_USER)
            password: Database password (default: from env DB_PASSWORD)
        """
        self.host = host or os.getenv('DB_HOST', 'localhost')
        self.port = port or int(os.getenv('DB_PORT', 5432))
        self.database = database or os.getenv('DB_NAME', 'jatzingueni_corpus')
        self.user = user or os.getenv('DB_USER', 'postgres')
        self.password = password or os.getenv('DB_PASSWORD', '')
        self.sslmode = os.getenv('DB_SSLMODE', 'prefer')
        
        self._connection = None
        self._cursor = None
    
    def connect(self) -> psycopg2.extensions.connection:
        """Establish database connection"""
        if self._connection is None or self._connection.closed:
            try:
                self._connection = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    sslmode=self.sslmode
                )
                print(f"✓ Conectado a PostgreSQL: {self.database}@{self.host}:{self.port}")
            except psycopg2.Error as e:
                print(f"✗ Error al conectar a PostgreSQL: {e}")
                raise
        
        return self._connection
    
    def close(self):
        """Close database connection"""
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        
        if self._connection and not self._connection.closed:
            self._connection.close()
            print("✓ Conexión cerrada")
    
    def cursor(self, cursor_factory=None):
        """Get database cursor"""
        conn = self.connect()
        if cursor_factory:
            return conn.cursor(cursor_factory=cursor_factory)
        return conn.cursor()
    
    def commit(self):
        """Commit current transaction"""
        if self._connection:
            self._connection.commit()
    
    def rollback(self):
        """Rollback current transaction"""
        if self._connection:
            self._connection.rollback()
    
    @contextmanager
    def transaction(self):
        """Context manager for transactions"""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
    
    def execute(self, query: str, params: tuple = None) -> Any:
        """
        Execute a query and return results
        
        Args:
            query: SQL query string
            params: Query parameters (tuple)
        
        Returns:
            Query results or None
        """
        with self.cursor() as cur:
            cur.execute(query, params)
            if cur.description:  # SELECT query
                return cur.fetchall()
            self.commit()
            return None
    
    def execute_one(self, query: str, params: tuple = None) -> Any:
        """Execute query and return single result"""
        with self.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchone()
            self.commit()
            return None


class CorpusDB:
    """High-level database operations for corpus management"""
    
    def __init__(self, connection: DBConnection = None):
        """
        Initialize corpus database
        
        Args:
            connection: DBConnection instance (creates new if None)
        """
        self.db = connection or DBConnection()
    
    # =========================================================================
    # SOURCES
    # =========================================================================
    
    def insert_source(
        self,
        name: str,
        author: str = None,
        publisher: str = None,
        licence: str = None,
        url: str = None
    ) -> int:
        """
        Insert a new source or return existing ID
        
        Args:
            name: Source name
            author: Author name
            publisher: Publisher name
            licence: License type
            url: Source URL
        
        Returns:
            Source ID (BIGINT)
        """
        # Check if source already exists
        query_check = """
            SELECT id FROM sources WHERE name = %s
        """
        result = self.db.execute_one(query_check, (name,))
        
        if result:
            return result[0]
        
        # Insert new source
        query_insert = """
            INSERT INTO sources (name, author, publisher, licence, url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        result = self.db.execute_one(
            query_insert,
            (name, author, publisher, licence, url)
        )
        
        return result[0] if result else None
    
    def get_source_by_name(self, name: str) -> Optional[Dict]:
        """Get source by name"""
        query = """
            SELECT id, name, author, publisher, licence, url, created_at
            FROM sources
            WHERE name = %s
        """
        result = self.db.execute_one(query, (name,))
        
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'author': result[2],
                'publisher': result[3],
                'licence': result[4],
                'url': result[5],
                'created_at': result[6]
            }
        return None
    
    # =========================================================================
    # DOCUMENTS
    # =========================================================================
    
    def insert_document(
        self,
        source_id: int,
        title: str,
        lang: str,
        genre: str = None,
        tsz_dialect: str = None,
        raw_text: str = None,
        full_text: str = None,
        metadata: Dict = None
    ) -> int:
        """
        Insert a new document
        
        Args:
            source_id: Source ID (FK)
            title: Document title
            lang: Language code (tsz, es, en)
            genre: Document genre
            tsz_dialect: Purépecha dialect (if lang='tsz')
            raw_text: Original raw text
            full_text: Processed full text
            metadata: Additional metadata (JSONB)
        
        Returns:
            Document ID (BIGINT)
        """
        query = """
            INSERT INTO documents 
            (source_id, title, lang, genre, tsz_dialect, raw_text, full_text, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        result = self.db.execute_one(
            query,
            (source_id, title, lang, genre, tsz_dialect, raw_text, full_text, metadata_json)
        )
        
        return result[0] if result else None
    
    def get_document_by_id(self, doc_id: int) -> Optional[Dict]:
        """Get document by ID"""
        query = """
            SELECT id, source_id, title, lang, genre, tsz_dialect, 
                   raw_text, full_text, metadata, created_at
            FROM documents
            WHERE id = %s
        """
        result = self.db.execute_one(query, (doc_id,))
        
        if result:
            return {
                'id': result[0],
                'source_id': result[1],
                'title': result[2],
                'lang': result[3],
                'genre': result[4],
                'tsz_dialect': result[5],
                'raw_text': result[6],
                'full_text': result[7],
                'metadata': result[8],
                'created_at': result[9]
            }
        return None
    
    # =========================================================================
    # SENTENCES
    # =========================================================================
    
    def insert_sentence(
        self,
        document_id: int,
        text: str,
        lang: str,
        sibling_pos: int = None,
        tsz_dialect: str = None,
        metadata: Dict = None
    ) -> int:
        """
        Insert a new sentence (simplified - without document_section for now)
        
        Args:
            document_id: Document ID (FK)
            text: Sentence text
            lang: Language code
            sibling_pos: Position in document (optional)
            tsz_dialect: Purépecha dialect
            metadata: Additional metadata
        
        Returns:
            Sentence ID (BIGINT)
        """
        # Simplified version that doesn't require parent_id/type_id (thanks to patches)
        
        query = """
            INSERT INTO sentences 
            (document_id, text, lang, sibling_pos, tsz_dialect, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        result = self.db.execute_one(
            query,
            (document_id, text, lang, sibling_pos, tsz_dialect, metadata_json)
        )
        
        if result:
            return result[0]
        return None
        
        try:
            result = self.db.execute_one(
                query,
                (document_id, text, lang, tsz_dialect, metadata_json)
            )
            return result[0] if result else None
        except psycopg2.Error as e:
            print(f"Error insertando sentencia: {e}")
            return None
    
    def get_sentences_by_document(self, document_id: int) -> List[Dict]:
        """Get all sentences for a document"""
        query = """
            SELECT id, document_id, text, lang, tsz_dialect, 
                   processing_status, quality, confidence, created_at
            FROM sentences
            WHERE document_id = %s
            ORDER BY id
        """
        results = self.db.execute(query, (document_id,))
        
        sentences = []
        for row in results:
            sentences.append({
                'id': row[0],
                'document_id': row[1],
                'text': row[2],
                'lang': row[3],
                'tsz_dialect': row[4],
                'processing_status': row[5],
                'quality': row[6],
                'confidence': row[7],
                'created_at': row[8]
            })
        
        return sentences
    
    # =========================================================================
    # ALIGNMENTS
    # =========================================================================
    
    def insert_alignment(
        self,
        tsz_sentence_id: int,
        es_sentence_id: int,
        alignment_method: str = 'manual',
        confidence: float = None,
        quality: float = None,
        word_alignments: Dict = None
    ) -> int:
        """
        Insert sentence alignment
        
        Args:
            tsz_sentence_id: Purépecha sentence ID
            es_sentence_id: Spanish sentence ID
            alignment_method: Alignment method
            confidence: Confidence score (0-1)
            quality: Quality score (0-1)
            word_alignments: Word-level alignments (JSONB)
        
        Returns:
            Alignment ID (BIGINT)
        """
        query = """
            INSERT INTO alignments 
            (tsz_sentence_id, es_sentence_id, alignment_method, 
             confidence, quality, word_alignments)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        word_alignments_json = json.dumps(word_alignments) if word_alignments else None
        
        result = self.db.execute_one(
            query,
            (tsz_sentence_id, es_sentence_id, alignment_method, 
             confidence, quality, word_alignments_json)
        )
        
        return result[0] if result else None
    
    def get_unaligned_sentence_pairs(self, limit: int = 1000) -> List[Dict]:
        """
        Get sentence pairs that haven't been aligned yet
        
        Args:
            limit: Maximum number of pairs to return
        
        Returns:
            List of sentence pair dictionaries
        """
        # This is a placeholder - actual implementation depends on your alignment strategy
        # For now, returns empty list
        return []
    
    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================
    
    def insert_sentences_batch(
        self,
        document_id: int,
        sentences: List[Tuple[str, str, int]],  # (text, lang, sibling_pos)
        tsz_dialect: str = None
    ) -> List[int]:
        """
        Insert multiple sentences in batch
        
        Args:
            document_id: Document ID
            sentences: List of (text, lang, sibling_pos) tuples
            tsz_dialect: Purépecha dialect (if applicable)
        
        Returns:
            List of sentence IDs
        """
        query = """
            INSERT INTO sentences 
            (document_id, text, lang, tsz_dialect)
            VALUES %s
            RETURNING id
        """
        
        # Prepare data for batch insert
        data = [
            (document_id, text, lang, tsz_dialect if lang == 'tsz' else None)
            for text, lang, _ in sentences
        ]
        
        try:
            with self.db.cursor() as cur:
                # Use execute_values for efficient batch insert
                result = extras.execute_values(
                    cur, query, data, 
                    template="(%s, %s, %s, %s)",
                    fetch=True
                )
                self.db.commit()
                return [row[0] for row in result]
        except psycopg2.Error as e:
            print(f"Error en inserción batch: {e}")
            self.db.rollback()
            return []
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_corpus_stats(self) -> Dict:
        """Get corpus statistics"""
        stats = {}
        
        # Count sources
        result = self.db.execute_one("SELECT COUNT(*) FROM sources")
        stats['total_sources'] = result[0] if result else 0
        
        # Count documents by language
        query_docs = """
            SELECT lang, COUNT(*) 
            FROM documents 
            GROUP BY lang
        """
        results = self.db.execute(query_docs)
        stats['documents_by_language'] = {row[0]: row[1] for row in results}
        
        # Count sentences by language
        query_sents = """
            SELECT lang, COUNT(*) 
            FROM sentences 
            GROUP BY lang
        """
        results = self.db.execute(query_sents)
        stats['sentences_by_language'] = {row[0]: row[1] for row in results}
        
        # Count alignments
        result = self.db.execute_one("SELECT COUNT(*) FROM alignments")
        stats['total_alignments'] = result[0] if result else 0
        
        return stats


class PipelineRunTracker:
    """Track pipeline execution runs"""
    
    def __init__(self, connection: DBConnection = None):
        """Initialize pipeline tracker"""
        self.db = connection or DBConnection()
        self.current_run_id = None
    
    def start_run(
        self,
        name: str,
        pipeline_type: str,
        configuration: Dict
    ) -> int:
        """
        Start a new pipeline run
        
        Args:
            name: Run name
            pipeline_type: Type (collection, alignment, export)
            configuration: Run configuration (JSONB)
        
        Returns:
            Run ID (BIGINT)
        """
        query = """
            INSERT INTO pipeline_runs 
            (name, pipeline_type, configuration, status)
            VALUES (%s, %s, %s, 'running')
            RETURNING id
        """
        
        config_json = json.dumps(configuration)
        result = self.db.execute_one(query, (name, pipeline_type, config_json))
        
        self.current_run_id = result[0] if result else None
        return self.current_run_id
    
    def update_progress(
        self,
        items_processed: int,
        items_succeeded: int,
        items_failed: int
    ):
        """Update pipeline run progress"""
        if not self.current_run_id:
            return
        
        query = """
            UPDATE pipeline_runs
            SET items_processed = %s,
                items_succeeded = %s,
                items_failed = %s
            WHERE id = %s
        """
        
        self.db.execute(
            query,
            (items_processed, items_succeeded, items_failed, self.current_run_id)
        )
    
    def complete_run(
        self,
        status: str = 'completed',
        error_message: str = None
    ):
        """Mark pipeline run as completed"""
        if not self.current_run_id:
            return
        
        query = """
            UPDATE pipeline_runs
            SET status = %s,
                error_message = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        
        self.db.execute(query, (status, error_message, self.current_run_id))
        self.current_run_id = None


# =========================================================================
# SINGLETON INSTANCES
# =========================================================================

_db_connection = None
_corpus_db = None


def get_db_connection() -> DBConnection:
    """Get singleton database connection"""
    global _db_connection
    if _db_connection is None:
        _db_connection = DBConnection()
    return _db_connection


def get_corpus_db() -> CorpusDB:
    """Get singleton corpus database instance"""
    global _corpus_db
    if _corpus_db is None:
        _corpus_db = CorpusDB(get_db_connection())
    return _corpus_db

-- ============================================================================
-- J'atzingueni Corpus Database Schema
-- PostgreSQL Database Design for Purépecha-Spanish Parallel Corpus
-- ============================================================================
-- 
-- This schema supports:
-- 1. Agglutinative morphology (Purépecha linguistic features)
-- 2. Automated data collection pipelines
-- 3. Manual annotation and correction workflows
-- 4. Quality metrics tracking
-- 5. Version control for linguistic datasets
-- 6. Dialectal variation tracking (PostGIS)
-- 7. Integration with PyTorch and mobile app APIs
--
-- Author: J'atzingueni Corpus Team
-- Created: September 2025
-- Updated: October 2025 - Migrated to BIGINT IDs and new structure
-- ============================================================================

-- ============================================================================
-- CLEANUP: Drop existing objects (for re-running script)
-- ============================================================================
-- WARNING: This will destroy all existing data!
-- Comment out this section if you want to preserve data

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS export_jobs CASCADE;
DROP TABLE IF EXISTS annotation_decisions CASCADE;
DROP TABLE IF EXISTS annotation_tasks CASCADE;
DROP TABLE IF EXISTS corpus_statistics CASCADE;
DROP TABLE IF EXISTS alignment_quality_metrics CASCADE;
DROP TABLE IF EXISTS pipeline_runs CASCADE;
DROP TABLE IF EXISTS morphological_annotations CASCADE;
DROP TABLE IF EXISTS alignments CASCADE;
DROP TABLE IF EXISTS sentences CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS document_groups CASCADE;
DROP TABLE IF EXISTS sources CASCADE;

-- Drop custom types
DROP TYPE IF EXISTS language_code CASCADE;
DROP TYPE IF EXISTS document_genre CASCADE;
DROP TYPE IF EXISTS alignment_method CASCADE;
DROP TYPE IF EXISTS processing_status CASCADE;
DROP TYPE IF EXISTS purepecha_dialect CASCADE;

-- Note: Extensions are not dropped as they may be used by other databases
-- If you need to drop them, uncomment the following lines:
-- DROP EXTENSION IF EXISTS "btree_gin";
-- DROP EXTENSION IF EXISTS "postgis";
-- DROP EXTENSION IF EXISTS "pg_trgm";

-- ============================================================================
-- EXTENSIONS: Enable required extensions
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram similarity for text search
CREATE EXTENSION IF NOT EXISTS "postgis";        -- Geospatial data for dialectal mapping
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN indexes on scalar types

-- ============================================================================
-- ENUMERATION TYPES
-- ============================================================================

-- Language codes (ISO 639-3)
CREATE TYPE language_code AS ENUM ('tsz', 'es', 'en');  -- Purépecha, Spanish, English

-- Document genre classification
CREATE TYPE document_genre AS ENUM (
    'religious',        -- Religious texts
    'educational',      -- Educational materials
    'conversational',   -- Conversational/dialogue
    'narrative'         -- Narrative/storytelling
);

-- Alignment method
CREATE TYPE alignment_method AS ENUM (
    'fast_align',       -- Fast align tool
    'awesome_align',    -- Awesome-align (BERT-based)
    'sim_align',        -- SimAlign
    'manual',           -- Human annotation
    'hybrid',           -- Combination of automatic + manual
    'eflomal'           -- Eflomal alignment tool
);

-- Processing status of data entries on the corpus
/**
 * IMPORTANT: valid state transitions should be:
 *     Initial state: raw
        ```mermaid
            stateDiagram-v2
                [*] --> raw: Start
                
                raw --> machine_generated: machine_algorithm
                raw --> human_generated: human_feedback

                machine_generated --> raw: review → redo
                machine_generated --> validated: review → approve
                machine_generated --> rejected: review → reject

                human_generated --> raw: review → redo
                human_generated --> validated: review → approve
                human_generated --> rejected: review → reject

                
                note right of validated
                    Data included in corpus
                end note
                
                note right of rejected
                    Data excluded from corpus, stored for future analysis
                end note
        ```
 * TODO: Implement state machine verification for preventing invalid transitions
         of processing_status values.
 */
CREATE TYPE processing_status AS ENUM (
    'raw',               -- Ready to be processed
    'machine_generated', -- Machine generated
    'human_generated',   -- Human generated
    'validated',         -- Data is ready to use
    'rejected'           -- Data is not suitable for use
);

-- Purépecha dialects (updated regional classification)
CREATE TYPE purepecha_dialect AS ENUM (
    'lacustre',         -- Lake region dialect (Pátzcuaro area)
    'central',          -- Central dialect
    'serrana',          -- Mountain/highland dialect
    'mixed',            -- Mixed features
    'unknown'           -- Dialect unknown
);

-- ============================================================================
-- CORE TABLES: SOURCES AND DOCUMENTS
-- ============================================================================

-- Source collections (e.g., JW.org, Bible translations, literary works)
CREATE TABLE sources (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(512) NOT NULL,
    author VARCHAR(512),
    publisher VARCHAR(256),
    licence VARCHAR(128),
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Document groups for parallel document organization
-- e.g., "The Bible: Jehovah Witnesses Edition" groups all language versions
CREATE TABLE document_groups (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(512) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Documents within sources (e.g., articles, chapters, books)
CREATE TABLE documents (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    document_group_id BIGINT REFERENCES document_groups(id) ON DELETE SET NULL,
    title VARCHAR(500),
    genre document_genre,
    lang language_code NOT NULL,
    tsz_dialect purepecha_dialect,  -- Only applicable when lang='tsz'
    metadata JSONB DEFAULT '{}',
    
    -- Text content
    raw_text TEXT,          -- Original unmodified text
    full_text TEXT,         -- Formatted text ready for training
    text_vector TSVECTOR,   -- Full-text search optimization
    
    -- Overall quality metric
    human_lang_quality DOUBLE PRECISION CHECK (
        human_lang_quality >= 0 AND human_lang_quality <= 1
    ),
    machine_lang_confidence DOUBLE PRECISION CHECK (
        machine_lang_confidence >= 0 AND machine_lang_confidence <= 1
    ),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_tsz_dialect CHECK (
        (lang = 'tsz' AND tsz_dialect IS NOT NULL) OR 
        (lang != 'tsz' AND tsz_dialect IS NULL)
    )
);

-- ============================================================================
-- SENTENCES AND SEGMENTS
-- ============================================================================

-- Sentences table (from all supported languages)
CREATE TABLE sentences (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    index INTEGER NOT NULL,  -- Order within document
    lang language_code NOT NULL,
    tsz_dialect purepecha_dialect,  -- Only applicable when lang='tsz'
    tsz_dialectal_features JSONB DEFAULT '{}',
    
    -- Main text content
    string TEXT NOT NULL,  -- String ready to be used in models
    
    -- Full-text search vector (updated by trigger)
    text_vec TSVECTOR,
    
    -- Geospatial data for dialectal mapping
    collection_location GEOMETRY(Point, 4326),  -- Where this variant was collected
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Quality metric
    processing_status processing_status DEFAULT 'raw',
    quality DOUBLE PRECISION CHECK (
        quality >= 0 AND quality <= 1
    ),
    confidence DOUBLE PRECISION CHECK (
        confidence >= 0 AND confidence <= 1
    ),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT sentences_document_index_unique UNIQUE (document_id, index),
    CONSTRAINT check_sentence_tsz_dialect CHECK (
        (lang = 'tsz' AND tsz_dialect IS NOT NULL) OR 
        (lang != 'tsz' AND tsz_dialect IS NULL)
    )
);

-- ============================================================================
-- ALIGNMENTS: AUTOMATIC AND MANUAL
-- ============================================================================

-- Sentence pair alignments
CREATE TABLE alignments (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    
    -- Source and target sentences
    tsz_sentence_id BIGINT NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    es_sentence_id BIGINT NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    
    -- Alignment metadata
    alignment_method alignment_method NOT NULL,
    
    -- Quality tracking
    processing_status processing_status DEFAULT 'raw',
    confidence DOUBLE PRECISION CHECK ( -- Replaces former alignment_score
        confidence >= 0 AND confidence <= 1
    ),
    quality DOUBLE PRECISION CHECK (
        quality >= 0 AND quality <= 1
    ),

    -- Word-level alignment data (stored as JSONB)
    word_alignments JSONB,  -- Format: [{"src_idx": 0, "tgt_idx": 1, "score": 0.95}, ...]
    
    -- Manual correction tracking
    corrected_by VARCHAR(255),  -- User who corrected
    correction_notes TEXT,
    
    -- Version control
    version INTEGER DEFAULT 1,
    parent_alignment_id BIGINT REFERENCES alignments(id),  -- For tracking corrections
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT alignments_sentence_pair_unique UNIQUE (tsz_sentence_id, es_sentence_id, version)
);

-- ============================================================================
-- MORPHOLOGICAL ANNOTATIONS (Purépecha agglutinative features)
-- ============================================================================

-- ============================================================================
-- MORPHOLOGICAL ANNOTATIONS (Purépecha agglutinative features)
-- ============================================================================

-- Token-level morphological analysis
CREATE TABLE morphological_annotations (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    sentence_id BIGINT NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    token_index INTEGER NOT NULL,  -- Position in sentence
    token TEXT NOT NULL,  -- Surface form
    
    -- Morphological decomposition
    morphemes TEXT[] NOT NULL,  -- Array of morphemes (e.g., ['ka', 'rhani', 'ni'])
    morpheme_glosses TEXT[],    -- Glosses for each morpheme
    morpheme_types TEXT[],      -- Types: 'root', 'affix', 'suffix', 'prefix', 'clitic'
    
    -- Grammatical features (following Universal Dependencies conventions)
    pos_tag VARCHAR(20),        -- Part of speech
    upos VARCHAR(20),           -- Universal POS tag
    features JSONB,             -- Morphological features (case, number, person, etc.)
    
    -- Annotation metadata
    annotation_method VARCHAR(50),  -- 'automatic', 'manual', 'corrected'
    annotator VARCHAR(255),
    confidence_score DECIMAL(5,4),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT morphological_annotations_sentence_token_unique UNIQUE (sentence_id, token_index)
);

-- ============================================================================
-- QUALITY METRICS AND PIPELINE TRACKING
-- ============================================================================

-- Pipeline execution tracking
CREATE TABLE pipeline_runs (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(255) NOT NULL,
    pipeline_type VARCHAR(100) NOT NULL,  -- 'collection', 'alignment', 'export'
    
    -- Run configuration
    configuration JSONB NOT NULL,  -- Pipeline parameters
    
    -- Execution details
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error_message TEXT,
    
    -- Statistics
    items_processed INTEGER DEFAULT 0,
    items_succeeded INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Quality metrics for alignments
-- TODO: redefine role of this entity as it talks about aggregated metrics
--       of translation quality of individual training data on a pipeline run, 
--       a thing that does not make sense. Maybe making this entity just only
--       listing metrics of a running model with a certain training data and a
--       certain evaluation set?
CREATE TABLE alignment_quality_metrics (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    alignment_id BIGINT REFERENCES alignments(id) ON DELETE CASCADE,
    pipeline_run_id BIGINT REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    
    -- Primary metric: Alignment accuracy
    alignment_accuracy DECIMAL(5,4),
    
    -- Secondary metrics
    bleu_score DECIMAL(5,4),
    ter_score DECIMAL(5,4),  -- Translation Error Rate
    length_ratio DECIMAL(5,4),
    
    -- Corpus-level statistics
    corpus_size_tokens INTEGER,
    vocabulary_size INTEGER,
    oov_rate DECIMAL(5,4),  -- Out-of-vocabulary rate
    
    -- Processing metrics
    processing_time_ms INTEGER,
    
    -- Metadata
    metrics_data JSONB DEFAULT '{}',  -- Additional flexible metrics
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Corpus statistics (aggregated metrics)
CREATE TABLE corpus_statistics (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Sentence counts
    total_sentence_pairs INTEGER,
    tsz_sentences INTEGER,
    es_sentences INTEGER,
    
    -- Alignment statistics
    auto_aligned_count INTEGER,
    manually_reviewed_count INTEGER,
    validated_count INTEGER,
    
    -- Quality metrics (averages)
    avg_alignment_accuracy DECIMAL(5,4),
    avg_alignment_score DECIMAL(5,4),
    
    -- Corpus size
    total_tsz_tokens INTEGER,
    total_es_tokens INTEGER,
    tsz_vocabulary_size INTEGER,
    es_vocabulary_size INTEGER,
    
    -- Coverage by source
    coverage_by_source JSONB,  -- {"jw_org": 50000, "biblical": 30000}
    
    -- Dialectal distribution
    dialect_distribution JSONB,  -- {"lacustre": 45, "central": 30, "serrana": 25}
    
    -- Additional statistics
    additional_stats JSONB DEFAULT '{}'
);

-- ============================================================================
-- MANUAL ANNOTATION WORKFLOW
-- ============================================================================

-- Annotation tasks for human reviewers
CREATE TABLE annotation_tasks (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    type VARCHAR(50) NOT NULL,  -- 'alignment_review', 'morphology_annotation', 'quality_check'
    
    -- Task assignment
    assigned_to VARCHAR(255),
    priority INTEGER DEFAULT 5,  -- 1-10, higher is more urgent
    
    -- Task items (references to sentences, alignments, etc.)
    target_items JSONB NOT NULL,  -- Array of IDs to review
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed'
    progress INTEGER DEFAULT 0,  -- Percentage complete
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Notes
    notes TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Annotation decisions (audit trail)
CREATE TABLE annotation_decisions (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    task_id BIGINT REFERENCES annotation_tasks(id) ON DELETE CASCADE,
    
    -- What was annotated
    entity_type VARCHAR(50) NOT NULL,  -- 'sentence', 'alignment', 'morphology'
    entity_id BIGINT NOT NULL,
    
    -- Decision details
    decision_type VARCHAR(50) NOT NULL,  -- 'accept', 'reject', 'correct', 'flag'
    previous_value JSONB,
    new_value JSONB,
    
    -- Annotator information
    annotator VARCHAR(255) NOT NULL,
    confidence INTEGER,  -- 1-5 scale
    notes TEXT,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- EXPORT AND INTEROPERABILITY
-- ============================================================================

-- Export jobs for different formats (TMX, CoNLL-U, JSON, etc.)
CREATE TABLE export_jobs (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    format VARCHAR(50) NOT NULL,  -- 'tmx', 'conllu', 'json', 'parallel_text', 'pytorch'
    
    -- Export criteria
    filter_criteria JSONB,  -- Which data to export
    
    -- Output details
    output_path TEXT,
    file_size_bytes BIGINT,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Statistics
    records_exported INTEGER,
    metadata JSONB DEFAULT '{}'
);

-- -- ============================================================================
-- -- INDEXES FOR PERFORMANCE
-- -- ============================================================================

-- -- Full-text search indexes
-- CREATE INDEX idx_sentences_text_vec ON sentences USING GIN(text_vec);
-- CREATE INDEX idx_sentences_string_trgm ON sentences USING GIN(string gin_trgm_ops);
-- CREATE INDEX idx_documents_text_vector ON documents USING GIN(text_vector);

-- -- Foreign key indexes
-- CREATE INDEX idx_documents_source_id ON documents(source_id);
-- CREATE INDEX idx_documents_group_id ON documents(document_group_id);
-- CREATE INDEX idx_sentences_document_id ON sentences(document_id);
-- CREATE INDEX idx_alignments_tsz_sentence ON alignments(tsz_sentence_id);
-- CREATE INDEX idx_alignments_es_sentence ON alignments(es_sentence_id);
-- CREATE INDEX idx_morphological_annotations_sentence ON morphological_annotations(sentence_id);

-- -- Language and quality filters
-- CREATE INDEX idx_sentences_lang ON sentences(lang);
-- CREATE INDEX idx_sentences_quality ON sentences(quality);
-- CREATE INDEX idx_documents_lang ON documents(lang);
-- CREATE INDEX idx_documents_genre ON documents(genre);
-- CREATE INDEX idx_alignments_quality_status ON alignments(quality_status);
-- CREATE INDEX idx_alignments_method ON alignments(alignment_method);

-- -- Dialectal indexes
-- CREATE INDEX idx_sentences_tsz_dialect ON sentences(tsz_dialect) WHERE lang = 'tsz';
-- CREATE INDEX idx_documents_tsz_dialect ON documents(tsz_dialect) WHERE lang = 'tsz';

-- -- Temporal indexes for queries
-- CREATE INDEX idx_sentences_created_at ON sentences(created_at);
-- CREATE INDEX idx_alignments_created_at ON alignments(created_at);
-- CREATE INDEX idx_pipeline_runs_started_at ON pipeline_runs(started_at);

-- -- Composite indexes for common queries
-- CREATE INDEX idx_sentences_document_lang_index ON sentences(document_id, lang, index);
-- CREATE INDEX idx_alignments_quality_method ON alignments(quality_status, alignment_method);

-- -- Geospatial index for dialectal analysis
-- CREATE INDEX idx_sentences_location ON sentences USING GIST(collection_location);

-- -- GIN indexes for JSONB queries
-- CREATE INDEX idx_sentences_metadata ON sentences USING GIN(metadata);
-- CREATE INDEX idx_documents_metadata ON documents USING GIN(metadata);
-- CREATE INDEX idx_alignments_word_alignments ON alignments USING GIN(word_alignments);
-- CREATE INDEX idx_morphological_features ON morphological_annotations USING GIN(features);
-- CREATE INDEX idx_corpus_stats_coverage ON corpus_statistics USING GIN(coverage_by_source);

-- -- ============================================================================
-- -- TRIGGERS AND FUNCTIONS
-- -- ============================================================================

-- -- Update timestamp trigger function
-- CREATE OR REPLACE FUNCTION update_updated_at_column()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     NEW.updated_at = CURRENT_TIMESTAMP;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- -- Apply update timestamp trigger to relevant tables
-- CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- CREATE TRIGGER update_document_groups_updated_at BEFORE UPDATE ON document_groups
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    
-- CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    
-- CREATE TRIGGER update_sentences_updated_at BEFORE UPDATE ON sentences
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    
-- CREATE TRIGGER update_alignments_updated_at BEFORE UPDATE ON alignments
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    
-- CREATE TRIGGER update_morphological_updated_at BEFORE UPDATE ON morphological_annotations
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -- Full-text search vector update trigger for sentences
-- CREATE OR REPLACE FUNCTION update_sentence_text_vec()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     IF NEW.lang = 'es' THEN
--         NEW.text_vec := to_tsvector('spanish', COALESCE(NEW.string, ''));
--     ELSE
--         NEW.text_vec := to_tsvector('simple', COALESCE(NEW.string, ''));
--     END IF;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- CREATE TRIGGER update_sentences_text_vec BEFORE INSERT OR UPDATE OF string
--     ON sentences FOR EACH ROW EXECUTE FUNCTION update_sentence_text_vec();

-- -- Full-text search vector update trigger for documents
-- CREATE OR REPLACE FUNCTION update_document_text_vector()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     IF NEW.lang = 'es' THEN
--         NEW.text_vector := to_tsvector('spanish', COALESCE(NEW.full_text, NEW.raw_text, ''));
--     ELSE
--         NEW.text_vector := to_tsvector('simple', COALESCE(NEW.full_text, NEW.raw_text, ''));
--     END IF;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- CREATE TRIGGER update_documents_text_vector BEFORE INSERT OR UPDATE OF full_text, raw_text
--     ON documents FOR EACH ROW EXECUTE FUNCTION update_document_text_vector();

-- -- Automatic corpus statistics update function
-- CREATE OR REPLACE FUNCTION update_corpus_statistics()
-- RETURNS VOID AS $$
-- BEGIN
--     INSERT INTO corpus_statistics (
--         total_sentence_pairs,
--         tsz_sentences,
--         es_sentences,
--         auto_aligned_count,
--         manually_reviewed_count,
--         validated_count,
--         avg_alignment_accuracy,
--         avg_alignment_score,
--         dialect_distribution
--     )
--     SELECT
--         COUNT(DISTINCT a.id) as total_sentence_pairs,
--         (SELECT COUNT(*) FROM sentences WHERE lang = 'tsz') as tsz_sentences,
--         (SELECT COUNT(*) FROM sentences WHERE lang = 'es') as es_sentences,
--         COUNT(*) FILTER (WHERE a.quality_status = 'auto_aligned') as auto_aligned_count,
--         COUNT(*) FILTER (WHERE a.quality_status = 'reviewed') as manually_reviewed_count,
--         COUNT(*) FILTER (WHERE a.quality_status = 'validated') as validated_count,
--         AVG(aqm.alignment_accuracy) as avg_alignment_accuracy,
--         AVG(a.alignment_score) as avg_alignment_score,
--         (
--             SELECT jsonb_object_agg(tsz_dialect, count)
--             FROM (
--                 SELECT tsz_dialect, COUNT(*) as count
--                 FROM sentences
--                 WHERE lang = 'tsz' AND tsz_dialect IS NOT NULL AND tsz_dialect != 'unknown'
--                 GROUP BY tsz_dialect
--             ) dialect_counts
--         ) as dialect_distribution
--     FROM alignments a
--     LEFT JOIN alignment_quality_metrics aqm ON a.id = aqm.alignment_id;
-- END;
-- $$ LANGUAGE plpgsql;

-- -- ============================================================================
-- -- VIEWS FOR COMMON QUERIES
-- -- ============================================================================

-- -- View for complete alignment information
-- CREATE VIEW v_complete_alignments AS
-- SELECT
--     a.alignment_id,
--     a.alignment_method,
--     a.alignment_score,
--     a.quality_status,
--     ps.sentence_id as purepecha_sentence_id,
--     ps.text as purepecha_text,
--     ps.dialect,
--     ss.sentence_id as spanish_sentence_id,
--     ss.text as spanish_text,
--     a.word_alignments,
--     aqm.alignment_accuracy,
--     aqm.bleu_score,
--     d_pur.document_identifier as purepecha_document,
--     d_spa.document_identifier as spanish_document,
--     src.source_name,
--     src.source_type,
--     a.created_at,
--     a.updated_at
-- FROM alignments a
-- JOIN sentences ps ON a.purepecha_sentence_id = ps.sentence_id
-- JOIN sentences ss ON a.spanish_sentence_id = ss.sentence_id
-- LEFT JOIN alignment_quality_metrics aqm ON a.alignment_id = aqm.alignment_id
-- LEFT JOIN documents d_pur ON ps.document_id = d_pur.document_id
-- LEFT JOIN documents d_spa ON ss.document_id = d_spa.document_id
-- LEFT JOIN sources src ON d_pur.source_id = src.source_id;

-- -- View for morphologically annotated sentences
-- CREATE VIEW v_morphologically_annotated_sentences AS
-- SELECT
--     s.sentence_id,
--     s.text,
--     s.language,
--     s.dialect,
--     s.quality_status,
--     array_agg(
--         jsonb_build_object(
--             'token', ma.token,
--             'morphemes', ma.morphemes,
--             'glosses', ma.morpheme_glosses,
--             'pos', ma.pos_tag,
--             'features', ma.features
--         ) ORDER BY ma.token_index
--     ) as morphological_analysis,
--     d.document_identifier,
--     src.source_name
-- FROM sentences s
-- JOIN morphological_annotations ma ON s.sentence_id = ma.sentence_id
-- JOIN documents d ON s.document_id = d.document_id
-- JOIN sources src ON d.source_id = src.source_id
-- WHERE s.language = 'tsz'
-- GROUP BY s.sentence_id, s.text, s.language, s.dialect, s.quality_status, 
--          d.document_identifier, src.source_name;

-- -- View for quality metrics dashboard
-- CREATE VIEW v_quality_metrics_dashboard AS
-- SELECT
--     pr.run_name,
--     pr.pipeline_type,
--     pr.started_at,
--     pr.completed_at,
--     pr.status,
--     pr.items_processed,
--     pr.items_succeeded,
--     pr.items_failed,
--     COUNT(aqm.metric_id) as metrics_computed,
--     AVG(aqm.alignment_accuracy) as avg_alignment_accuracy,
--     AVG(aqm.bleu_score) as avg_bleu_score,
--     AVG(aqm.processing_time_ms) as avg_processing_time_ms,
--     SUM(aqm.corpus_size_tokens) as total_corpus_tokens
-- FROM pipeline_runs pr
-- LEFT JOIN alignment_quality_metrics aqm ON pr.run_id = aqm.pipeline_run_id
-- GROUP BY pr.run_id, pr.run_name, pr.pipeline_type, pr.started_at, 
--          pr.completed_at, pr.status, pr.items_processed, 
--          pr.items_succeeded, pr.items_failed;

-- -- View for annotation workflow status
-- CREATE VIEW v_annotation_workflow_status AS
-- SELECT
--     at.task_id,
--     at.task_type,
--     at.assigned_to,
--     at.status,
--     at.progress,
--     at.priority,
--     COUNT(ad.decision_id) as decisions_made,
--     at.created_at,
--     at.started_at,
--     at.completed_at,
--     CASE 
--         WHEN at.completed_at IS NOT NULL THEN
--             EXTRACT(EPOCH FROM (at.completed_at - at.started_at))/3600
--         WHEN at.started_at IS NOT NULL THEN
--             EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - at.started_at))/3600
--         ELSE NULL
--     END as hours_elapsed
-- FROM annotation_tasks at
-- LEFT JOIN annotation_decisions ad ON at.task_id = ad.task_id
-- GROUP BY at.task_id, at.task_type, at.assigned_to, at.status, at.progress,
--          at.priority, at.created_at, at.started_at, at.completed_at;

-- -- ============================================================================
-- -- UTILITY FUNCTIONS
-- -- ============================================================================

-- -- Function to create a new sentence pair alignment
-- CREATE OR REPLACE FUNCTION create_sentence_alignment(
--     p_purepecha_text TEXT,
--     p_spanish_text TEXT,
--     p_document_id_pur UUID,
--     p_document_id_spa UUID,
--     p_sentence_order INT,
--     p_alignment_method alignment_method,
--     p_alignment_score DECIMAL DEFAULT NULL,
--     p_word_alignments JSONB DEFAULT NULL
-- )
-- RETURNS UUID AS $$
-- DECLARE
--     v_pur_sentence_id UUID;
--     v_spa_sentence_id UUID;
--     v_alignment_id UUID;
-- BEGIN
--     -- Insert Purépecha sentence
--     INSERT INTO sentences (document_id, sentence_order, language, text)
--     VALUES (p_document_id_pur, p_sentence_order, 'tsz', p_purepecha_text)
--     RETURNING sentence_id INTO v_pur_sentence_id;
    
--     -- Insert Spanish sentence
--     INSERT INTO sentences (document_id, sentence_order, language, text)
--     VALUES (p_document_id_spa, p_sentence_order, 'es', p_spanish_text)
--     RETURNING sentence_id INTO v_spa_sentence_id;
    
--     -- Create alignment
--     INSERT INTO alignments (
--         purepecha_sentence_id,
--         spanish_sentence_id,
--         alignment_method,
--         alignment_score,
--         word_alignments
--     )
--     VALUES (
--         v_pur_sentence_id,
--         v_spa_sentence_id,
--         p_alignment_method,
--         p_alignment_score,
--         p_word_alignments
--     )
--     RETURNING alignment_id INTO v_alignment_id;
    
--     RETURN v_alignment_id;
-- END;
-- $$ LANGUAGE plpgsql;

-- -- Function to search sentences with full-text search
-- CREATE OR REPLACE FUNCTION search_sentences(
--     p_search_query TEXT,
--     p_language language_code DEFAULT NULL,
--     p_limit INTEGER DEFAULT 100
-- )
-- RETURNS TABLE (
--     sentence_id UUID,
--     text TEXT,
--     language language_code,
--     similarity REAL,
--     document_identifier VARCHAR
-- ) AS $$
-- BEGIN
--     RETURN QUERY
--     SELECT
--         s.sentence_id,
--         s.text,
--         s.language,
--         ts_rank(s.text_vector, plainto_tsquery('spanish', p_search_query)) as similarity,
--         d.document_identifier
--     FROM sentences s
--     JOIN documents d ON s.document_id = d.document_id
--     WHERE
--         (p_language IS NULL OR s.language = p_language)
--         AND s.text_vector @@ plainto_tsquery('spanish', p_search_query)
--     ORDER BY similarity DESC
--     LIMIT p_limit;
-- END;
-- $$ LANGUAGE plpgsql;

-- -- ============================================================================
-- -- COMMENTS FOR DOCUMENTATION
-- -- ============================================================================

-- COMMENT ON TABLE sources IS 'Corpus data sources (JW.org, biblical translations, etc.)';
-- COMMENT ON TABLE documents IS 'Documents within sources (articles, chapters, books)';
-- COMMENT ON TABLE sentences IS 'Individual sentences in Purépecha and Spanish with morphological features';
-- COMMENT ON TABLE alignments IS 'Sentence-level alignments between Purépecha and Spanish with quality tracking';
-- COMMENT ON TABLE morphological_annotations IS 'Token-level morphological analysis for Purépecha agglutinative structures';
-- COMMENT ON TABLE pipeline_runs IS 'Tracking of automated pipeline executions';
-- COMMENT ON TABLE alignment_quality_metrics IS 'Quality metrics for alignment accuracy and corpus statistics';
-- COMMENT ON TABLE corpus_statistics IS 'Aggregated statistics for the entire corpus';
-- COMMENT ON TABLE annotation_tasks IS 'Human-in-the-loop annotation workflow tasks';
-- COMMENT ON TABLE annotation_decisions IS 'Audit trail for manual annotations and corrections';
-- COMMENT ON TABLE export_jobs IS 'Export jobs for various formats (TMX, CoNLL-U, JSON, etc.)';

-- COMMENT ON COLUMN sentences.morphemes IS 'Array of morphemes for agglutinative analysis';
-- COMMENT ON COLUMN sentences.text_vector IS 'Full-text search vector (automatically maintained)';
-- COMMENT ON COLUMN sentences.collection_location IS 'Geographic location for dialectal mapping (PostGIS)';
-- COMMENT ON COLUMN alignments.word_alignments IS 'Word-level alignment data in JSONB format';
-- COMMENT ON COLUMN alignments.version IS 'Version number for tracking manual corrections';
-- COMMENT ON COLUMN alignment_quality_metrics.alignment_accuracy IS 'Primary quality metric for alignment';

-- -- ============================================================================
-- -- INITIAL DATA SETUP
-- -- ============================================================================

-- -- Insert default sources
-- INSERT INTO sources (source_name, source_type, source_url, description) VALUES
--     ('JW.org Purépecha', 'jw_org', 'https://www.jw.org/tsz/', 'Jehovah''s Witnesses official website in Purépecha'),
--     ('JW.org Spanish', 'jw_org', 'https://www.jw.org/es/', 'Jehovah''s Witnesses official website in Spanish'),
--     ('Biblia en Purépecha', 'biblical', NULL, 'Purépecha Bible translation'),
--     ('Biblia en Español', 'biblical', NULL, 'Spanish Bible translation (Reina-Valera)');

-- -- ============================================================================
-- -- GRANTS (Adjust according to your user roles)
-- -- ============================================================================

-- -- Example: Grant permissions to application role
-- -- CREATE ROLE jatzingueni_app;
-- -- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO jatzingueni_app;
-- -- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO jatzingueni_app;
-- -- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO jatzingueni_app;

-- -- ============================================================================
-- -- END OF SCHEMA
-- -- ============================================================================

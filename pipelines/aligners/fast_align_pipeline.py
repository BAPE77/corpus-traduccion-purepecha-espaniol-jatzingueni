"""
Fast Align Pipeline for Purépecha-Spanish Sentence Alignment

This script uses fast_align to perform initial sentence-level alignment
of Purépecha-Spanish parallel text.

Usage:
    python fast_align_pipeline.py --batch-size 1000
"""

import os
import sys
import subprocess
import tempfile
from typing import List, Dict, Tuple
from datetime import datetime
from pathlib import Path

from loguru import logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_corpus_db, PipelineRunTracker, get_db_connection


class FastAlignPipeline:
    """Pipeline for sentence alignment using fast_align"""
    
    def __init__(self, fast_align_path: str = 'fast_align'):
        """
        Initialize fast_align pipeline
        
        Args:
            fast_align_path: Path to fast_align executable
        """
        self.fast_align_path = fast_align_path
        self.db = get_corpus_db()
        
        # Verify fast_align is available
        try:
            subprocess.run(
                [self.fast_align_path, '-h'],
                capture_output=True,
                check=False
            )
            logger.info(f"fast_align found: {self.fast_align_path}")
        except FileNotFoundError:
            logger.error(f"fast_align not found at {self.fast_align_path}")
            logger.error("Please install fast_align: https://github.com/clab/fast_align")
            raise
    
    def prepare_alignment_input(
        self,
        sentence_pairs: List[Dict],
        output_file: Path
    ):
        """
        Prepare input file for fast_align
        
        Format: source ||| target (one pair per line)
        
        Args:
            sentence_pairs: List of sentence pair dictionaries
            output_file: Path to output file
        """
        logger.info(f"Preparing alignment input for {len(sentence_pairs)} pairs")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for pair in sentence_pairs:
                # fast_align format: source ||| target
                line = f"{pair['purepecha_text']} ||| {pair['spanish_text']}\n"
                f.write(line)
        
        logger.info(f"  Written to {output_file}")
    
    def run_fast_align(
        self,
        input_file: Path,
        output_file: Path,
        reverse: bool = False
    ) -> bool:
        """
        Run fast_align on input file
        
        Args:
            input_file: Input file path
            output_file: Output file path
            reverse: Reverse alignment direction (target to source)
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Running fast_align (reverse={reverse})")
        
        cmd = [self.fast_align_path, '-i', str(input_file), '-d', '-o', '-v']
        
        if reverse:
            cmd.append('-r')
        
        try:
            with open(output_file, 'w') as out_f:
                result = subprocess.run(
                    cmd,
                    stdout=out_f,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True
                )
            
            logger.info(f"  ✓ fast_align completed")
            return True
        
        except subprocess.CalledProcessError as e:
            logger.error(f"fast_align failed: {e.stderr}")
            return False
    
    def parse_alignment_output(
        self,
        alignment_file: Path
    ) -> List[List[Tuple[int, int]]]:
        """
        Parse fast_align output
        
        Format: Each line contains alignments like "0-1 2-3 4-5"
        where each pair is source_idx-target_idx
        
        Args:
            alignment_file: Path to alignment output
        
        Returns:
            List of alignment lists (one per sentence pair)
        """
        alignments = []
        
        with open(alignment_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    alignments.append([])
                    continue
                
                # Parse alignment pairs
                pairs = []
                for pair in line.split():
                    src, tgt = pair.split('-')
                    pairs.append((int(src), int(tgt)))
                
                alignments.append(pairs)
        
        return alignments
    
    def calculate_alignment_score(
        self,
        alignments: List[Tuple[int, int]],
        src_length: int,
        tgt_length: int
    ) -> float:
        """
        Calculate alignment confidence score
        
        Simple heuristic based on:
        - Alignment coverage (how many words are aligned)
        - Alignment density (alignments per word)
        - Length ratio
        
        Args:
            alignments: List of (source_idx, target_idx) tuples
            src_length: Number of source tokens
            tgt_length: Number of target tokens
        
        Returns:
            Confidence score between 0 and 1
        """
        if not alignments or src_length == 0 or tgt_length == 0:
            return 0.0
        
        # Coverage: proportion of source words aligned
        aligned_src = len(set(a[0] for a in alignments))
        coverage = aligned_src / src_length
        
        # Density: alignments per source word
        density = len(alignments) / src_length
        density_score = min(density, 2.0) / 2.0  # Normalize to 0-1
        
        # Length ratio
        length_ratio = min(src_length, tgt_length) / max(src_length, tgt_length)
        
        # Combined score (weighted average)
        score = 0.5 * coverage + 0.3 * density_score + 0.2 * length_ratio
        
        return round(score, 4)
    
    def store_alignments(
        self,
        sentence_pairs: List[Dict],
        forward_alignments: List[List[Tuple[int, int]]],
        backward_alignments: List[List[Tuple[int, int]]],
        pipeline_run_id: str
    ) -> Tuple[int, int]:
        """
        Store alignments in database
        
        Args:
            sentence_pairs: List of sentence pair dictionaries
            forward_alignments: Forward alignments (src→tgt)
            backward_alignments: Backward alignments (tgt→src)
            pipeline_run_id: UUID of pipeline run
        
        Returns:
            Tuple of (successful, failed) counts
        """
        logger.info("Storing alignments in database")
        
        successful = 0
        failed = 0
        
        for pair, fwd_align, bwd_align in zip(
            sentence_pairs, forward_alignments, backward_alignments
        ):
            try:
                # Tokenize sentences (simple whitespace tokenization)
                src_tokens = pair['purepecha_text'].split()
                tgt_tokens = pair['spanish_text'].split()
                
                # Calculate alignment score
                score = self.calculate_alignment_score(
                    fwd_align, len(src_tokens), len(tgt_tokens)
                )
                
                # Prepare word alignments in JSONB format
                word_alignments = {
                    'forward': [
                        {'src_idx': src, 'tgt_idx': tgt, 'src_token': src_tokens[src], 'tgt_token': tgt_tokens[tgt]}
                        for src, tgt in fwd_align
                        if src < len(src_tokens) and tgt < len(tgt_tokens)
                    ],
                    'backward': [
                        {'src_idx': src, 'tgt_idx': tgt}
                        for tgt, src in bwd_align
                    ]
                }
                
                # Determine quality status based on score
                quality_status = 'auto_aligned' if score >= 0.7 else 'raw'
                
                # Insert alignment
                self.db.insert_alignment(
                    purepecha_sentence_id=pair['purepecha_sentence_id'],
                    spanish_sentence_id=pair['spanish_sentence_id'],
                    alignment_method='fast_align',
                    alignment_score=score,
                    word_alignments=word_alignments,
                    quality_status=quality_status
                )
                
                successful += 1
            
            except Exception as e:
                logger.error(f"Failed to store alignment: {e}")
                failed += 1
        
        logger.info(f"  ✓ Stored {successful} alignments ({failed} failed)")
        return successful, failed
    
    def run_pipeline(
        self,
        batch_size: int = 1000,
        max_batches: int = None
    ):
        """
        Run complete alignment pipeline
        
        Args:
            batch_size: Number of sentence pairs per batch
            max_batches: Maximum number of batches to process (None = all)
        """
        logger.info("Starting fast_align pipeline")
        logger.info(f"  Batch size: {batch_size}")
        
        # Start pipeline run tracking
        db_conn = get_db_connection()
        tracker = PipelineRunTracker(db_conn)
        
        run_id = tracker.start_run(
            run_name=f'fast_align - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            pipeline_type='alignment',
            configuration={
                'aligner': 'fast_align',
                'batch_size': batch_size
            }
        )
        
        logger.info(f"Pipeline run ID: {run_id}")
        
        # Process in batches
        batch_num = 0
        total_aligned = 0
        total_failed = 0
        
        while True:
            # Check if we've reached max batches
            if max_batches and batch_num >= max_batches:
                logger.info(f"Reached maximum batches ({max_batches})")
                break
            
            batch_num += 1
            logger.info(f"\nProcessing batch {batch_num}")
            
            # Get unaligned sentence pairs
            sentence_pairs = self.db.get_unaligned_sentence_pairs(limit=batch_size)
            
            if not sentence_pairs:
                logger.info("No more unaligned sentence pairs")
                break
            
            logger.info(f"  Retrieved {len(sentence_pairs)} sentence pairs")
            
            # Create temporary files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                
                input_file = temp_dir / 'input.txt'
                forward_output = temp_dir / 'forward.align'
                backward_output = temp_dir / 'backward.align'
                
                # Prepare input
                self.prepare_alignment_input(sentence_pairs, input_file)
                
                # Run forward alignment
                if not self.run_fast_align(input_file, forward_output, reverse=False):
                    logger.error("Forward alignment failed")
                    total_failed += len(sentence_pairs)
                    continue
                
                # Run backward alignment
                if not self.run_fast_align(input_file, backward_output, reverse=True):
                    logger.error("Backward alignment failed")
                    total_failed += len(sentence_pairs)
                    continue
                
                # Parse alignments
                forward_alignments = self.parse_alignment_output(forward_output)
                backward_alignments = self.parse_alignment_output(backward_output)
                
                # Store alignments
                successful, failed = self.store_alignments(
                    sentence_pairs,
                    forward_alignments,
                    backward_alignments,
                    run_id
                )
                
                total_aligned += successful
                total_failed += failed
                
                # Update progress
                tracker.update_progress(
                    items_processed=total_aligned + total_failed,
                    items_succeeded=total_aligned,
                    items_failed=total_failed
                )
        
        # Complete pipeline run
        tracker.complete_run(status='completed')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Alignment pipeline complete!")
        logger.info(f"  Batches processed: {batch_num}")
        logger.info(f"  Total aligned: {total_aligned}")
        logger.info(f"  Total failed: {total_failed}")
        logger.info(f"{'='*60}\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Align Purépecha-Spanish sentences using fast_align'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of sentence pairs per batch (default: 1000)'
    )
    parser.add_argument(
        '--max-batches',
        type=int,
        default=None,
        help='Maximum number of batches to process (default: all)'
    )
    parser.add_argument(
        '--fast-align-path',
        type=str,
        default='fast_align',
        help='Path to fast_align executable (default: fast_align)'
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
        f"logs/alignment_{datetime.now().strftime('%Y%m%d')}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
    )
    
    # Run pipeline
    pipeline = FastAlignPipeline(fast_align_path=args.fast_align_path)
    
    try:
        pipeline.run_pipeline(
            batch_size=args.batch_size,
            max_batches=args.max_batches
        )
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
    finally:
        # Close database connections
        get_db_connection().close_all_connections()


if __name__ == '__main__':
    main()

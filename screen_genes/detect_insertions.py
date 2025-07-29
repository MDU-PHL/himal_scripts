import argparse
import logging
import sys
from datetime import datetime
from Bio import SeqIO, pairwise2
from Bio.Align import substitution_matrices
from tqdm import tqdm

def setup_logging():
    """Setup logging with timestamp format"""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Detect insertions in protein sequences by comparing against a reference sequence in a specified region',
        epilog='''
Examples:
  python detect_insertions.py -r reference.fasta -i sequences.fasta -s 330 -e 340
  python detect_insertions.py --reference ref.fasta --input seqs.fasta --start 100 --end 150 --output results.tsv
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-r', '--reference', 
                       required=True,
                       help='Reference sequence file in FASTA format (contains the standard PBP3 sequence)')
    
    parser.add_argument('-i', '--input',
                       required=True, 
                       help='Input FASTA file containing sequences to analyze for insertions')
    
    parser.add_argument('-s', '--start',
                       type=int,
                       required=True,
                       help='Start position of region to analyze (1-based inclusive)')
    
    parser.add_argument('-e', '--end',
                       type=int, 
                       required=True,
                       help='End position of region to analyze (1-based inclusive)')
    
    parser.add_argument('-o', '--output',
                       help='Output file for results (default: stdout)')
    
    parser.add_argument('--gap-open',
                       type=float,
                       default=-10,
                       help='Gap opening penalty for alignment (default: -10)')
    
    parser.add_argument('--gap-extend', 
                       type=float,
                       default=-0.5,
                       help='Gap extension penalty for alignment (default: -0.5)')
    
    return parser.parse_args()

def main():
    setup_logging()
    args = parse_arguments()
    
    logging.info(f"Starting insertion detection analysis")
    logging.info(f"Reference file: {args.reference}")
    logging.info(f"Input file: {args.input}")
    logging.info(f"Analysis region: {args.start}-{args.end}")
    
    # Load reference sequence
    try:
        reference = SeqIO.read(args.reference, "fasta").seq
        logging.info(f"Loaded reference sequence of length {len(reference)}")
    except Exception as e:
        logging.error(f"Error loading reference file: {e}")
        sys.exit(1)
    
    # Validate region boundaries
    if args.start < 1 or args.end > len(reference) or args.start > args.end:
        logging.error(f"Invalid region: {args.start}-{args.end} for sequence of length {len(reference)}")
        sys.exit(1)
    
    # Extract reference segment
    ref_segment = reference[args.start-1:args.end]
    logging.info(f"Reference segment ({args.start}-{args.end}): {ref_segment}")
    
    # Load alignment matrix
    matrix = substitution_matrices.load("BLOSUM62")
    logging.info("Loaded BLOSUM62 substitution matrix")
    
    results = []
    sequences_processed = 0
    
    # Count total sequences for progress bar
    try:
        total_sequences = sum(1 for _ in SeqIO.parse(args.input, "fasta"))
        logging.info(f"Found {total_sequences} sequences to process")
    except Exception as e:
        logging.error(f"Error counting sequences in input file: {e}")
        sys.exit(1)
    
    # Process input sequences
    try:
        with tqdm(total=total_sequences, desc="Processing sequences", unit="seq") as pbar:
            for rec in SeqIO.parse(args.input, "fasta"):
                sequences_processed += 1
                seq = rec.seq
                
                # Update progress bar description with current sequence
                pbar.set_postfix({"Current": rec.id[:20] + "..." if len(rec.id) > 20 else rec.id})
                
                # Perform global alignment
                alignments = pairwise2.align.globalds(reference, seq, matrix, 
                                                     args.gap_open, args.gap_extend, 
                                                     one_alignment_only=True)
                if not alignments:
                    logging.warning(f"No alignment found for sequence {rec.id}")
                    pbar.update(1)
                    continue
                
                aln_ref, aln_seq, score, begin, end = alignments[0]
                
                # Locate the reference region in alignment
                ref_pos = 0
                aln_region = ""
                ref_region_aligned = ""
                
                for a_ref, a_seq in zip(aln_ref, aln_seq):
                    if a_ref != "-":
                        ref_pos += 1
                    if args.start <= ref_pos <= args.end:
                        aln_region += a_seq
                        ref_region_aligned += a_ref
                
                # Count insertions properly by looking at gaps in reference alignment
                insertion_length = ref_region_aligned.count('-')
                
                # Create alignment comparison string
                alignment_comparison = ""
                for ref_char, seq_char in zip(ref_region_aligned, aln_region):
                    if ref_char == '-':
                        alignment_comparison += 'N'  # Insertion
                    elif seq_char == '-':
                        alignment_comparison += 'D'  # Deletion
                    elif ref_char == seq_char:
                        alignment_comparison += '*'  # Match
                    else:
                        alignment_comparison += '.'  # Mismatch
                
                # Store all results (including those without insertions)
                results.append((rec.id, str(ref_segment), ref_region_aligned, aln_region, alignment_comparison, insertion_length))
                
                # Update progress bar
                pbar.update(1)
            
        logging.info(f"Processed {sequences_processed} sequences")
        
    except Exception as e:
        logging.error(f"Error processing input file: {e}")
        sys.exit(1)
    
    # Prepare output
    header = "ID\tReferenceSegment\tReferenceAligned\tQueryAligned\tAlignment\tInsertionLength"
    
    # Write results
    output_file = None
    try:
        if args.output:
            output_file = open(args.output, 'w')
            logging.info(f"Writing results to {args.output}")
        else:
            output_file = sys.stdout
            
        print(header, file=output_file)
        
        insertions_found = 0
        for rec_id, ref_seg, ref_aligned, query_aligned, alignment, ins_len in results:
            print(f"{rec_id}\t{ref_seg}\t{ref_aligned}\t{query_aligned}\t{alignment}\t{ins_len}", file=output_file)
            if ins_len > 0:
                insertions_found += 1
        
        logging.info(f"Found {insertions_found} sequences with insertions out of {len(results)} total sequences")
        
    except Exception as e:
        logging.error(f"Error writing output: {e}")
        sys.exit(1)
    finally:
        if output_file and output_file != sys.stdout:
            output_file.close()

if __name__ == "__main__":
    main()

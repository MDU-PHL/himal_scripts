import argparse
import os
import sys
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime
import re
from collections import defaultdict

def setup_logging(output_dir):
    """Setup logging with timestamp in filename and detailed format"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(output_dir, f"gene_screening_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_filename

def search_gene_in_file(isolate_data, keywords, base_path):
    """
    Search for keywords in AMRfinder output file for a single isolate
    
    Args:
        isolate_data: tuple of (ISOLATE, RUN_ID)
        keywords: list of keywords to search for
        base_path: base path for data files
    
    Returns:
        dict: Results for this isolate
    """
    isolate, run_id = isolate_data
    
    # Construct file path
    amr_file = os.path.join(base_path, run_id, isolate, "abritamr", "current", "amrfinder.out")
    
    result = {
        'isolate': isolate,
        'run_id': run_id,
        'file_exists': False,
        'hits': [],
        'gene_names': []
    }
    
    # Check if file exists
    if not os.path.exists(amr_file):
        logging.warning(f"File not found: {amr_file}")
        return result
    
    result['file_exists'] = True
    
    try:
        with open(amr_file, 'r') as f:
            header_line = f.readline().strip()  # Skip header
            
            for line_num, line in enumerate(f, 2):  # Start from line 2
                line = line.strip()
                if not line:
                    continue
                
                # Case insensitive search for any keyword
                for keyword in keywords:
                    if re.search(keyword, line, re.IGNORECASE):
                        result['hits'].append(line)
                        
                        # Extract gene name from column 6 (Gene symbol) - 0-indexed column 5
                        parts = line.split('\t')
                        if len(parts) > 5 and parts[5]:  # Gene symbol column
                            gene_name = parts[5]
                            result['gene_names'].append(gene_name)
                        break
    
    except Exception as e:
        logging.error(f"Error reading file {amr_file}: {str(e)}")
    
    return result

def process_isolates(ids_file, keywords, base_path="/home/mdu/data", num_threads=200):
    """
    Process all isolates in parallel
    
    Args:
        ids_file: path to ids_run.tab file
        keywords: list of keywords to search for
        base_path: base path for data files
        num_threads: number of threads to use
    
    Returns:
        tuple: (results_list, missing_files_list)
    """
    # Read the input file
    try:
        df = pd.read_csv(ids_file, sep='\t')
        logging.info(f"Loaded {len(df)} isolates from {ids_file}")
    except Exception as e:
        logging.error(f"Error reading {ids_file}: {str(e)}")
        return [], []
    
    # Prepare data for parallel processing
    isolate_data = [(row['ISOLATE'], row['RUN_ID']) for _, row in df.iterrows()]
    
    results = []
    missing_files = []
    
    # Progress bar setup
    with tqdm(total=len(isolate_data), desc="Processing isolates") as pbar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit all tasks
            future_to_isolate = {
                executor.submit(search_gene_in_file, data, keywords, base_path): data
                for data in isolate_data
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_isolate):
                isolate_data = future_to_isolate[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if not result['file_exists']:
                        missing_files.append(result['isolate'])
                    
                except Exception as e:
                    logging.error(f"Error processing {isolate_data}: {str(e)}")
                
                pbar.update(1)
    
    return results, missing_files

def generate_summary(results, keywords):
    """Generate summary statistics"""
    total_isolates = len(results)
    files_found = len([r for r in results if r['file_exists']])
    isolates_with_hits = len([r for r in results if r['hits']])
    
    # Gene frequency analysis
    gene_counts = defaultdict(int)
    for result in results:
        if result['gene_names']:
            for gene in result['gene_names']:
                gene_counts[gene] += 1
    
    summary = {
        'total_isolates': total_isolates,
        'files_found': files_found,
        'files_missing': total_isolates - files_found,
        'isolates_with_hits': isolates_with_hits,
        'percentage_with_hits': (isolates_with_hits / files_found * 100) if files_found > 0 else 0,
        'gene_frequencies': dict(gene_counts),
        'keywords_searched': keywords
    }
    
    return summary

def write_results(results, missing_files, summary, keywords, output_dir):
    """Write results to output files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Write missing files
    missing_file = os.path.join(output_dir, f"missing_files_{timestamp}.txt")
    with open(missing_file, 'w') as f:
        for isolate in missing_files:
            f.write(f"{isolate}\n")
    logging.info(f"Missing files written to: {missing_file}")
    
    # Write results with hits
    results_file = os.path.join(output_dir, f"gene_screening_results_{timestamp}.tsv")
    with open(results_file, 'w') as f:
        f.write("ISOLATE\tRUN_ID\tGENE_STATUS\tGENE_NAMES\tHITS_COUNT\tHITS\n")
        
        for result in results:
            if result['file_exists']:
                status = "PRESENT" if result['hits'] else "ABSENT"
                gene_names = ",".join(result['gene_names']) if result['gene_names'] else ""
                hits_count = len(result['hits'])
                hits = " ; ".join(result['hits']) if result['hits'] else ""
                
                # Wrap hits in quotes to handle tabs within the data
                hits_quoted = f'"{hits}"' if hits else ""
                
                f.write(f"{result['isolate']}\t{result['run_id']}\t{status}\t{gene_names}\t{hits_count}\t{hits_quoted}\n")
    
    logging.info(f"Results written to: {results_file}")
    
    # Write summary
    summary_file = os.path.join(output_dir, f"gene_screening_summary_{timestamp}.txt")
    with open(summary_file, 'w') as f:
        f.write("GENE SCREENING SUMMARY REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Search Keywords: {', '.join(keywords)}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("OVERALL STATISTICS:\n")
        f.write(f"Total isolates processed: {summary['total_isolates']}\n")
        f.write(f"AMR files found: {summary['files_found']}\n")
        f.write(f"AMR files missing: {summary['files_missing']}\n")
        f.write(f"Isolates with gene hits: {summary['isolates_with_hits']}\n")
        f.write(f"Percentage with hits: {summary['percentage_with_hits']:.2f}%\n\n")
        
        if summary['gene_frequencies']:
            f.write("GENE FREQUENCIES:\n")
            for gene, count in sorted(summary['gene_frequencies'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / summary['files_found'] * 100) if summary['files_found'] > 0 else 0
                f.write(f"{gene}: {count} isolates ({percentage:.2f}%)\n")
    
    logging.info(f"Summary written to: {summary_file}")
    
    return results_file, summary_file, missing_file

def main():
    parser = argparse.ArgumentParser(
        description="Screen AMRfinder output files for specific gene keywords across multiple isolates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i ids_run.tab -k fimbria -o results/
  %(prog)s --input-file ids_run.tab --keywords fimbria pili --threads 100 --output-dir ./output/
  %(prog)s -i ids_run.tab -k fimbria --base-path /custom/path/data -o results/
        """
    )
    
    parser.add_argument(
        '-i', '--input-file',
        required=True,
        help='Input file (ids_run.tab) containing ISOLATE and RUN_ID columns'
    )
    
    parser.add_argument(
        '-k', '--keywords',
        nargs='+',
        required=True,
        help='Keywords to search for (case insensitive). Can specify multiple keywords separated by spaces'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        default='.',
        help='Output directory for all result files (default: current directory)'
    )
    
    parser.add_argument(
        '-b', '--base-path',
        default='/home/mdu/data',
        help='Base path for data files (default: /home/mdu/data)'
    )
    
    parser.add_argument(
        '-t', '--threads',
        type=int,
        default=200,
        help='Number of threads for parallel processing (default: 200)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Gene Screening Tool v1.1'
    )
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Setup logging
    log_file = setup_logging(args.output_dir)
    logging.info("=" * 60)
    logging.info("GENE SCREENING ANALYSIS STARTED")
    logging.info("=" * 60)
    logging.info(f"Input file: {args.input_file}")
    logging.info(f"Keywords: {args.keywords}")
    logging.info(f"Base path: {args.base_path}")
    logging.info(f"Output directory: {args.output_dir}")
    logging.info(f"Threads: {args.threads}")
    logging.info(f"Log file: {log_file}")
    
    # Validate input file
    if not os.path.exists(args.input_file):
        logging.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    
    # Process isolates
    logging.info("Starting parallel processing...")
    results, missing_files = process_isolates(
        args.input_file, 
        args.keywords, 
        args.base_path, 
        args.threads
    )
    
    # Generate summary
    logging.info("Generating summary statistics...")
    summary = generate_summary(results, args.keywords)
    
    # Write output files
    logging.info("Writing output files...")
    results_file, summary_file, missing_file = write_results(results, missing_files, summary, args.keywords, args.output_dir)
    
    # Final summary
    logging.info("=" * 60)
    logging.info("ANALYSIS COMPLETED")
    logging.info("=" * 60)
    logging.info(f"Total isolates: {summary['total_isolates']}")
    logging.info(f"Files found: {summary['files_found']}")
    logging.info(f"Files missing: {summary['files_missing']}")
    logging.info(f"Isolates with hits: {summary['isolates_with_hits']} ({summary['percentage_with_hits']:.2f}%)")
    logging.info(f"Results file: {results_file}")
    logging.info(f"Summary file: {summary_file}")
    logging.info(f"Missing files: {missing_file}")
    logging.info("Analysis completed successfully!")

if __name__ == "__main__":
    main()
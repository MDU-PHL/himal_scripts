import os
import subprocess
import argparse
from multiprocessing import Pool
import math
import time
from datetime import datetime
from tqdm import tqdm

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_screening(chunk_info):
    chunk_file, chunk_id, query_file, identity, coverage = chunk_info
    output_dir = f"results_chunk_{chunk_id}"
    
    cmd = [
        "python", "screen_genes6.py",
        "--query", query_file,
        "--contigs", chunk_file,
        "--output", output_dir,
        "--identity", str(identity),
        "--coverage", str(coverage),
        "--force",
        "--force_db"
    ]
    
    start_time = time.time()
    log_message(f"Starting screen_genes6.py on chunk {chunk_id} (file: {chunk_file})")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            log_message(f"Completed chunk {chunk_id} successfully in {duration:.2f} seconds")
        else:
            log_message(f"ERROR: Chunk {chunk_id} failed with return code {result.returncode}")
            log_message(f"STDERR: {result.stderr}")
    except Exception as e:
        log_message(f"EXCEPTION: Chunk {chunk_id} failed with error: {str(e)}")
    
    return chunk_id

def split_contigs_file(input_file, chunk_size=1000):
    chunk_files = []
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    num_chunks = math.ceil(len(lines) / chunk_size)
    
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, len(lines))
        
        chunk_filename = f"contigs_chunk_{i:03d}.tab"
        with open(chunk_filename, 'w') as chunk_file:
            chunk_file.writelines(lines[start_idx:end_idx])
        
        chunk_files.append((chunk_filename, i))
    
    return chunk_files

def main():
    parser = argparse.ArgumentParser(
        description="Parallel processing wrapper for screen_genes6.py - splits contigs file into chunks and runs TBLASTN pipeline in parallel.",
        epilog="""
        Example Usage:
        python parallel_screen.py --query query.fasta --contigs contigs.tab --output results_dir --processes 20 --chunk_size 1000 --identity 90 --coverage 90
        python parallel_screen.py -q query.fasta -c contigs.tab -o results_dir -p 10 -s 500 -i 95 -v 85
        """,
        add_help=True
    )
    parser.add_argument("-q", "--query", required=True, help="Query sequence file (multi-FASTA format) containing protein sequences.")
    parser.add_argument("-c", "--contigs", required=True, help="Tab-separated file with contig ID in column 1 and file path in column 2.")
    parser.add_argument("-o", "--output", help="Main output directory prefix for results (default: uses screen_genes6.py default behavior).")
    parser.add_argument("-p", "--processes", type=int, default=20, help="Number of parallel processes to run (default: 20).")
    parser.add_argument("-s", "--chunk_size", type=int, default=1000, help="Number of lines per chunk when splitting contigs file (default: 1000).")
    parser.add_argument("-i", "--identity", type=float, default=90.0, help="Identity threshold for BLAST results (default: 90.0).")
    parser.add_argument("-v", "--coverage", type=float, default=90.0, help="Coverage threshold for BLAST results (default: 90.0).")
    
    args = parser.parse_args()
    
    start_time = time.time()
    log_message(f"Starting screen_genes6.py on {args.contigs}")
    log_message(f"Configuration: processes={args.processes}, chunk_size={args.chunk_size}, identity={args.identity}, coverage={args.coverage}")
    
    # Split the contigs file
    log_message(f"Splitting {args.contigs} into chunks of {args.chunk_size} lines")
    chunk_files = split_contigs_file(args.contigs, args.chunk_size)
    log_message(f"Created {len(chunk_files)} chunks for parallel processing")
    
    # Prepare arguments for parallel processing
    chunk_args = [
        (chunk_file, chunk_id, args.query, args.identity, args.coverage)
        for chunk_file, chunk_id in chunk_files
    ]
    
    # Run in parallel with progress bar
    log_message(f"Starting parallel execution with {args.processes} processes")
    log_message(f"Processing {len(chunk_files)} chunks...")
    
    completed_chunks = []
    with Pool(processes=args.processes) as pool:
        with tqdm(total=len(chunk_files), desc="Processing chunks", unit="chunk") as pbar:
            for result in pool.imap(run_screening, chunk_args):
                completed_chunks.append(result)
                pbar.update(1)
                
                # Calculate ETA
                elapsed_time = time.time() - start_time
                if len(completed_chunks) > 0:
                    avg_time_per_chunk = elapsed_time / len(completed_chunks)
                    remaining_chunks = len(chunk_files) - len(completed_chunks)
                    eta_seconds = remaining_chunks * avg_time_per_chunk
                    eta_formatted = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))
                    pbar.set_postfix(ETA=eta_formatted)
    
    total_time = time.time() - start_time
    log_message(f"All {len(chunk_files)} chunks completed successfully!")
    log_message(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    log_message(f"Average time per chunk: {total_time/len(chunk_files):.2f} seconds")
    
    # Cleanup chunk files
    log_message("Cleaning up temporary chunk files...")
    for chunk_file, _ in chunk_files:
        try:
            os.remove(chunk_file)
        except OSError:
            log_message(f"Warning: Could not remove {chunk_file}")
    
    log_message("Parallel screening completed successfully!")

if __name__ == "__main__":
    main()
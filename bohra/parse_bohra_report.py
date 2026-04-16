#!/usr/bin/env python3
"""
Parse BOHRA reports to extract SNP distance and core genome alignment statistics.
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import statistics


def setup_logging():
    """Configure logging with custom format."""
    log_format = '[%(asctime)s] - %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def parse_core_genome_stats(core_genome_file: Path) -> Dict[str, float]:
    """
    Parse core genome statistics file and calculate alignment summary.
    
    Args:
        core_genome_file: Path to core_genome.txt file
        
    Returns:
        Dictionary with min, max, and avg alignment percentages
    """
    logging.info(f"Parsing core genome stats from: {core_genome_file}")
    
    if not core_genome_file.exists():
        logging.error(f"Core genome file not found: {core_genome_file}")
        raise FileNotFoundError(f"File not found: {core_genome_file}")
    
    alignment_percentages = []
    
    try:
        with open(core_genome_file, 'r') as f:
            lines = f.readlines()
            
            if len(lines) < 2:
                logging.error("Core genome file has insufficient data")
                raise ValueError("Core genome file must have header and at least one data row")
            
            # Skip header line
            for line in lines[1:]:
                if line.strip():
                    fields = line.strip().split('\t')
                    if len(fields) >= 6:
                        try:
                            pct_aligned = float(fields[6])
                            alignment_percentages.append(pct_aligned)
                        except (ValueError, IndexError) as e:
                            logging.warning(f"Could not parse alignment percentage from line: {line.strip()}")
                            continue
        
        if not alignment_percentages:
            logging.error("No valid alignment percentages found in core genome file")
            raise ValueError("No valid data found in core genome file")
        
        stats = {
            'min': min(alignment_percentages),
            'max': max(alignment_percentages),
            'avg': statistics.mean(alignment_percentages),
            'count': len(alignment_percentages)
        }
        
        logging.info(f"Parsed {stats['count']} isolates from core genome stats")
        return stats
        
    except Exception as e:
        logging.error(f"Error parsing core genome file: {e}")
        raise


def parse_distance_matrix(distance_file: Path) -> Dict[str, float]:
    """
    Parse SNP distance matrix and calculate summary statistics.
    
    Args:
        distance_file: Path to distances.tab file
        
    Returns:
        Dictionary with min, max, and avg SNP distances (excluding self and reference)
    """
    logging.info(f"Parsing distance matrix from: {distance_file}")
    
    if not distance_file.exists():
        logging.error(f"Distance file not found: {distance_file}")
        raise FileNotFoundError(f"File not found: {distance_file}")
    
    distances = []
    
    try:
        with open(distance_file, 'r') as f:
            lines = f.readlines()
            
            if len(lines) < 2:
                logging.error("Distance file has insufficient data")
                raise ValueError("Distance file must have header and at least one data row")
            
            # Parse header to get column indices
            header = lines[0].strip().split('\t')
            isolate_names = header[1:]  # Skip first column (Isolate label)
            
            # Identify reference column (case-insensitive)
            ref_column_idx = None
            for idx, name in enumerate(isolate_names):
                if name.lower() == 'reference':
                    ref_column_idx = idx + 1  # +1 because first column is isolate name
                    logging.info(f"Found reference column at index {ref_column_idx}")
                    break
            
            # Parse distance data (skip header)
            for row_idx, line in enumerate(lines[1:], start=1):
                if line.strip():
                    fields = line.strip().split('\t')
                    row_isolate = fields[0]
                    
                    # Skip reference row
                    if row_isolate.lower() == 'reference':
                        logging.debug(f"Skipping reference row")
                        continue
                    
                    # Parse distances for this row
                    for col_idx, value in enumerate(fields[1:], start=1):
                        # Skip diagonal (self-comparison)
                        if col_idx == row_idx:
                            continue
                        
                        # Skip reference column
                        if col_idx == ref_column_idx:
                            continue
                        
                        try:
                            distance = float(value)
                            distances.append(distance)
                        except ValueError:
                            logging.warning(f"Could not parse distance value: {value}")
                            continue
        
        if not distances:
            logging.error("No valid SNP distances found in distance matrix")
            raise ValueError("No valid distances found in distance matrix")
        
        # Remove duplicate comparisons (keep only upper triangle)
        # Since we're iterating through all cells, we're getting both i->j and j->i
        # For simplicity, we'll divide by 2 or just keep all for now
        unique_distances = []
        seen_pairs = set()
        
        with open(distance_file, 'r') as f:
            lines = f.readlines()
            header = lines[0].strip().split('\t')
            isolate_names = header[1:]
            
            for row_idx, line in enumerate(lines[1:]):
                if line.strip():
                    fields = line.strip().split('\t')
                    row_isolate = fields[0]
                    
                    if row_isolate.lower() == 'reference':
                        continue
                    
                    for col_idx, value in enumerate(fields[1:]):
                        col_isolate = isolate_names[col_idx]
                        
                        # Skip self-comparisons and reference
                        if row_isolate == col_isolate or col_isolate.lower() == 'reference':
                            continue
                        
                        # Create sorted pair to avoid duplicates
                        pair = tuple(sorted([row_isolate, col_isolate]))
                        
                        if pair not in seen_pairs:
                            try:
                                distance = float(value)
                                unique_distances.append(distance)
                                seen_pairs.add(pair)
                            except ValueError:
                                continue
        
        if not unique_distances:
            logging.error("No valid unique SNP distances found")
            raise ValueError("No valid unique distances found")
        
        stats = {
            'min': min(unique_distances),
            'max': max(unique_distances),
            'avg': statistics.mean(unique_distances),
            'count': len(unique_distances)
        }
        
        logging.info(f"Parsed {stats['count']} unique pairwise distances")
        return stats
        
    except Exception as e:
        logging.error(f"Error parsing distance matrix: {e}")
        raise


def process_single_report(report_dir: Path) -> Tuple[Dict, Dict]:
    """
    Process a single BOHRA report directory.
    
    Args:
        report_dir: Path to report directory
        
    Returns:
        Tuple of (core_genome_stats, distance_stats) dictionaries
    """
    logging.info(f"Processing report directory: {report_dir}")
    
    if not report_dir.exists():
        logging.error(f"Report directory does not exist: {report_dir}")
        raise FileNotFoundError(f"Directory not found: {report_dir}")
    
    if not report_dir.is_dir():
        logging.error(f"Path is not a directory: {report_dir}")
        raise ValueError(f"Not a directory: {report_dir}")
    
    core_genome_file = report_dir / "core_genome.txt"
    distance_file = report_dir / "distances.tab"
    
    core_stats = parse_core_genome_stats(core_genome_file)
    distance_stats = parse_distance_matrix(distance_file)
    
    return core_stats, distance_stats


def print_summary(report_name: str, core_stats: Dict, distance_stats: Dict):
    """
    Print formatted summary of statistics.
    
    Args:
        report_name: Name of the report
        core_stats: Core genome statistics
        distance_stats: Distance matrix statistics
    """
    print("\n" + "="*80)
    print(f"BOHRA REPORT SUMMARY: {report_name}")
    print("="*80)
    
    print("\nCore Genome Alignment Statistics:")
    print(f"  Number of isolates: {core_stats['count']}")
    print(f"  % Aligned (min):    {core_stats['min']:.2f}%")
    print(f"  % Aligned (max):    {core_stats['max']:.2f}%")
    print(f"  % Aligned (avg):    {core_stats['avg']:.2f}%")
    
    print("\nSNP Distance Statistics (excluding self and reference):")
    print(f"  Number of pairwise comparisons: {distance_stats['count']}")
    print(f"  SNP distance (min): {distance_stats['min']:.0f}")
    print(f"  SNP distance (max): {distance_stats['max']:.0f}")
    print(f"  SNP distance (avg): {distance_stats['avg']:.2f}")
    print("="*80 + "\n")


def process_multiple_reports(reports_file: Path):
    """
    Process multiple BOHRA reports from a file containing paths.
    
    Args:
        reports_file: Path to text file with one report directory path per line
    """
    logging.info(f"Processing multiple reports from file: {reports_file}")
    
    if not reports_file.exists():
        logging.error(f"Reports list file not found: {reports_file}")
        raise FileNotFoundError(f"File not found: {reports_file}")
    
    report_dirs = []
    with open(reports_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):  # Skip empty lines and comments
                report_dirs.append(Path(line))
    
    if not report_dirs:
        logging.error("No report directories found in input file")
        raise ValueError("No valid report directories in input file")
    
    logging.info(f"Found {len(report_dirs)} report directories to process")
    
    all_core_stats = []
    all_distance_stats = []
    
    for idx, report_dir in enumerate(report_dirs, 1):
        try:
            logging.info(f"Processing report {idx}/{len(report_dirs)}")
            core_stats, distance_stats = process_single_report(report_dir)
            print_summary(report_dir.name, core_stats, distance_stats)
            
            all_core_stats.append(core_stats)
            all_distance_stats.append(distance_stats)
            
        except Exception as e:
            logging.error(f"Failed to process {report_dir}: {e}")
            continue
    
    if not all_core_stats:
        logging.error("No reports were successfully processed")
        return
    
    # Calculate combined statistics
    logging.info("Calculating combined statistics across all reports")
    
    combined_core = {
        'min': min(s['min'] for s in all_core_stats),
        'max': max(s['max'] for s in all_core_stats),
        'avg': statistics.mean([s['avg'] for s in all_core_stats]),
        'total_isolates': sum(s['count'] for s in all_core_stats)
    }
    
    combined_distance = {
        'min': min(s['min'] for s in all_distance_stats),
        'max': max(s['max'] for s in all_distance_stats),
        'avg': statistics.mean([s['avg'] for s in all_distance_stats]),
        'total_comparisons': sum(s['count'] for s in all_distance_stats)
    }
    
    print("\n" + "="*80)
    print("COMBINED SUMMARY ACROSS ALL REPORTS")
    print("="*80)
    print(f"\nNumber of reports processed: {len(all_core_stats)}")
    
    print("\nCombined Core Genome Alignment Statistics:")
    print(f"  Total isolates:     {combined_core['total_isolates']}")
    print(f"  % Aligned (min):    {combined_core['min']:.2f}%")
    print(f"  % Aligned (max):    {combined_core['max']:.2f}%")
    print(f"  % Aligned (avg):    {combined_core['avg']:.2f}%")
    
    print("\nCombined SNP Distance Statistics:")
    print(f"  Total pairwise comparisons: {combined_distance['total_comparisons']}")
    print(f"  SNP distance (min): {combined_distance['min']:.0f}")
    print(f"  SNP distance (max): {combined_distance['max']:.0f}")
    print(f"  SNP distance (avg): {combined_distance['avg']:.2f}")
    print("="*80 + "\n")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Parse BOHRA reports to extract SNP distance and core genome alignment statistics.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single report directory
  %(prog)s --report-dir /path/to/bohra/report

  # Process multiple reports from a list file
  %(prog)s --multiple-reports reports_list.txt

  # Using abbreviated arguments
  %(prog)s -r ./my_report
  %(prog)s -m ./my_reports.txt

Input Files:
  The report directory should contain:
    - distances.tab: SNP distance matrix
    - core_genome.txt: Core genome alignment statistics

  For multiple reports, provide a text file with one report directory path per line.
  Lines starting with '#' are treated as comments and ignored.

Output:
  The script prints summary statistics including:
    - Core genome alignment: min, max, avg %% aligned
    - SNP distances: min, max, avg (excluding self-comparisons and reference)
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-r', '--report-dir',
        type=Path,
        metavar='PATH',
        help='Path to single BOHRA report directory containing distances.tab and core_genome.txt'
    )
    group.add_argument(
        '-m', '--multiple-reports',
        type=Path,
        metavar='FILE',
        help='Path to text file containing list of report directories (one path per line)'
    )
    
    args = parser.parse_args()
    
    setup_logging()
    
    logging.info("Starting BOHRA report parser")
    
    try:
        if args.report_dir:
            # Process single report
            core_stats, distance_stats = process_single_report(args.report_dir)
            print_summary(args.report_dir.name, core_stats, distance_stats)
            logging.info("Successfully completed processing")
            
        elif args.multiple_reports:
            # Process multiple reports
            process_multiple_reports(args.multiple_reports)
            logging.info("Successfully completed processing all reports")
        
        return 0
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

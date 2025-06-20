#!/usr/bin/env python3
"""
Script to generate a markdown summary of Qualimap results with links to HTML reports.

This script:
1. Scans a directory for Qualimap report directories
2. Extracts stats from reports
3. Merges data with metadata from mdu_search.tab
4. Generates a markdown file with a summary table and links
5. Converts the markdown to a styled HTML report

Usage:
    python generate_qualimap_summary.py -i /path/to/html/reports -o /path/to/output/directory
"""

import os
import sys
import json
import glob
import argparse
import markdown
import datetime
import csv
import re
from pathlib import Path

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a summary markdown file with links to Qualimap HTML reports",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-i", "--input-dir", 
        required=True,
        help="Directory containing Qualimap report directories"
    )
    
    parser.add_argument(
        "-o", "--output-dir", 
        required=True,
        help="Directory to save the summary markdown and HTML files"
    )
    
    parser.add_argument(
        "-u", "--base-url",
        default="",
        help="Base URL for the HTML report links (optional)"
    )
    
    parser.add_argument(
        "-m", "--metadata-file",
        help="Path to mdu_search.tab file with metadata"
    )
    
    parser.add_argument(
        "-v", "--qualimap-version",
        help="Qualimap version used for processing"
    )
    
    return parser.parse_args()

def read_metadata(metadata_file):
    """Read metadata from mdu_search.tab file."""
    metadata = {}
    
    if not metadata_file or not os.path.exists(metadata_file):
        return metadata
        
    try:
        with open(metadata_file, 'r') as f:
            reader = csv.reader(f, delimiter='\t')
            headers = next(reader)  # Read header row
            
            # Find indices of required columns
            isolate_idx = headers.index('ISOLATE') if 'ISOLATE' in headers else None
            species_idx = headers.index('SPECIES') if 'SPECIES' in headers else None
            run_id_idx = headers.index('RUN_ID') if 'RUN_ID' in headers else None
            qc_idx = headers.index('QC') if 'QC' in headers else None
            
            # Read data rows
            for row in reader:
                if isolate_idx is not None and len(row) > max(filter(None, [isolate_idx, species_idx, run_id_idx, qc_idx])):
                    isolate = row[isolate_idx]
                    metadata[isolate] = {
                        'SPECIES': row[species_idx] if species_idx is not None else 'N/A',
                        'RUN_ID': row[run_id_idx] if run_id_idx is not None else 'N/A',
                        'QC': row[qc_idx] if qc_idx is not None else 'N/A'
                    }
    except Exception as e:
        print(f"Error reading metadata file: {e}")
    
    return metadata

def extract_stats_from_qualimap(report_dir):
    """Extract basic statistics from Qualimap genome_results.txt file."""
    stats = {}
    
    # Path to genome_results.txt file
    results_file = os.path.join(report_dir, "genome_results.txt")
    
    if not os.path.exists(results_file):
        return stats
    
    try:
        with open(results_file, 'r') as f:
            content = f.read()
            
            # Extract key statistics using regex
            mapping_rate_match = re.search(r'number of mapped reads = ([0-9,]+)', content)
            if mapping_rate_match:
                stats['mapped_reads'] = mapping_rate_match.group(1)
            
            coverage_match = re.search(r'mean coverageData = ([0-9.]+)X', content)
            if coverage_match:
                stats['mean_coverage'] = coverage_match.group(1)
                
            gc_match = re.search(r'GC percentage = ([0-9.]+)%', content)
            if gc_match:
                stats['gc_percentage'] = gc_match.group(1)
    
    except Exception as e:
        print(f"Error extracting stats from {results_file}: {e}")
    
    return stats

def generate_summary(input_dir, output_dir, base_url="", metadata_file=None, qualimap_version=None):
    """Generate summary markdown and HTML files."""
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Read metadata if provided
    metadata = read_metadata(metadata_file) if metadata_file else {}
    
    # Set up the markdown content
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_content = f"""# Qualimap BAM QC Summary
    
*Generated on: {current_date}*

## Overview

This report summarizes the Qualimap BAM QC results for the variant calling alignments (snps.bam files).
"""

    # Add qualimap version if provided
    if qualimap_version:
        md_content += f"""
### Tool Information
- **Qualimap Version:** {qualimap_version}
- **Run Date:** {current_date}
"""

    md_content += """
## Sample Reports

Click on each sample below to view the detailed Qualimap report:

| Sample ID | Qualimap Report | SPECIES | RUN_ID | QC |
|-----------|-----------------|---------|--------|-------|
"""

    # Get all Qualimap report directories
    report_dirs = glob.glob(os.path.join(input_dir, "snps_stats_*"))
    
    # Sort directories by isolate ID
    report_dirs.sort()
    
    # Ensure base URL ends with a slash if provided
    if base_url and not base_url.endswith('/'):
        base_url += '/'
    
    # Process each directory
    for report_dir in report_dirs:
        # Extract isolate ID from directory name
        isolate_id = os.path.basename(report_dir).replace("snps_stats_", "")
        
        # Path to HTML report within the stats directory
        report_html = f"{os.path.basename(report_dir)}/qualimapReport.html"
        
        # Calculate the URL for the report
        if base_url:
            url = f"{base_url}{report_html}"
        else:
            url = report_html
        
        # Get metadata
        species = metadata.get(isolate_id, {}).get('SPECIES', 'N/A')
        run_id = metadata.get(isolate_id, {}).get('RUN_ID', 'N/A')
        qc = metadata.get(isolate_id, {}).get('QC', 'N/A')
        
        # Add row to markdown table
        md_content += f"| {isolate_id} | [Report]({url}) | {species} | {run_id} | {qc} |\n"
    
    # Add footer
    md_content += """
## Summary

This report includes Qualimap BAM QC results for all samples processed in the workflow.
Qualimap provides quality control metrics for aligned reads in BAM files.
"""
    
    # Write markdown file
    md_file = os.path.join(output_dir, "qualimap_summary.md")
    with open(md_file, "w") as f:
        f.write(md_content)
    
    # Convert to HTML
    html_content = markdown.markdown(md_content, extensions=['tables'])
    
    # Add some CSS for better formatting
    html_styled = f'''<!DOCTYPE html>
<html>
<head>
    <title>Qualimap BAM QC Summary</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>'''
    
    # Write HTML file
    html_file = os.path.join(output_dir, "qualimap_summary.html")
    with open(html_file, "w") as f:
        f.write(html_styled)
    
    print(f"Summary markdown written to: {md_file}")
    print(f"Summary HTML written to: {html_file}")

def main():
    """Main function to run the script."""
    args = parse_arguments()
    generate_summary(
        args.input_dir, 
        args.output_dir, 
        args.base_url, 
        args.metadata_file,
        args.qualimap_version
    )

if __name__ == "__main__":
    main()
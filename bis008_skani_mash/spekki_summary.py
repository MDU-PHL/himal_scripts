#!/usr/bin/env python3
import argparse
import csv
import os
import logging

def setup_logging():
    """Setup logging to spekki_summary.log"""
    logging.basicConfig(
        filename='spekki_summary.log',
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        filemode='w'
    )

def read_ids_file(filepath):
    """Read the IDs and RUN IDs from input file"""
    isolates = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    isolates.append((parts[0], parts[1]))
    return isolates

def extract_spekki_data(runid, mdu_id):
    """Extract data from spekki.tab file"""
    spekki_path = f"/home/mdu/data/{runid}/{mdu_id}/spekki/current/spekki.tab"
    logging.info(f"Checking spekki file: {spekki_path}")
    
    if not os.path.exists(spekki_path):
        logging.warning(f"Spekki file not found: {spekki_path}")
        return None
    
    with open(spekki_path, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row.get('ID') == mdu_id:
                return {
                    'SPEKKI': row.get('SPEKKI', ''),
                    'Pluspf_Species': row.get('Pluspf_Species', ''),
                    'Pluspf_Unclassified_Rate': row.get('Pluspf_Unclassified_Rate', ''),
                    'GTDB_Species': row.get('GTDB_Species', ''),
                    'GTDB_Unclassified_Rate': row.get('GTDB_Unclassified_Rate', '')
                }
    return None

def extract_kraken_rate(kraken_path, species_name):
    """Extract classification rate from kraken2 report"""
    logging.info(f"Checking kraken file: {kraken_path}")
    
    if not os.path.exists(kraken_path):
        logging.warning(f"Kraken file not found: {kraken_path}")
        return ""
    
    with open(kraken_path, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) > 0 and species_name in line:
                return f"{parts[0]}/100"
    return ""

def process_isolates(input_file):
    """Main processing function"""
    isolates = read_ids_file(input_file)
    results = []
    
    for mdu_id, runid in isolates:
        logging.info(f"Processing isolate: {mdu_id}, Run: {runid}")
        
        # Extract spekki data
        spekki_data = extract_spekki_data(runid, mdu_id)
        if not spekki_data:
            logging.warning(f"No spekki data found for {mdu_id}")
            continue
        
        # Extract kraken rates
        pluspf_kraken_path = f"/home/mdu/data/{runid}/{mdu_id}/species/pluspf/kraken2.tab"
        gtdb_kraken_path = f"/home/mdu/data/{runid}/{mdu_id}/species/kraken2_gtdb/kraken2.tab"
        
        pluspf_rate = extract_kraken_rate(pluspf_kraken_path, spekki_data['Pluspf_Species'])
        gtdb_rate = extract_kraken_rate(gtdb_kraken_path, spekki_data['GTDB_Species'])
        
        result = {
            'MDU_ID': mdu_id,
            'SPEKKI': spekki_data['SPEKKI'],
            'Pluspf_Species': spekki_data['Pluspf_Species'],
            'Pluspf_Classified_Rate': pluspf_rate,
            'Pluspf_Unclassified_Rate': spekki_data['Pluspf_Unclassified_Rate'],
            'GTDB_Species': spekki_data['GTDB_Species'],
            'GTDB_Classified_Rate': gtdb_rate,
            'GTDB_Unclassified_Rate': spekki_data['GTDB_Unclassified_Rate']
        }
        results.append(result)
    
    return results

def write_output(results):
    """Write results to CSV file"""
    fieldnames = [
        'MDU_ID', 'SPEKKI', 'Pluspf_Species', 'Pluspf_Classified_Rate',
        'Pluspf_Unclassified_Rate', 'GTDB_Species', 'GTDB_Classified_Rate',
        'GTDB_Unclassified_Rate'
    ]
    
    with open('spekki_summary.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    logging.info(f"Output written to spekki_summary.csv with {len(results)} records")

def main():
    parser = argparse.ArgumentParser(description='Process spekki and kraken data')
    parser.add_argument('-i', '--input', required=True, 
                       help='Input file with MDU IDs and RUN IDs')
    
    args = parser.parse_args()
    
    setup_logging()
    logging.info("Starting spekki summary processing")
    
    results = process_isolates(args.input)
    write_output(results)
    
    logging.info("Processing completed")

if __name__ == '__main__':
    main()
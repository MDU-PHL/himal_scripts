#!/usr/bin/env python3
# filepath: /home/himals/3_resources/github-repos/himal_scripts/datashare/create_pathogen_combined.py
"""
Script to create pathogen_combined.tab from a LIMS data file with appropriate formatting for NCBI submission.
"""

import argparse
import csv
import sys
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create pathogen_combined.tab from LIMS data for NCBI Pathogen submission",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python create_pathogen_combined.py -i ids_lims_filtered_with_ausmduid_search.csv -p PRJNA123456 -o pathogen_combined.tab -e "env,sink,water"
        """
    )
    
    parser.add_argument(
        "-i", "--input", 
        required=True,
        help="Input CSV file with LIMS data including ausmduid and species info"
    )
    
    parser.add_argument(
        "-p", "--prjna",
        required=True,
        help="BioProject accession number (e.g., PRJNA123456)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="pathogen_combined.tab",
        help="Output tab-delimited file (default: pathogen_combined.tab)"
    )
    
    parser.add_argument(
        "-e", "--environmental-terms",
        help="Comma-separated list of terms that indicate environmental samples"
    )
    
    return parser.parse_args()

def format_date(date_str: str) -> str:
    """
    Convert various date formats to YYYY-MM-DD format.
    Handles DD/MM/YYYY and YYYY-MM-DD formats.
    Removes time component if present.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Date string in YYYY-MM-DD format
    """
    if not date_str or date_str.strip() == "-":
        return ""
    
    # Extract just the date part if time is included
    date_part = date_str.split(" ")[0]
    
    # Try different date formats
    date_formats = [
        ("%d/%m/%Y", "%Y-%m-%d"),  # DD/MM/YYYY -> YYYY-MM-DD
        ("%Y-%m-%d", "%Y-%m-%d"),  # YYYY-MM-DD -> YYYY-MM-DD (no change needed)
        ("%d-%m-%Y", "%Y-%m-%d"),  # DD-MM-YYYY -> YYYY-MM-DD
        ("%m/%d/%Y", "%Y-%m-%d"),  # MM/DD/YYYY -> YYYY-MM-DD
    ]
    
    for input_format, output_format in date_formats:
        try:
            # Parse the date with current format
            parsed_date = datetime.strptime(date_part, input_format)
            # Return in YYYY-MM-DD format
            return parsed_date.strftime(output_format)
        except ValueError:
            continue
    
    # If we get here, none of the formats worked
    print(f"Warning: Could not parse date '{date_str}': no matching format found", file=sys.stderr)
    return ""

def is_environmental_sample(row: Dict[str, str], env_terms: List[str]) -> bool:
    """
    Determine if a sample is environmental based on search terms.
    
    Args:
        row: Dictionary containing row data
        env_terms: List of terms that indicate environmental samples
        
    Returns:
        bool: True if sample is environmental, False otherwise
    """
    if not env_terms:
        return False
    
    # Fields to check for environmental terms
    fields_to_check = [
        'Samp categ', 'Spec desc', 'Spec source', 
        'Body site', 'Specimen source type'
    ]
    
    # Convert row values to lowercase for case-insensitive matching
    row_lower = {k: str(v).lower() for k, v in row.items()}
    
    # Check each field for environmental terms
    for field in fields_to_check:
        if field not in row_lower:
            continue
            
        field_value = row_lower.get(field, "")
        for term in env_terms:
            if term.lower() in field_value:
                return True
                
    return False

def process_lims_data(input_file: str, prjna: str, env_terms_str: Optional[str]) -> List[Dict[str, str]]:
    """
    Process LIMS data and convert to pathogen tab format.
    
    Args:
        input_file: Path to input CSV file
        prjna: BioProject accession number
        env_terms_str: Comma-separated list of environmental terms
    
    Returns:
        List of dictionaries with processed data
    """
    processed_entries = []
    
    # Parse environmental terms if provided
    env_terms = []
    if env_terms_str:
        env_terms = [term.strip() for term in env_terms_str.split(",") if term.strip()]
    
    with open(input_file, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            # Extract required fields
            ausmduid = row.get('ausmduid', '')
            species = row.get('SPECIES', '')
            date_coll = row.get('Date coll', '')
            st = row.get('ST', '')
            isolate = row.get('ISOLATE', '')  # Added ISOLATE field
            
            # Additional columns to keep
            samp_categ = row.get('Samp categ', '')
            pat_state = row.get('Pat state', '')
            spec_desc = row.get('Spec desc', '')
            spec_source = row.get('Spec source', '')
            body_site = row.get('Body site', '')
            specimen_source_type = row.get('Specimen source type', '')
            
            # Process the genotype value, if ST is present add add "ST" as a prefix
            genotype = f"ST{st}" if st and st != "-" else ""
            
            # Format the date
            formatted_date = format_date(date_coll)
            
            # Check if this is an environmental sample
            is_environmental = is_environmental_sample(row, env_terms)
            
            # Set appropriate values based on sample type
            if is_environmental:
                isolation_source = "environmental"
                attribute_package = "Pathogen.env"
                host = "missing"
            else:
                isolation_source = "Human"
                attribute_package = "Pathogen.cl"
                host = "Homo sapiens"
            
            # Default values for remaining fields
            sample_name = ausmduid
            sample_title = ""
            strain = ausmduid
            collected_by = "MDU-PHL"
            geo_loc_name = "Australia:Victoria"
            lat_lon = "missing"
            culture_collection = ""
            host_disease = "not collected"
            
            # Create entry dictionary with all required columns
            entry = {
                "sample_name": sample_name,
                "sample_title": sample_title,
                "bioproject_accession": prjna,
                "attribute_package": attribute_package,
                "organism": species,
                "strain": strain,
                "isolate": isolate,
                "collected_by": collected_by,
                "collection_date": formatted_date,
                "geo_loc_name": geo_loc_name,
                "isolation_source": isolation_source,
                "lat_lon": lat_lon,
                "culture_collection": culture_collection,
                "genotype": genotype,
                "host": host,
                "host_age": "",
                "host_description": "",
                "host_disease": host_disease,
                "host_disease_outcome": "",
                "host_disease_stage": "",
                "host_health_state": "",
                "host_sex": "",
                "host_subject_id": "",
                "host_tissue_sampled": "",
                "passage_history": "",
                "pathotype": "",
                "serotype": "",
                "serovar": "",
                "specimen_voucher": "",
                "subgroup": "",
                "subtype": "",
                "description": "",
                # Additional columns from original data
                "Samp categ": samp_categ,
                "Pat state": pat_state,
                "Spec desc": spec_desc,
                "Spec source": spec_source,
                "Body site": body_site,
                "Specimen source type": specimen_source_type,
                "ISOLATE": isolate
            }
            
            processed_entries.append(entry)
    
    return processed_entries

def write_pathogen_tab(entries: List[Dict[str, str]], output_file: str) -> int:
    """
    Write processed data to pathogen_combined.tab file.
    
    Args:
        entries: List of dictionaries with processed data
        output_file: Path to output tab-delimited file
    
    Returns:
        Number of entries written
    """
    if not entries:
        return 0
    
    # Define the column order
    columns = [
        "sample_name", "sample_title", "bioproject_accession", "attribute_package",
        "organism", "strain", "isolate", "collected_by", "collection_date",
        "geo_loc_name", "isolation_source", "lat_lon", "culture_collection",
        "genotype", "host", "host_age", "host_description", "host_disease",
        "host_disease_outcome", "host_disease_stage", "host_health_state",
        "host_sex", "host_subject_id", "host_tissue_sampled", "passage_history",
        "pathotype", "serotype", "serovar", "specimen_voucher", "subgroup",
        "subtype", "description",
        # Additional columns
        "Samp categ", "Pat state", "Spec desc", "Spec source", "Body site", 
        "Specimen source type", "ISOLATE"
    ]
    
    with open(output_file, 'w', newline='') as tabfile:
        writer = csv.DictWriter(tabfile, fieldnames=columns, delimiter='\t')
        writer.writeheader()
        writer.writerows(entries)
    
    return len(entries)

def main() -> int:
    """Main function to create pathogen_combined.tab."""
    args = parse_arguments()
    
    try:
        # Process LIMS data
        print(f"Processing LIMS data from: {args.input}")
        entries = process_lims_data(args.input, args.prjna, args.environmental_terms)
        
        if not entries:
            print("No entries found in the input file", file=sys.stderr)
            return 1
        
        # Print environmental classification summary
        env_count = sum(1 for entry in entries if entry["isolation_source"] == "Environmental")
        human_count = sum(1 for entry in entries if entry["isolation_source"] == "Human")
        
        print(f"Found {len(entries)} total entries")
        print(f"- Environmental samples: {env_count}")
        print(f"- Human samples: {human_count}")
        
        # Write output file
        count = write_pathogen_tab(entries, args.output)
        print(f"Successfully wrote {count} entries to {args.output}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
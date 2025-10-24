#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import glob
from pathlib import Path

__version__ = "1.0.0"

def run_mdu_search(id_value):
    """Run mdu search command for a given ID and return the result."""
    try:
        cmd = ['mdu', 'search', '-id', id_value, '--noitemcode', '--count']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Combine stdout and stderr to capture both data and log messages
        output = ""
        if result.stderr.strip():
            output += result.stderr.strip()
        if result.stdout.strip():
            if output:
                output += " | "
            output += result.stdout.strip()
        return output if output else "No output"
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return f"Error: {error_msg}"
    except FileNotFoundError:
        return "Error: 'mdu' command not found"

def run_mdu_search_to_file(id_value):
    """Run mdu search and save to file."""
    try:
        cmd = ['mdu', 'search', '-id', id_value, '--noitemcode']
        with open(f'search_{id_value}.tab', 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
        return f"Saved to search_{id_value}.tab"
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip() if e.stderr else str(e)}"
    except FileNotFoundError:
        return "Error: 'mdu' command not found"

def main():
    usage = "%(prog)s [options] idfile"
    description = (
        "Run mdu search operations for IDs supplied in a file (one ID per line).\n\n"
        "Two primary modes are available:\n"
        " - Default mode (--save-files not used): run 'mdu search --count' for each ID and print counts to stdout.\n"
        " - Save-files mode (--save-files): run 'mdu search --noitemcode' for each ID, save per-ID .tab files,\n"
        "   concatenate them into search_noitemcode_all.tab using csvtk and extract the first column to ids_new.txt.\n\n"
        "Notes:\n"
        " - This script expects the external tools 'mdu' and 'csvtk' to be available on PATH if using the\n"
        "   corresponding functionality.\n"
    )
    epilog = (
        "Examples:\n"
        "  1) Show counts for IDs in my_ids.txt:\n"
        "     %(prog)s my_ids.txt\n\n"
        "  2) Save full search results (per-ID files), concatenate and extract first column:\n"
        "     %(prog)s --save-files --verbose my_ids.txt\n\n"
        "  3) Show help and version:\n"
        "     %(prog)s -h\n"
        "     %(prog)s --version\n\n"
        "Output files created by --save-files mode:\n"
        "  - search_<ID>.tab         : per-ID raw output\n"
        "  - search_noitemcode_all.tab : concatenated table (created by csvtk)\n"
        "  - ids_new.txt             : first column extracted from the concatenation\n"
    )

    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        usage=usage,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('idfile', help='Path to file containing IDs (one per line).')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Show verbose progress information during processing.')
    parser.add_argument('--save-files', action='store_true',
                       help='Save individual search results to files and concatenate them afterward (requires csvtk).')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}',
                       help="Show program's version number and exit.")
    
    args = parser.parse_args()
    
    # Check if file exists
    id_file = Path(args.idfile)
    if not id_file.exists():
        print(f"Error: File '{args.idfile}' not found")
        sys.exit(1)
    
    # Read IDs from file
    try:
        with open(id_file, 'r') as f:
            ids = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    if not ids:
        print("No IDs found in file")
        sys.exit(1)
    
    if args.save_files:
        print(f"Running mdu search --noitemcode for {len(ids)} IDs and saving to files")
        print("-" * 60)
        
        # Process each ID and save to file
        for i, id_value in enumerate(ids, 1):
            if args.verbose:
                print(f"[{i}/{len(ids)}] Processing ID: {id_value}")
            
            result = run_mdu_search_to_file(id_value)
            print(f"ID: {id_value} | {result}")
        
        # Concatenate all files
        print("\nConcatenating all search files...")
        try:
            # Expand the glob in Python (csvtk does not receive shell-expanded globs when called without shell=True)
            search_files = sorted(glob.glob('search_*.tab'))
            if not search_files:
                print("No individual search_*.tab files found to concatenate")
            else:
                # Concatenate using csvtk by passing explicit filenames
                with open('search_noitemcode_all.tab', 'w') as out_f:
                    subprocess.run(['csvtk', '-t', 'concat'] + search_files,
                                   stdout=out_f,
                                   check=True)
                print("Created: search_noitemcode_all.tab")
                
                # Extract first column to new ids.txt
                try:
                    result = subprocess.run(
                        ['csvtk', '-t', 'cut', '-f', '1', 'search_noitemcode_all.tab'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )
                    # Remove header line (first line) and write the rest to ids_new.txt
                    lines = result.stdout.splitlines()
                    with open('ids_new.txt', 'w') as out_f:
                        if len(lines) > 1:
                            out_f.write("\n".join(lines[1:]) + "\n")
                        else:
                            # No data rows beyond header — write an empty file
                            out_f.write("")
                    print("Created: ids_new.txt with first column")
                except subprocess.CalledProcessError as e:
                    print(f"Error extracting ids: {e.stderr.strip() if e.stderr else e}")
                    raise
                
                # Remove individual search files (except the concatenated file)
                removed = 0
                for file in search_files:
                    if file != 'search_noitemcode_all.tab':
                        try:
                            os.remove(file)
                            removed += 1
                            if args.verbose:
                                print(f"Removed: {file}")
                        except OSError:
                            if args.verbose:
                                print(f"Failed to remove: {file}")
                print(f"Removed {removed} individual search files")
            
        except subprocess.CalledProcessError as e:
            print(f"Error in post-processing: {e}")
        except FileNotFoundError:
            print("Error: 'csvtk' command not found")
    
    else:
        print(f"Running mdu search --count for {len(ids)} IDs from {args.idfile}")
        print("-" * 60)
        
        # Process each ID for count
        for i, id_value in enumerate(ids, 1):
            if args.verbose:
                print(f"[{i}/{len(ids)}] Processing ID: {id_value}")
            
            result = run_mdu_search(id_value)
            print(f"ID: {id_value} | {result}")
    
    print("-" * 60)
    print("Completed")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import argparse
from Bio import Phylo
import sys

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Display phylogenetic tree in ASCII format from a tree file.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Example:\n  python ascii_tree.py -f tree.nwk\n  python ascii_tree.py --file tree.newick'
    )
    
    parser.add_argument('-f', '--file', 
                        required=True,
                        help='Input tree file')
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    try:
        # Read the tree file
        print(f"Reading tree file: {args.file}")
        tree = Phylo.read(args.file, "newick")
        
        # Draw the ASCII tree
        print("\nDisplaying ASCII tree:\n")
        Phylo.draw_ascii(tree)
        
    except FileNotFoundError:
        print(f"Error: Could not find file '{args.file}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

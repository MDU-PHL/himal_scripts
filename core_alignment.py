import argparse
import pandas as pd

def calculate_aligned_percentage(input_file, output_file):
    # Read tab-separated file
    df = pd.read_csv(input_file, sep='\s+')
    
    # Calculate %_Aligned
    df['%_Aligned'] = (df['ALIGNED'] / df['LENGTH']) * 100
    
    # Round to 2 decimal places
    df['%_Aligned'] = df['%_Aligned'].round(2)
    
    # Save to output file
    df.to_csv(output_file, sep='\t', index=False)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Calculate percentage of aligned sequences')
    parser.add_argument('-i', '--input', required=True, help='Input core.txt file')
    parser.add_argument('-o', '--output', default='core_aligned.txt', help='Output file name (default: core_aligned.txt)')
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        calculate_aligned_percentage(args.input, args.output)
        print(f"Analysis complete. Results written to {args.output}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()

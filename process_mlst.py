import click
import pandas as pd

@click.command()
@click.option('--input-file', '-i', required=True, help='Input MLST tab file (all_mlst.tab)')
@click.option('--output-file', '-o', required=True, help='Output Excel file path')
def process_mlst(input_file, output_file):
    """
    Process concatenated MLST tab file and create an Excel spreadsheet with MLST profiles. \n
    This is how your input file should look like: \n
    ----------------------------- \n
    sample1.fa        -       - \n
    sample2.fa        neisseria       1901    abcZ(109)       adk(39) aroE(170)      fumC(111)       gdh(148)        pdhC(153)       pgm(65) \n
    sampleX.fa        neisseria       1901    abcZ(109)       adk(39) aroE(170)      fumC(111)       gdh(148)        pdhC(153)       pgm(65) \n
    ----------------------------- \n
    """
    try:
        # Initialize a list to hold the data
        data = []

        # Define processing steps for overall progress
        steps = [
            ('Counting lines', 1),
            ('Reading MLST data', 3),
            ('Processing data', 2),
            ('Creating Excel file', 1)
        ]
        total_steps = sum(weight for _, weight in steps)

        with click.progressbar(length=total_steps,
                             label='Overall progress',
                             show_eta=True,
                             show_percent=True) as overall_bar:
            
            # Step 1: Count lines
            click.echo('\nCounting lines...')
            with open(input_file, 'r') as file:
                total_lines = sum(1 for _ in file)
            overall_bar.update(1)

            # Step 2: Read MLST data
            click.echo('\nReading MLST data...')
            with click.progressbar(length=total_lines,
                                 label='Reading lines',
                                 show_eta=True,
                                 show_percent=True) as file_bar:
                with open(input_file, 'r') as file:
                    for line in file:
                        row = line.strip().split('\t')
                        data.append(row)
                        file_bar.update(1)
            overall_bar.update(3)

            # Step 3: Process data
            click.echo('\nProcessing data...')
            max_columns = max(len(row) for row in data)
            headers = ['SAMPLE', 'SCHEME', 'ST'] + [f'LOCUS{i+1}' for i in range(max_columns - 3)]
            df = pd.DataFrame(data, columns=headers[:max_columns])
            overall_bar.update(2)

            # Step 4: Create Excel file
            click.echo('\nCreating Excel file...')
            df.to_excel(output_file, index=False)
            overall_bar.update(1)

        click.echo(f"\nSuccessfully created MLST spreadsheet: {output_file}")

    except Exception as e:
        click.echo(f"Error processing MLST data: {str(e)}", err=True)
        raise click.Abort()

if __name__ == '__main__':
    process_mlst()
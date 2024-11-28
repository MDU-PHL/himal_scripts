import os
import subprocess

# Path to the contigs.tab file
contigs_file = 'contigs.tab'

# Usage Documentation
"""
This Python script reads a file named `contigs.tab` which contains IDs and paths to contigs. 
For each line in the file, it executes a command to run `ngmaster` and processes the output using `sed`. 
The processed output is then saved to a specific directory.

Prerequisites:
- Python 3.x
- `ngmaster` installed and accessible from the command line
- `sed` installed and accessible from the command line
- `contigs.tab` file with the following format (no headers):
  ID1 /path/to/contig1
  ID2 /path/to/contig2
- You can used conda environment: ca /home/khhor/conda/envs/ngmaster

Script Description:
1. Reads the `contigs.tab` file line by line.
2. Splits each line into an ID and a path to the contig.
3. Creates a directory named after the ID if it does not already exist.
4. Constructs and executes a command to run `ngmaster` on the contig and processes the output using `sed`.
5. Saves the processed output to a file named `typer_ngmaster.tab` in the directory created for the ID.

How to Run the Script:
1. Ensure that the `contigs.tab` file is in the same directory as the script or update the `contigs_file` variable with the correct path.
2. Open a terminal and navigate to the directory containing the script.
3. Run the script using Python:
   python run_ngmaster.py
   

Output:
For each ID in the `contigs.tab` file, the script will:
- Create a directory named after the ID if it does not exist. 
- Run `ngmaster` on the contig file.
- Process the output using `sed`.
- Save the processed output to `typer_ngmaster.tab` in the corresponding directory.

Troubleshooting:
- Ensure that the `contigs.tab` file is correctly formatted with IDs and paths separated by spaces.
- Verify that `ngmaster` and `sed` are installed and accessible from the command line.
- Check for any error messages in the terminal to diagnose issues with command execution.
"""

# Read the file line by line
with open(contigs_file, 'r') as file:
    for line in file:
        # Split the line into ID and path
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        contig_id, contig_path = parts

        # Create the directory if it doesn't exist
        output_dir = os.path.join(os.getcwd(), contig_id)
        os.makedirs(output_dir, exist_ok=True)

        # Construct the command
        command = f"ngmaster --comments {contig_path} | sed 's/shovill.fa/{contig_id}/g' > {output_dir}/typer_ngmaster.tab"

        # Execute the command
        subprocess.run(command, shell=True)
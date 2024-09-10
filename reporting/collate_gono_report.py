import argparse
import pathlib
import subprocess
import pandas as pd
from datetime import datetime

def main():
    """
    Generate Gonorrhea surveillance results report.
    Example:
        python collate_gono_report.py 2024-08-30 himals MDU/REPORTS/Gono_reports 2024-08-23 "Himal Shrestha" path_to_cgts_file.txt
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('date', type=str, help="Date of analysis (e.g., 2024-08-30)")
    parser.add_argument('user', type=str, help="MDU Username (e.g., himals)")
    parser.add_argument('path_to_reports', type=str, help="Path to the public_html directory (e.g., MDU/REPORTS/Gono_reports) NOTE: Do not include the path leading to the public_html directory")
    parser.add_argument('last_date', type=str, help="Last date of analysis (e.g., 2024-08-23)")
    parser.add_argument('author', type=str, help="Author's name (e.g., Himal Shrestha)")
    parser.add_argument('cgts_file', type=str, help="Path to the file containing the list of cgTs")

    args = parser.parse_args()

    # Assign arguments to variables
    tdy = args.date
    user = args.user
    path_to_reports = args.path_to_reports
    last_date = args.last_date
    author = args.author
    cgts_file = args.cgts_file

    url_stub = f"https://bioinformatics.mdu.unimelb.edu.au/~{user}/{path_to_reports}/{tdy}/"
    target = f"/home/{user}/public_html/{path_to_reports}/{tdy}/"

    # Create target directory
    subprocess.run(f"mkdir -p {target}", shell=True)
    
    # Copy custom.css file
    subprocess.run(f"cp /home/himals/3_resources/github-repos/himal_scripts/reporting/custom.css {target}", shell=True)

    # Generate report content
    content = f"""---
title: "Gono surveillance results - {datetime.strptime(last_date, '%Y-%m-%d').strftime('%B %Y')}"
author: "{author}"
date: "{tdy}"
highlight-style: github
css: custom.css
---

# Report

## Methods

A *bohra* (version 2.3.7) analysis was performed on each cgMLST cluster type with the default parameters and the *gubbins* (version 2.24.1) flag to account for recombination. The reference genome was chosen based on the highest quality de novo assembly of a member of the cgMLST cluster type to minimise the impact of recombination and maximise recovery of the core genome. A *unicycler* (version 0.5.0) assembly was performed on the reads of the chosen reference isolate to create a high-quality reference genome for *bohra* analysis.

## Rules for SNP cluster naming

| Rule                                     | Category         |
| :--------------------------------------- | :--------------- |
| <10 SNPs before recombination correction | Highly related   |
| <50 SNPs before recombination correction | Possibly related |
| <50 SNPs after recombination correction  | Possibly related |
| <10 SNPs after recombination correction  | Possibly related |


## cgMLST clusters analysed

"""

    # Read the list of cgTs from the file
    with open(cgts_file, 'r') as f:
        cgts = f.read().strip().split('\n')

    results = []
    for cgt in cgts:
        results.append(generate_cgt_section(cgt, tdy, url_stub, target))

    content += '\n'.join(results)

    # Write content to summary.md
    pathlib.Path(f"{target}summary.md").write_text(content)

def generate_cgt_section(cgt, tdy, url_stub, target):
    section = f"""### {cgt}

* Bohra analysis: [Default report]({url_stub}/Gono_Vic_{tdy}_{cgt}_default.html), [Gubbins report]({url_stub}/Gono_Vic_{tdy}_{cgt}_gubbins.html)
* Distance matrix and clusters before and after recombination correction: [Spreadsheet]({url_stub}/{cgt}_{tdy}_summary_distclust.xlsx)
* Tree: 

![Phylogenetic tree]({cgt}_tree_{tdy}.png)
*The isolate(s) of interest is/are highlighted in red*  
* SNP (`50 SNP. 10 SNP`): [To be filled]    
* **Interpretation**: 

[To be filled]

"""
    # Copy files
    subprocess.run(f"cp {cgt}/Gono_Vic_{tdy}_{cgt}_default.html {target}", shell=True)
    subprocess.run(f"cp {cgt}/Gono_Vic_{tdy}_{cgt}_gubbins.html {target}", shell=True)
    subprocess.run(f"cp {cgt}/{cgt}_{tdy}_summary_distclust.xlsx {target}", shell=True)
    subprocess.run(f"cp {cgt}/reporting/{cgt}_tree_{tdy}.png {target}", shell=True)

    # Add SNP Cluster naming table
    section += generate_snp_cluster_table(cgt, tdy)

    return section

def generate_snp_cluster_table(cgt, tdy):
    # Read the clusters_final.csv file for the specific cgT
    df = pd.read_csv(f"{cgt}/clusters_final.csv")
    
    # Convert the DataFrame to a markdown table
    table = df.to_markdown(index=False)
    
    return f"""
### SNP Cluster naming for {cgt}

{table}
"""

if __name__ == "__main__":
    main()
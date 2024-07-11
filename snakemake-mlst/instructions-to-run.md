# Tutorial: Creating and Running a Snakemake Pipeline for Subsampling Reads, Assembly, and MLST Analysis

This tutorial will guide you through the process of setting up and running a Snakemake pipeline for MLST (Multi-Locus Sequence Typing) analysis. The pipeline will read input data, calculate required coverage, subsample reads, perform assembly, and run MLST analysis. The outputs will be logged for easy debugging.

## Prerequisites

Before starting, ensure you have the following installed:
- Python (with pandas and logging modules)
- Snakemake
- SeqKit
- Shovill
- MLST

## Step 1: Create the YAML files to set up conda environments

Create the required conda environment with necessary dependencies for each step of the pipeline. You can activate and export the environment as a YAML file using the following commands:

```bash
conda create -n env_name
conda activate env_name
conda install package1 package2 ...
conda env export > env_name.yml
```
* The YAML file looks as follows:

```yaml
name: bohra-shovill
channels:
  - conda-forge
  - bioconda
  - defaults
dependencies:
  - _libgcc_mutex=0.1=conda_forge
  - _openmp_mutex=4.5=2_gnu
  - _sysroot_linux-64_curr_repodata_hack=3=h69a702a_13
  - alsa-lib=1.2.3.2=h166bdaf_0
  .....
  - other packages

prefix: /home/mdu/conda/envs/bohra-shovill
```

* For this script, we will need three conda environments: `hicap_dev`, `env_shovill`, and `mlst`.
* Create the YAML files for each environment and move them to the `envs` directory.

## Step 2: Prepare Input Files

Ensure you have the following input files in the `data` directory:
- `isolates.tab`: Contains the sample IDs and read file paths.
- `coverage.tab`: Contains the sample IDs and their current coverage values.

Example format for `isolates.tab`:
```
sample_id	R1	R2
sample1	data/sample1_R1.fastq.gz	data/sample1_R2.fastq.gz
sample2	data/sample2_R1.fastq.gz	data/sample2_R2.fastq.gz
```

Example format for `coverage.tab`:
```
sample_id	COVERAGE
sample1	100
sample2	80
```

## Step 3: Write the Snakemake Pipeline Script

Save the following script as `Snakefile`:

```python
import pandas as pd
import logging

# Set up logging
logging.basicConfig(filename='pipeline.log', level=logging.INFO)

# Define the required coverage values
REQUIRED_COVERAGES = [40]

# Read the isolates.tab file
df_isolates = pd.read_csv('data/isolates.tab', sep='\t')

# Read the coverage.tab file
df_coverage = pd.read_csv('data/coverage.tab', sep='\t')

# Merge the two dataframes on sample_id
df = pd.merge(df_isolates, df_coverage, on='sample_id')

# Calculate p_values for required coverage
for cov in REQUIRED_COVERAGES:
    df[f'p_{cov}'] = round(cov / df['COVERAGE'], 2)

# Print and log the p_values
for _, row in df.iterrows():
    for cov in REQUIRED_COVERAGES:
        logging.info(f"Sample {row['sample_id']}: Required Coverage = {cov}, Current Coverage = {row['COVERAGE']}, p_value = {row[f'p_{cov}']}")
        print(f"Sample {row['sample_id']}: Required Coverage = {cov}, Current Coverage = {row['COVERAGE']}, p_value = {row[f'p_{cov}']}")

# Define sample_ids
SAMPLES = df['sample_id'].tolist()

rule all:
    input:
        expand("reads/{sample_id}_cov{cov}/{sample_id}_cov{cov}_R{R}.fastq.gz", 
               sample_id=SAMPLES, 
               R=[1, 2], 
               cov=REQUIRED_COVERAGES),
        expand("final_assemblies/{sample_id}_cov{cov}.fa", 
               sample_id=SAMPLES, 
               cov=REQUIRED_COVERAGES),
        expand("mlst_output/{sample_id}_cov{cov}_mlst.tab", 
               sample_id=SAMPLES, 
               cov=REQUIRED_COVERAGES)

# Create a dictionary mapping sample_id to R1 and R2 read files
SAMPLE_DICT = df.set_index('sample_id')[['R1', 'R2']].to_dict(orient='index')

def get_read_files(wildcards):
    read_files = SAMPLE_DICT[wildcards.sample_id]
    return read_files['R1'], read_files['R2']

rule subsample:
    input:
        get_read_files
    output:
        r1_out = "reads/{sample_id}_cov{cov}/{sample_id}_cov{cov}_R1.fastq.gz",
        r2_out = "reads/{sample_id}_cov{cov}/{sample_id}_cov{cov}_R2.fastq.gz"
    params:
        p_val = lambda wildcards: df.loc[df['sample_id'] == wildcards.sample_id, f'p_{wildcards.cov}'].values[0]
    conda:
        "envs/hicap_dev.yml"
    shell:
        """
        mkdir -p reads/{wildcards.sample_id}_cov{wildcards.cov}
        echo "Sample {wildcards.sample_id}, Cov {wildcards.cov}, p_value {params.p_val}" | tee -a pipeline.log
        seqkit sample -p {params.p_val} -o {output.r1_out} {input[0]}
        seqkit sample -p {params.p_val} -o {output.r2_out} {input[1]}
        """

rule assemble:
    input:
        r1 = "reads/{sample_id}_cov{cov}/{sample_id}_cov{cov}_R1.fastq.gz",
        r2 = "reads/{sample_id}_cov{cov}/{sample_id}_cov{cov}_R2.fastq.gz"
    output:
        "final_assemblies/{sample_id}_cov{cov}.fa"
    conda:
        "envs/env_shovill.yml"
    shell:
        """
        shovill --R1 {input.r1} --R2 {input.r2} --outdir assemblies/{wildcards.sample_id}_cov{wildcards.cov}/ --force --cpus 8 --ram 16 --minlen 500
        cp assemblies/{wildcards.sample_id}_cov{wildcards.cov}/contigs.fa final_assemblies/{wildcards.sample_id}_cov{wildcards.cov}.fa
        """

rule mlst:
    input:
        "final_assemblies/{sample_id}_cov{cov}.fa"
    output:
        "mlst_output/{sample_id}_cov{cov}_mlst.tab"
    conda:
        "envs/mlst.yml"
    shell:
        """
        mlst --quiet --blastdb /home/mdu/resources/mlst/blast/mlst.fa --datadir /home/mdu/resources/mlst/pubmlst --nopath {input} --exclude ecoli > {output}
        """
```

## Step 4: Run the Pipeline

Run the Snakemake pipeline using the following command:
1. Test the pipeline without executing the rules:
```bash
snakemake --use-conda --cores 100 -s Snakefile --rerun-incomplete -n
```
2. Execute the rules:
```bash
snakemake --use-conda --cores 100 -s Snakefile --rerun-incomplete
```

The `--use-conda` flag ensures that the specified conda environments are activated during the execution of each rule. The `--cores` flag specifies the number of CPU cores to use. The `-s` flag specifies the Snakefile to use, and the `--rerun-incomplete` flag ensures that only incomplete or failed jobs are rerun. The `-n` flag is used for a dry-run to check the execution plan without actually running the pipeline.

## Step 5: Verify the Output

After the pipeline finishes, check the following directories for outputs:
- `reads/`: Contains the subsampled reads.
- `final_assemblies/`: Contains the assembled genomes.
- `mlst_output/`: Contains the MLST results.

Check the `pipeline.log` file for the logged `p_values` and any other messages.

## Conclusion

You have successfully set up and run a Snakemake pipeline for subsampling reads, assembly, and MLST analysis. This pipeline will help automate the process. You can further customise the pipeline to include additional steps or analyses as needed as `rules` in the `Snakefile`. 

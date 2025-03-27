#!/usr/bin/env nextflow
nextflow.enable.dsl=2
version = '1.0'

// run MLST on existing genomes
// genome files are already downloaded and available at genome_pattern from nextflow.config

process RUN_MLST {
    tag { "${sample_id}" }
    
    publishDir "${params.output_dir}/mlst", mode: 'copy'
    
    conda params.mlst_conda_env
    
    cpus 1
    memory '4 GB'
    time '1 h'
    
    errorStrategy 'retry'
    maxRetries 1
    
    input:
    tuple val(sample_id), path(genome_file)

    output:
    tuple val(sample_id), path("${sample_id}_mlst.tab")

    script:
    """
    # Handle both compressed and uncompressed files
    if [[ "${genome_file}" == *.gz ]]; then
        # For compressed files
        gunzip -c ${genome_file} > input.fna
    else
        # For uncompressed files
        cp ${genome_file} input.fna
    fi
    
    # Run MLST on the prepared input file
    mlst --quiet --blastdb "${params.mlst_blastdb}" --datadir "${params.mlst_datadir}" \
         --nopath input.fna --exclude ecoli > tmp.tab
    
    # Process the output file
    sed 's/input.fna/${sample_id}/g' tmp.tab > ${sample_id}_mlst.tab
    
    # Cleanup
    rm tmp.tab input.fna
    """
}

process COMBINE_MLST_RESULTS {
    publishDir "${params.output_dir}", mode: 'copy'
    
    input:
    path(mlst_files)
    
    output:
    path("combined_mlst_results.tsv")
    
    script:
    """
    # Create header
    echo -e "sample\tscheme\tST\tloci1\tloci2\tloci3\tloci4\tloci5\tloci6\tloci7" > combined_mlst_results.tsv
    
    # Combine all files without headers
    for file in ${mlst_files}; do
        cat \$file >> combined_mlst_results.tsv
    done
    """
}

workflow {
    // Create channel from existing genome files
    genome_files = Channel
        .fromPath(params.genome_pattern)
        .map { file -> 
            // Extract sample_id from file path
            def sample_id = file.getName().tokenize('/').last()
            // Remove file extension if present
            sample_id = sample_id.replaceAll(/\.(fna|fna\.gz)$/, '')
            return tuple(sample_id, file)
        }
    
    // Run MLST on existing genomes
    mlst_results = RUN_MLST(genome_files)
    
    // Combine all MLST results
    COMBINE_MLST_RESULTS(mlst_results.map { it[1] }.collect())
}
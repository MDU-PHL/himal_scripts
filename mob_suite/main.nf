#!/usr/bin/env nextflow
nextflow.enable.dsl=2
version = '1.0'

// Define input channel from the NDM-1_abritamr_contig_info.tab file
process EXTRACT_CONTIG {
    tag { "${sample_id}-${params.gene_name}" }
    
    publishDir "${params.output_dir}/${sample_id}", mode: 'copy'
    
    conda params.bioinf_env
    
    cpus 1
    memory '4 GB'
    time '30 m'
    
    errorStrategy 'retry'
    maxRetries 1
    
    input:
    tuple val(sample_id), val(contig_id), path(contigs_path)

    output:
    tuple val(sample_id), path("${sample_id}-${params.gene_name}.fa")

    script:
    """
    seqkit grep -r -p "${contig_id}" ${contigs_path} > ${sample_id}-${params.gene_name}.fa
    """
}

process RUN_MOB_TYPER {
    tag { "${sample_id}-${params.gene_name}" }
    
    publishDir "${params.output_dir}/${sample_id}", mode: 'copy'
    
    conda params.mob_suite_env
    
    cpus 1
    memory '4 GB'
    time '1 h'
    
    errorStrategy 'retry'
    maxRetries 1
    
    input:
    tuple val(sample_id), path(fasta_file)

    output:
    tuple val(sample_id), path("${sample_id}-${params.gene_name}_mobtyper.txt")

    script:
    """
    mob_typer --infile ${fasta_file} --out_file ${sample_id}-${params.gene_name}_mobtyper.txt
    """
}

process CONCATENATE_RESULTS {
    publishDir params.output_dir, mode: 'copy'
    
    conda params.bioinf_env
    
    input:
    path(mobtyper_files)
    
    output:
    path("${params.gene_name}_mobtyper_summary.txt")
    
    script:
    """
    csvtk -t concat ${mobtyper_files} > ${params.gene_name}_mobtyper_summary.txt
    """
}

workflow {
    // Read the NDM-1_abritamr_contig_info.tab file
    contig_info = Channel
        .fromPath(params.contig_info_tab)
        .splitCsv(header: true, sep: '\t')
        .map { row -> 
            tuple(row.sample_id, row.contig_id, file(row.contigs_path))
        }

    // Extract contigs containing NDM-1
    extracted_contigs = EXTRACT_CONTIG(contig_info)
    
    // Run mob_typer on the extracted contigs
    mobtyper_results = RUN_MOB_TYPER(extracted_contigs)
    
    // Collect all mobtyper result files as a list
    mobtyper_results_files = mobtyper_results.map { it[1] }.collect()
    
    // Concatenate all result files using csvtk
    CONCATENATE_RESULTS(mobtyper_results_files)
}
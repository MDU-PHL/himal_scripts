#!/usr/bin/env nextflow

// Define the workflow for running Qualimap on BAM files

// Log workflow start
log.info """
==============================================
QUALIMAP ANALYSIS WORKFLOW
==============================================
Input data: ${params.bam_file}
Results directory: ${params.output_dir}
Public HTML directory: ${params.public_html_dir}
Conda environment: ${params.qualimap_conda_env}
==============================================
"""

// Create channel from input BAM file
Channel
    .fromPath(params.bam_file)
    .splitCsv(sep: '\t')
    .map { row -> tuple(row[0], file(row[1])) }
    .set { bam_ch }

process RUN_QUALIMAP {
    tag { "${isolate_id}" }
    
    conda params.qualimap_conda_env
    publishDir "${params.output_dir}/${isolate_id}", mode: 'copy'
    
    cpus 4
    memory '8 GB'
    time '2 h'
    
    input:
    tuple val(isolate_id), path(bam_file)
    
    output:
    tuple val(isolate_id), path("snps_stats_${isolate_id}")
    
    script:
    """
    # Run Qualimap on the BAM file
    qualimap bamqc -bam ${bam_file} -outdir snps_stats
    
    # Rename the output directory to include isolate ID
    mv snps_stats snps_stats_${isolate_id}
    """
}

process COPY_TO_PUBLIC_HTML {
    tag { "${isolate_id}" }
    
    publishDir "${params.public_html_dir}", mode: 'copy'
    
    input:
    tuple val(isolate_id), path(stats_dir)
    
    output:
    tuple val(isolate_id), path("snps_stats_${isolate_id}")
    
    script:
    """
    # Nothing to do - publishDir handles the copying
    echo "Copying ${stats_dir} to public HTML directory"
    """
}

process GENERATE_SUMMARY {
    publishDir "${params.output_dir}", mode: 'copy'
    publishDir "${params.public_html_dir}", mode: 'copy'
    
    conda params.conda_env

    input:
    path(stats_dirs)
    path(metadata_file)
    
    output:
    path("qualimap_summary.md")
    path("qualimap_summary.html")
    
    script:
    """
    # Run the generate_qualimap_summary.py script from the bin directory
    generate_qualimap_summary.py \\
        -i ${params.public_html_dir} \\
        -o . \\
        -u "${params.public_html_url}" \\
        -m "${metadata_file}" \\
        -v "${params.qualimap_version}"
    """
}

workflow {
    // Read metadata file
    metadata_file = file(params.metadata_file)
    
    // Run Qualimap on each BAM file
    qualimap_results = RUN_QUALIMAP(bam_ch)
    
    // Copy results to public HTML directory
    html_dirs = COPY_TO_PUBLIC_HTML(qualimap_results)
    
    // Collect all stats directories for summary generation
    html_dirs
        .map { isolate_id, stats_dir -> stats_dir }
        .collect()
        .set { all_stats_dirs }
    
    // Generate summary report
    GENERATE_SUMMARY(all_stats_dirs, metadata_file)
}

workflow.onComplete {
    log.info """
    ==============================================
    QUALIMAP ANALYSIS WORKFLOW - COMPLETED
    ==============================================
    Results have been saved to:
    ${params.output_dir}
    
    HTML reports have been copied to:
    ${params.public_html_dir}
    
    Summary report available at:
    ${params.public_html_dir}/qualimap_summary.html
    ==============================================
    """
}
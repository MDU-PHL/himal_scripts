#!/usr/bin/env nextflow

// Define the workflow for running fastp on multiple isolates

// Import required packages
import groovy.io.FileType
import java.nio.file.Paths

// Log workflow start
log.info """
==============================================
FASTP QUALITY CONTROL WORKFLOW
==============================================
Input data: ${params.reads_file}
Results directory: ${params.output_dir}
Public HTML directory: ${params.public_html_dir}
Conda environment: ${params.fastp_conda_env}
==============================================
"""

// Create channel from input reads file
Channel
    .fromPath(params.reads_file)
    .splitCsv(sep: '\t')
    .map { row -> tuple(row[0], file(row[1]), file(row[2])) }
    .set { reads_ch }

process RUN_FASTP {
    tag { "${isolate_id}" }
    
    conda params.fastp_conda_env
    publishDir "${params.output_dir}/${isolate_id}/fastp", mode: 'copy'
    
    cpus 8
    memory '8 GB'
    time '2 h'
    
    input:
    tuple val(isolate_id), path(r1_file), path(r2_file)
    
    output:
    tuple val(isolate_id), 
          path("${isolate_id}_R1_trimmed.fastq.gz"), 
          path("${isolate_id}_R2_trimmed.fastq.gz"),
          path("${isolate_id}.fastp.json"),
          path("${isolate_id}.fastp.html")
    
    script:
    """
    # Capture fastp version
    fastp --version > fastp_version.txt 2>&1
    
    # Run fastp with specified parameters
    fastp --in1 ${r1_file} \\
          --in2 ${r2_file} \\
          --out1 ${isolate_id}_R1_trimmed.fastq.gz \\
          --out2 ${isolate_id}_R2_trimmed.fastq.gz \\
          --json ${isolate_id}.fastp.json \\
          -h ${isolate_id}.fastp.html \\
          --thread ${task.cpus} \\
          --detect_adapter_for_pe \\
          --overrepresentation_analysis
    
    # Add version info to JSON file (for summary report later)
    FASTP_VERSION=\$(cat fastp_version.txt)
    mv ${isolate_id}.fastp.json ${isolate_id}.fastp.json.temp
    jq --arg version "\$FASTP_VERSION" '. + {"version": \$version}' ${isolate_id}.fastp.json.temp > ${isolate_id}.fastp.json
    rm ${isolate_id}.fastp.json.temp
    """
}

process COPY_TO_PUBLIC_HTML {
    tag { "${isolate_id}" }
    
    publishDir "${params.public_html_dir}", mode: 'copy', pattern: "*.html"
    
    input:
    tuple val(isolate_id), 
          path(trimmed_r1), 
          path(trimmed_r2),
          path(json_file),
          path(html_file)
    
    output:
    tuple val(isolate_id), path("${html_file}")
    
    script:
    """
    # No manual copy needed - publishDir handles it
    echo "Copying ${html_file} to public HTML directory"
    """
}

process GENERATE_SUMMARY {
    publishDir "${params.output_dir}", mode: 'copy'
    publishDir "${params.public_html_dir}", mode: 'copy'
    
    conda params.conda_env

    input:
    path(html_files)
    path(metadata_file)
    
    output:
    path("fastp_summary.md")
    path("fastp_summary.html")
    
    script:
    """
    # Create a temporary directory for the HTML files
    mkdir -p html_files
    cp *.html html_files/
    
    # Get fastp version from one of the JSON files (they all have the same version)
    FASTP_VERSION=\$(jq -r '.version' ${params.output_dir}/*/fastp/*.json | head -n 1)
    
    # Run the generate_fastp_summary.py script from the bin directory
    generate_fastp_summary.py \\
        -i html_files \\
        -o . \\
        -u "${params.public_html_url}" \\
        -j "${params.output_dir}" \\
        -m "${metadata_file}" \\
        -v "\$FASTP_VERSION"
    """
}

workflow {
    // Read metadata file
    metadata_file = file(params.metadata_file)
    
    // Run fastp on each sample
    fastp_results = RUN_FASTP(reads_ch)
    
    // Copy HTML reports to public HTML directory
    html_files = COPY_TO_PUBLIC_HTML(fastp_results)
    
    // Collect all HTML files for summary generation
    html_files
        .map { isolate_id, html_file -> html_file }
        .collect()
        .set { all_html_files }
    
    // Generate summary report
    GENERATE_SUMMARY(all_html_files, metadata_file)
}

workflow.onComplete {
    log.info """
    ==============================================
    FASTP QUALITY CONTROL WORKFLOW - COMPLETED
    ==============================================
    Results have been saved to:
    ${params.output_dir}
    
    HTML reports have been copied to:
    ${params.public_html_dir}
    
    Summary report available at:
    ${params.public_html_dir}/fastp_summary.html
    ==============================================
    """
}
import os
import argparse
import subprocess
import pandas as pd
from Bio import SeqIO
from Bio.Seq import Seq
# Author: Jake Lacey
# **Parse command-line arguments**
def parse_args():
    """Parses command-line arguments for user input and provides detailed help information."""
    parser = argparse.ArgumentParser(
        description="TBLASTN pipeline with multi-query support, extraction, clustering, and sequence mapping.",
        epilog="""
        Example Usage:
        python script.py --query query.fasta --contigs contigs.tab --output results_dir --identity 90 --coverage 90 --force --force_db
        """,
        add_help=True
    )
    parser.add_argument("-q", "--query", required=True, help="Query sequence file (multi-FASTA format) containing protein sequences.")
    parser.add_argument("-c", "--contigs", required=True, help="Tab-separated file with contig ID in column 1 and file path in column 2.")
    parser.add_argument("-o", "--output", required=True, help="Main output directory to store results.")
    parser.add_argument("-i", "--identity", type=float, default=90.0, help="Identity threshold for BLAST results (default: 90.0).")
    parser.add_argument("-v", "--coverage", type=float, default=90.0, help="Coverage threshold for BLAST results (default: 90.0).")
    parser.add_argument("--force", action="store_true", help="Force overwrite if the output directory exists.")
    parser.add_argument("--force_db", action="store_true", help="Force rebuilding of BLAST databases, even if they exist.")
    return parser.parse_args()

# **Step 1: Create BLAST databases**
def create_blast_db(contigs_file, blast_db_dir, force_db):
    """Creates BLAST databases for each contig file, rebuilding if --force_db is enabled."""
    with open(contigs_file, "r") as f:
        for line in f:
            id_name, contig_path = line.strip().split("\t")
            db_path = os.path.join(blast_db_dir, id_name)

            if not force_db and all(os.path.exists(f"{db_path}.{ext}") for ext in ["nin", "nsq", "nhr"]):
                print(f"BLAST database exists for {id_name}. Skipping.")
                continue

            if not os.path.exists(contig_path):
                print(f"⚠️ Warning: Contig file missing for {id_name}: {contig_path}")
                continue

            subprocess.run(["makeblastdb", "-in", contig_path, "-dbtype", "nucl", "-out", db_path])

# **Step 2: Perform TBLASTN searches**
def run_tblastn(contigs_file, query_file, blast_db_dir, output_dir, identity_threshold, coverage_threshold):
    """Runs TBLASTN for each query sequence and stores results separately."""
    for query_record in SeqIO.parse(query_file, "fasta"):
        query_id = query_record.id
        query_output_dir = os.path.join(output_dir, query_id)
        os.makedirs(query_output_dir, exist_ok=True)

        query_seq_file = os.path.join(query_output_dir, f"{query_id}.fa")
        with open(query_seq_file, "w") as qf:
            SeqIO.write(query_record, qf, "fasta")

        query_blast_results_dir = os.path.join(query_output_dir, "blast_results")
        os.makedirs(query_blast_results_dir, exist_ok=True)

        blast_results = []
        with open(contigs_file, "r") as f:
            for line in f:
                id_name, _ = line.strip().split("\t")
                db_path = os.path.join(blast_db_dir, id_name)
                result_path = os.path.join(query_blast_results_dir, f"{id_name}_{query_id}_tblastn_results.txt")

                if not all(os.path.exists(f"{db_path}.{ext}") for ext in ["nin", "nsq", "nhr"]):
                    continue

                subprocess.run(["tblastn", "-query", query_seq_file, "-db", db_path, "-out", result_path,
                                "-evalue", "1e-5", "-outfmt", "6 qseqid sseqid pident qcovs sstart send",
                                "-qcov_hsp_perc", str(coverage_threshold)])

                # **Read results and filter**
                with open(result_path, "r") as blast_file:
                    for line in blast_file:
                        qseqid, sseqid, pident, qcovs, sstart, send = line.strip().split("\t")
                        if float(pident) >= identity_threshold and float(qcovs) >= coverage_threshold:
                            blast_results.append((qseqid, sseqid, pident, qcovs, sstart, send))

        # **Save filtered results**
        filtered_results_file = os.path.join(query_output_dir, "filtered_tblastn_results.csv")
        if blast_results:
            pd.DataFrame(blast_results, columns=["Query", "Subject", "Identity", "Coverage", "Start", "End"]).to_csv(filtered_results_file, index=False)
            print(f"✅ Filtered results saved: {filtered_results_file}")
        else:
            print(f"⚠️ Warning: No hits found for query {query_id}, skipping extraction.")

# **Step 3: Extract, Cluster & Translate**
def process_results(contigs_file, query_output_dir, query_id):
    """Extracts, clusters, translates, and maps sequences, storing them in the query-specific directory."""
    filtered_results_file = os.path.join(query_output_dir, "filtered_tblastn_results.csv")
    extracted_hits_file = os.path.join(query_output_dir, "gene_hit_sequences.fasta")
    clustered_nucleotide_file = os.path.join(query_output_dir, "clustered_nucleotide_sequences.fasta")
    clustered_protein_file = os.path.join(query_output_dir, "clustered_protein_sequences.fasta")

    if not os.path.exists(filtered_results_file) or os.path.getsize(filtered_results_file) == 0:
        print(f"⚠️ Warning: No valid BLAST results found in {filtered_results_file}. Skipping extraction.")
        return

    # **Extract Gene Sequences**
    extracted_sequences = []
    filtered_df = pd.read_csv(filtered_results_file)

    with open(contigs_file, "r") as f:
        for line in f:
            id_name, contig_path = line.strip().split("\t")
            if not os.path.exists(contig_path):
                continue

            contig_dict = SeqIO.to_dict(SeqIO.parse(contig_path, "fasta"))

            for _, row in filtered_df.iterrows():
                subject_id = row["Subject"]
                start, end = int(row["Start"]), int(row["End"])

                if subject_id not in contig_dict:
                    continue

                contig_seq = contig_dict[subject_id].seq
                gene_seq = contig_seq[start-1:end] if start < end else contig_seq[end-1:start].reverse_complement()

                if len(gene_seq) == 0:
                    continue

                extracted_sequences.append((f">{id_name}_{subject_id}_{start}_{end}", str(gene_seq)))

    if extracted_sequences:
        with open(extracted_hits_file, "w") as out_f:
            for header, seq in extracted_sequences:
                out_f.write(f"{header}\n{seq}\n")
        print(f"✅ Extracted sequences saved: {extracted_hits_file}")

        # **Now Perform Clustering, Translation & Second Clustering**
        subprocess.run(["cd-hit", "-i", extracted_hits_file, "-o", clustered_nucleotide_file, "-c", "1.0"], check=True)

        with open(clustered_protein_file, "w") as out_f:
            for record in SeqIO.parse(clustered_nucleotide_file, "fasta"):
                protein_seq = Seq(record.seq).translate(table=11)
                out_f.write(f">{record.id}\n{protein_seq}\n")

        subprocess.run(["cd-hit", "-i", clustered_protein_file, "-o", clustered_protein_file.replace(".fasta", "_clustered.fasta"), "-c", "1.0"], check=True)

        print(f"✅ Clustering and translation completed for {query_output_dir}")

# **Step 4: Generate Final CSV with Unique Numbering**
def generate_csv(query_output_dir, query_id):
    """Generates a CSV file for each query with unique numbering for sequences."""
    extracted_hits_file = os.path.join(query_output_dir, "gene_hit_sequences.fasta")
    clustered_nucleotide_file = os.path.join(query_output_dir, "clustered_nucleotide_sequences.fasta")
    clustered_protein_file = os.path.join(query_output_dir, "clustered_protein_sequences.fasta")
    final_output_csv = os.path.join(query_output_dir, "final_clustered_results.csv")

    if not os.path.exists(extracted_hits_file) or not os.path.exists(clustered_nucleotide_file) or not os.path.exists(clustered_protein_file.replace(".fasta", "_clustered.fasta")):
        print(f"⚠️ Warning: Required clustering files missing. Skipping CSV generation for {query_id}.")
        return

    # Assign unique numbers to nucleotide and protein sequences
    nucleotide_sequences = {}
    protein_sequences = {}
    nucleotide_counter = 1
    protein_counter = 1

    for record in SeqIO.parse(clustered_nucleotide_file, "fasta"):
        seq_str = str(record.seq)
        if seq_str not in nucleotide_sequences:
            nucleotide_sequences[seq_str] = f"Cluster_{nucleotide_counter}"
            nucleotide_counter += 1

    for record in SeqIO.parse(clustered_protein_file.replace(".fasta", "_clustered.fasta"), "fasta"):
        seq_str = str(record.seq)
        if seq_str not in protein_sequences:
            protein_sequences[seq_str] = f"Cluster_{protein_counter}"
            protein_counter += 1

    result_data = []
    for record in SeqIO.parse(extracted_hits_file, "fasta"):
        nucleotide_seq = str(record.seq)
        protein_seq = str(Seq(record.seq).translate(table=11))

        nucleotide_cluster = nucleotide_sequences.get(nucleotide_seq, f"Cluster_{nucleotide_counter}")
        protein_cluster = protein_sequences.get(protein_seq, f"Cluster_{protein_counter}")

        if nucleotide_cluster == f"Cluster_{nucleotide_counter}":
            nucleotide_sequences[nucleotide_seq] = nucleotide_cluster
            nucleotide_counter += 1
        if protein_cluster == f"Cluster_{protein_counter}":
            protein_sequences[protein_seq] = protein_cluster
            protein_counter += 1

        result_data.append({
            "Isolate_ID": record.id,
            "Query Name": query_id,
            "Nucleotide Cluster": nucleotide_cluster,
            "Nucleotide Sequence": nucleotide_seq,
            "Protein Cluster": protein_cluster,
            "Protein Sequence": protein_seq,
        })

    pd.DataFrame(result_data).to_csv(final_output_csv, index=False)
    print(f"✅ Final clustered results saved to {final_output_csv}")
# **Step 5: Generate Summary Statistics**

def generate_summary(query_output_dir, query_id, contigs_file):
    """Generates a summary statistics file for each query including sample count and unique sequences."""
    filtered_results_file = os.path.join(query_output_dir, "filtered_tblastn_results.csv")
    clustered_nucleotide_file = os.path.join(query_output_dir, "clustered_nucleotide_sequences.fasta")
    clustered_protein_file = os.path.join(query_output_dir, "clustered_protein_sequences.fasta")
    summary_file = os.path.join(query_output_dir, "summary_statistics.txt")

    # Count number of samples screened
    with open(contigs_file, "r") as f:
        total_samples = sum(1 for _ in f)
    
    # Count number of samples positive
    positive_samples = 0
    if os.path.exists(filtered_results_file):
        df = pd.read_csv(filtered_results_file)
        positive_samples = df["Subject"].nunique()
    
    # Count unique nucleotide sequences
    unique_nucleotide_seqs = 0
    if os.path.exists(clustered_nucleotide_file):
        unique_nucleotide_seqs = sum(1 for _ in SeqIO.parse(clustered_nucleotide_file, "fasta"))
    
    # Count unique protein sequences
    unique_protein_seqs = 0
    if os.path.exists(clustered_protein_file.replace(".fasta", "_clustered.fasta")):
        unique_protein_seqs = sum(1 for _ in SeqIO.parse(clustered_protein_file.replace(".fasta", "_clustered.fasta"), "fasta"))
    
    # Write summary statistics to file
    with open(summary_file, "w") as out_f:
        out_f.write(f"Query: {query_id}\n")
        out_f.write(f"Total Samples Screened: {total_samples}\n")
        out_f.write(f"Samples Positive: {positive_samples}\n")
        out_f.write(f"Unique Nucleotide Sequences: {unique_nucleotide_seqs}\n")
        out_f.write(f"Unique Protein Sequences: {unique_protein_seqs}\n")
    
    print(f"✅ Summary statistics saved to {summary_file}")

# **Main function**

def main():
    """Runs the full pipeline with steps for BLAST, TBLASTN, extraction, clustering, and CSV generation."""
    args = parse_args()
    output_dir = args.output

    if os.path.exists(output_dir) and args.force:
        subprocess.run(["rm", "-r", output_dir])
    os.makedirs(output_dir, exist_ok=True)

    print("Step 1: Creating BLAST databases...")
    create_blast_db(args.contigs, "blast_dbs", args.force_db)

    print("Step 2: Running TBLASTN searches...")
    run_tblastn(args.contigs, args.query, "blast_dbs", output_dir, args.identity, args.coverage)

    for query_record in SeqIO.parse(args.query, "fasta"):
        query_output_dir = os.path.join(output_dir, query_record.id)
        process_results(args.contigs, query_output_dir, query_record.id)
        generate_csv(query_output_dir, query_record.id)
        generate_summary(query_output_dir, query_record.id, args.contigs)

    print("✅ Pipeline completed!")

if __name__ == "__main__":
    main()

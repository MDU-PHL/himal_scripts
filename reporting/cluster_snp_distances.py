#!/usr/bin/env python3
"""
cluster_snp_distances.py
------------------------
Calculate pairwise SNP distance statistics (average, min, max) within and
between clusters defined at a specific SNP-clustering threshold.

Validates that isolates in the distance matrix are present in the cluster
definition file, and outputs structured summary reports.
"""

import argparse
import csv
import itertools
import logging
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
LOG_FORMAT = "[%(asctime)s] <%(levelname)s> %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_ID_CANDIDATES = [
    "seq_id",
    "seqid",
    "isolate",
    "isolate_id",
    "id",
    "sample",
    "sample_id",
    "strain",
]


# -----------------------------------------------------------------------------
# CLI Arguments Parser
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Calculate within-cluster and between-cluster SNP distance summaries "
            "(average, min, max) for isolates based on a clustering threshold."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  # Basic run with threshold column name:
  python3 cluster_snp_distances.py -c clusters.csv -d distances.tab -t Tx:5

  # Run with numeric threshold (automatically resolves to 'Tx:5' if present):
  python3 cluster_snp_distances.py -c clusters.csv -d distances.tab -t 5

  # Save text summary and structured TSV table:
  python3 cluster_snp_distances.py -c clusters.csv -d distances.tab -t Tx:10 -o summary.txt -s metrics.tsv

  # Enforce strict isolate matching and verbose logging:
  python3 cluster_snp_distances.py -c clusters.csv -d distances.tab -t Tx:2 -k -v
""",
    )

    parser.add_argument(
        "-c",
        "--clusters",
        required=True,
        type=Path,
        help="Path to clusters CSV/TSV file (contains isolate ID and threshold cluster columns).",
    )
    parser.add_argument(
        "-d",
        "--distances",
        required=True,
        type=Path,
        help="Path to pairwise distance matrix file (tab-separated or whitespace-separated).",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        required=True,
        type=str,
        help="Clustering threshold column name (e.g. 'Tx:5') or numeric threshold value (e.g. '5').",
    )
    parser.add_argument(
        "-i",
        "--id-col",
        type=str,
        default=None,
        help="Column name for isolate identifier in clusters file (default: auto-detected, e.g. 'Seq_ID').",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Optional path to output text summary report (printed to stdout if omitted).",
    )
    parser.add_argument(
        "-s",
        "--tsv-out",
        type=Path,
        default=None,
        help="Optional path to output machine-readable TSV metrics table.",
    )
    parser.add_argument(
        "-k",
        "--strict",
        action="store_true",
        help="Fail with error if any isolate in distances file is absent in clusters file.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )

    return parser.parse_args()


# -----------------------------------------------------------------------------
# Logic Functions
# -----------------------------------------------------------------------------
def detect_delimiter(file_path: Path) -> str:
    """Detect delimiter (comma, tab, or whitespace) from header line."""
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                if "\t" in line_str:
                    return "\t"
                if "," in line_str:
                    return ","
                return r"\s+"
    return ","


def load_clusters(
    clusters_path: Path, threshold_query: str, id_col: Optional[str] = None
) -> Tuple[Dict[str, str], str]:
    """
    Load isolate cluster assignments for the specified threshold from CSV/TSV.

    Returns:
        tuple: (dict mapping isolate_id -> cluster_id, resolved threshold column name)
    """
    if not clusters_path.is_file():
        raise FileNotFoundError(f"Clusters file not found: {clusters_path}")

    delim = detect_delimiter(clusters_path)
    with open(clusters_path, "r", encoding="utf-8") as f:
        if delim == r"\s+":
            lines = [line.strip().split() for line in f if line.strip()]
            if not lines:
                raise ValueError(f"Clusters file {clusters_path} is empty.")
            header = lines[0]
            rows = lines[1:]
        else:
            reader = csv.reader(f, delimiter=delim)
            rows_all = [r for r in reader if r and not r[0].startswith("#")]
            if not rows_all:
                raise ValueError(f"Clusters file {clusters_path} is empty.")
            header = [h.strip() for h in rows_all[0]]
            rows = [[c.strip() for c in r] for r in rows_all[1:]]

    # Resolve isolate ID column
    resolved_id_col = None
    if id_col:
        for idx, col in enumerate(header):
            if col.strip().lower() == id_col.strip().lower():
                resolved_id_col = idx
                break
        if resolved_id_col is None:
            raise KeyError(
                f"Specified isolate ID column '{id_col}' not found in {clusters_path}. "
                f"Available columns: {header}"
            )
    else:
        for idx, col in enumerate(header):
            if col.strip().lower() in DEFAULT_ID_CANDIDATES:
                resolved_id_col = idx
                break
        if resolved_id_col is None:
            logging.info(
                "No standard ID column name matched; using first column '%s' as isolate ID.",
                header[0],
            )
            resolved_id_col = 0

    # Resolve threshold column
    resolved_threshold_col = None
    threshold_clean = threshold_query.strip()

    # Exact match first
    for idx, col in enumerate(header):
        if col.strip().lower() == threshold_clean.lower():
            resolved_threshold_col = idx
            break

    # If numeric or prefix match attempted (e.g., query='5', match 'Tx:5' or 'tx_5')
    if resolved_threshold_col is None:
        patterns = [
            f"tx:{threshold_clean}".lower(),
            f"tx_{threshold_clean}".lower(),
            f"t:{threshold_clean}".lower(),
            f"cluster_{threshold_clean}".lower(),
            threshold_clean.lower(),
        ]
        for idx, col in enumerate(header):
            if col.strip().lower() in patterns:
                resolved_threshold_col = idx
                break

    if resolved_threshold_col is None:
        raise KeyError(
            f"Threshold column matching '{threshold_query}' not found in {clusters_path}. "
            f"Available columns: {header}"
        )

    col_name = header[resolved_threshold_col]
    logging.debug(
        "Using isolate ID column '%s' (index %d) and threshold column '%s' (index %d)",
        header[resolved_id_col],
        resolved_id_col,
        col_name,
        resolved_threshold_col,
    )

    clusters: Dict[str, str] = {}
    for row in rows:
        if len(row) <= max(resolved_id_col, resolved_threshold_col):
            continue
        isolate = row[resolved_id_col]
        cluster_val = row[resolved_threshold_col]
        if isolate:
            clusters[isolate] = cluster_val

    return clusters, col_name


def load_distance_matrix(
    distances_path: Path,
) -> Tuple[Dict[Tuple[str, str], float], List[str]]:
    """
    Load square pairwise distance matrix from file.

    Returns:
        tuple: (dict mapping (u, v) sorted tuple -> distance, list of isolates in matrix)
    """
    if not distances_path.is_file():
        raise FileNotFoundError(f"Distances file not found: {distances_path}")

    delim = detect_delimiter(distances_path)
    with open(distances_path, "r", encoding="utf-8") as f:
        if delim == r"\s+":
            raw_lines = [line.strip().split() for line in f if line.strip()]
        else:
            reader = csv.reader(f, delimiter=delim)
            raw_lines = [[c.strip() for c in r] for r in reader if r]

    if not raw_lines:
        raise ValueError(f"Distance matrix file {distances_path} is empty.")

    header = raw_lines[0]
    data_rows = raw_lines[1:]

    # Header parsing
    # If header contains column label in first position (e.g. 'Isolate', 'Seq_ID', or empty '')
    if len(header) == len(data_rows) + 1:
        col_isolates = header[1:]
    elif len(header) == len(data_rows):
        col_isolates = header
    else:
        # Check if first cell in header is empty or label
        if header[0].lower() in DEFAULT_ID_CANDIDATES or header[0] == "":
            col_isolates = header[1:]
        else:
            col_isolates = header

    matrix: Dict[Tuple[str, str], float] = {}
    row_isolates: List[str] = []

    for r_idx, row in enumerate(data_rows):
        row_id = row[0]
        row_isolates.append(row_id)
        values = row[1:]

        if len(values) < len(col_isolates):
            logging.warning(
                "Row %s has fewer values (%d) than expected columns (%d).",
                row_id,
                len(values),
                len(col_isolates),
            )

        for c_idx, val_str in enumerate(values):
            if c_idx >= len(col_isolates):
                break
            col_id = col_isolates[c_idx]
            try:
                dist = float(val_str)
            except ValueError:
                logging.warning(
                    "Non-numeric distance value '%s' at (%s, %s); skipping.",
                    val_str,
                    row_id,
                    col_id,
                )
                continue

            pair = (min(row_id, col_id), max(row_id, col_id))
            matrix[pair] = dist

    logging.debug(
        "Loaded %d pairwise distances across %d unique isolates.",
        len(matrix),
        len(row_isolates),
    )
    return matrix, row_isolates


def validate_isolates(
    dist_isolates: List[str],
    clusters: Dict[str, str],
    strict: bool = False,
) -> List[str]:
    """
    Check if all isolates in distances.tab are present in clusters.csv.

    Returns:
        List of common isolates to analyze.
    """
    dist_set = set(dist_isolates)
    clust_set = set(clusters.keys())

    missing_in_clusters = sorted(list(dist_set - clust_set))
    missing_in_distances = sorted(list(clust_set - dist_set))
    common_isolates = sorted(list(dist_set & clust_set))

    logging.info("Validating isolate presence across input files...")
    logging.info("Isolates in distance matrix: %d", len(dist_set))
    logging.info("Isolates in clusters file   : %d", len(clust_set))
    logging.info("Common isolates in both     : %d", len(common_isolates))

    if missing_in_clusters:
        msg = (
            f"{len(missing_in_clusters)} isolate(s) from distance matrix NOT present in clusters file: "
            + ", ".join(missing_in_clusters[:10])
            + ("..." if len(missing_in_clusters) > 10 else "")
        )
        if strict:
            logging.error("Strict validation failed: %s", msg)
            raise ValueError(msg)
        logging.warning("%s (these isolates will be excluded from cluster analysis)", msg)
    else:
        logging.info("Validation passed: All isolates in distance matrix are present in clusters file.")

    if missing_in_distances:
        logging.info(
            "%d isolate(s) from clusters file are absent from distance matrix: %s%s",
            len(missing_in_distances),
            ", ".join(missing_in_distances[:5]),
            ("..." if len(missing_in_distances) > 5 else ""),
        )

    if not common_isolates:
        raise ValueError("No common isolates found between distance matrix and clusters file.")

    return common_isolates


def calculate_stats(distances: List[float]) -> Optional[Tuple[float, float, float]]:
    """
    Calculate average, min, max for a list of distances.

    Returns:
        (average, min, max) or None if list is empty.
    """
    if not distances:
        return None
    avg = sum(distances) / len(distances)
    return avg, min(distances), max(distances)


def compute_cluster_metrics(
    isolates: List[str],
    clusters: Dict[str, str],
    dist_matrix: Dict[Tuple[str, str], float],
) -> Tuple[Dict[str, dict], Dict[Tuple[str, str], dict]]:
    """
    Compute within-cluster and between-cluster SNP distance metrics.

    Returns:
        tuple: (within_cluster_dict, between_cluster_dict)
    """
    # Group isolates by cluster
    cluster_to_isolates: Dict[str, List[str]] = defaultdict(list)
    for iso in isolates:
        c_id = clusters[iso]
        cluster_to_isolates[c_id].append(iso)

    # Sort clusters naturally (numeric if possible, else string)
    def cluster_sort_key(c: str):
        try:
            return (0, int(c))
        except ValueError:
            return (1, str(c))

    sorted_clusters = sorted(cluster_to_isolates.keys(), key=cluster_sort_key)

    # 1. Within-cluster distances
    within_metrics: Dict[str, dict] = {}
    for c_id in sorted_clusters:
        isos = cluster_to_isolates[c_id]
        n_iso = len(isos)

        if n_iso < 2:
            within_metrics[c_id] = {
                "num_isolates": n_iso,
                "num_pairs": 0,
                "stats": None,
                "applicable": False,
            }
        else:
            dists = []
            for u, v in itertools.combinations(isos, 2):
                pair = (min(u, v), max(u, v))
                if pair in dist_matrix:
                    dists.append(dist_matrix[pair])
                else:
                    logging.warning("Distance not found for pair (%s, %s)", u, v)

            within_metrics[c_id] = {
                "num_isolates": n_iso,
                "num_pairs": len(dists),
                "stats": calculate_stats(dists),
                "applicable": True,
            }

    # 2. Between-cluster distances (for all pairs of clusters)
    between_metrics: Dict[Tuple[str, str], dict] = {}
    for c1, c2 in itertools.combinations(sorted_clusters, 2):
        isos1 = cluster_to_isolates[c1]
        isos2 = cluster_to_isolates[c2]

        # Inter-cluster only (strictly cross-cluster pairs)
        inter_dists = []
        for u in isos1:
            for v in isos2:
                pair = (min(u, v), max(u, v))
                if pair in dist_matrix:
                    inter_dists.append(dist_matrix[pair])
                else:
                    logging.warning("Distance not found for pair (%s, %s)", u, v)

        # Pooled (include all pairs in C1 U C2: within C1, within C2, and between C1 & C2)
        pooled_isos = isos1 + isos2
        pooled_dists = []
        for u, v in itertools.combinations(pooled_isos, 2):
            pair = (min(u, v), max(u, v))
            if pair in dist_matrix:
                pooled_dists.append(dist_matrix[pair])

        between_metrics[(c1, c2)] = {
            "cluster_1": c1,
            "cluster_2": c2,
            "n_iso_1": len(isos1),
            "n_iso_2": len(isos2),
            "inter_stats": calculate_stats(inter_dists),
            "inter_pairs": len(inter_dists),
            "all_stats": calculate_stats(pooled_dists),
            "all_pairs": len(pooled_dists),
        }

    return within_metrics, between_metrics


def format_stats(stats: Optional[Tuple[float, float, float]], precision: int = 2) -> str:
    """Format (avg, min, max) tuple nicely."""
    if stats is None:
        return "N/A"
    avg, min_val, max_val = stats
    min_str = f"{int(min_val)}" if min_val.is_integer() else f"{min_val:.{precision}f}"
    max_str = f"{int(max_val)}" if max_val.is_integer() else f"{max_val:.{precision}f}"
    return f"average: {avg:.{precision}f}, min: {min_str}, max: {max_str}"


def build_text_summary(
    threshold_col: str,
    clusters_path: Path,
    distances_path: Path,
    within_metrics: Dict[str, dict],
    between_metrics: Dict[Tuple[str, str], dict],
) -> str:
    """Generate user-facing formatted text summary."""
    lines = []
    lines.append("=" * 80)
    lines.append("SNP DISTANCE CLUSTER SUMMARY")
    lines.append("=" * 80)
    lines.append(f"Clustering Threshold Column : {threshold_col}")
    lines.append(f"Clusters File              : {clusters_path}")
    lines.append(f"Distances File             : {distances_path}")
    lines.append(f"Total Clusters Identified  : {len(within_metrics)}")
    total_isolates = sum(m["num_isolates"] for m in within_metrics.values())
    lines.append(f"Total Analyzed Isolates    : {total_isolates}")
    lines.append("=" * 80)
    lines.append("")

    # Section 1: Within-cluster statistics
    lines.append("--- Within-Cluster SNP Distances ---")
    for c_id, m in within_metrics.items():
        n = m["num_isolates"]
        lines.append(f"number of isolates in cluster {c_id} = {n}")
        if not m["applicable"] or m["stats"] is None:
            lines.append(
                f"SNP distance between isolates in cluster {c_id} = N/A (single isolate in cluster)"
            )
        else:
            lines.append(
                f"SNP distance between isolates in cluster {c_id} = {format_stats(m['stats'])}"
            )
        lines.append("")

    # Section 2: Between-cluster statistics
    if between_metrics:
        lines.append("--- Inter-Cluster SNP Distances ---")
        for (c1, c2), bm in between_metrics.items():
            lines.append(
                f"SNP distance between isolates in cluster {c1} and cluster {c2} = "
                f"{format_stats(bm['all_stats'])} [include all]"
            )
            lines.append(
                f"SNP distance between isolates in cluster {c1} and cluster {c2} = "
                f"{format_stats(bm['inter_stats'])} [excluding the SNP distances within the same cluster]"
            )
            lines.append("")
    else:
        lines.append("--- Inter-Cluster SNP Distances ---")
        lines.append("Only 1 cluster present; no inter-cluster comparisons available.\n")

    lines.append("=" * 80)
    return "\n".join(lines)


def export_tsv_metrics(
    tsv_path: Path,
    within_metrics: Dict[str, dict],
    between_metrics: Dict[Tuple[str, str], dict],
) -> None:
    """Export tabular metrics to a TSV file for validation and downstream pipelines."""
    with open(tsv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        # Header
        writer.writerow(
            [
                "Comparison_Type",
                "Cluster_A",
                "Cluster_B",
                "Num_Isolates_A",
                "Num_Isolates_B",
                "Num_Pairs",
                "Average_SNP_Distance",
                "Min_SNP_Distance",
                "Max_SNP_Distance",
                "Notes",
            ]
        )

        # Within clusters
        for c_id, m in within_metrics.items():
            stats = m["stats"]
            if stats is not None:
                avg, min_v, max_v = stats
                notes = "Within-cluster pairs"
            else:
                avg, min_v, max_v = ("NA", "NA", "NA")
                notes = "Single isolate; within-cluster distance not applicable"

            writer.writerow(
                [
                    "Within_Cluster",
                    c_id,
                    c_id,
                    m["num_isolates"],
                    m["num_isolates"],
                    m["num_pairs"],
                    f"{avg:.4f}" if isinstance(avg, float) else avg,
                    min_v,
                    max_v,
                    notes,
                ]
            )

        # Between clusters (both include all and cross-cluster only)
        for (c1, c2), bm in between_metrics.items():
            # Inter-cluster only
            inter_stats = bm["inter_stats"]
            if inter_stats is not None:
                i_avg, i_min, i_max = inter_stats
                i_avg_str = f"{i_avg:.4f}"
            else:
                i_avg_str, i_min, i_max = ("NA", "NA", "NA")

            writer.writerow(
                [
                    "Between_Clusters_Excluding_Within",
                    c1,
                    c2,
                    bm["n_iso_1"],
                    bm["n_iso_2"],
                    bm["inter_pairs"],
                    i_avg_str,
                    i_min,
                    i_max,
                    "Strictly inter-cluster pairs",
                ]
            )

            # Pooled (include all)
            all_stats = bm["all_stats"]
            if all_stats is not None:
                a_avg, a_min, a_max = all_stats
                a_avg_str = f"{a_avg:.4f}"
            else:
                a_avg_str, a_min, a_max = ("NA", "NA", "NA")

            writer.writerow(
                [
                    "Between_Clusters_Including_All",
                    c1,
                    c2,
                    bm["n_iso_1"],
                    bm["n_iso_2"],
                    bm["all_pairs"],
                    a_avg_str,
                    a_min,
                    a_max,
                    "All pairs within and between both clusters",
                ]
            )


# -----------------------------------------------------------------------------
# Main Execution Flow
# -----------------------------------------------------------------------------
def main() -> int:
    """Main execution function."""
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        datefmt=LOG_DATEFMT,
        stream=sys.stderr,
    )

    logging.info("Starting cluster SNP distance analysis.")
    logging.info("Clusters file    : %s", args.clusters)
    logging.info("Distances file   : %s", args.distances)
    logging.info("Threshold query  : %s", args.threshold)
    logging.info("Strict validation: %s", args.strict)

    try:
        # Step 1: Load clusters and resolve threshold column
        clusters, resolved_col = load_clusters(
            clusters_path=args.clusters,
            threshold_query=args.threshold,
            id_col=args.id_col,
        )
        logging.info("Loaded %d isolates from %s (using column: '%s').", len(clusters), args.clusters, resolved_col)

        # Step 2: Load distance matrix
        dist_matrix, dist_isolates = load_distance_matrix(distances_path=args.distances)
        logging.info("Loaded %d isolates in distance matrix from %s.", len(dist_isolates), args.distances)

        # Step 3: Validate isolates in distance matrix vs clusters
        common_isolates = validate_isolates(
            dist_isolates=dist_isolates,
            clusters=clusters,
            strict=args.strict,
        )

        # Step 4: Compute metrics
        within_metrics, between_metrics = compute_cluster_metrics(
            isolates=common_isolates,
            clusters=clusters,
            dist_matrix=dist_matrix,
        )

        # Step 5: Format and deliver text summary
        summary_text = build_text_summary(
            threshold_col=resolved_col,
            clusters_path=args.clusters,
            distances_path=args.distances,
            within_metrics=within_metrics,
            between_metrics=between_metrics,
        )

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(summary_text + "\n")
            logging.info("Saved text summary report to %s", args.output)

        # Always print summary to stdout
        print(summary_text)

        # Step 6: Export TSV metrics if requested
        if args.tsv_out:
            args.tsv_out.parent.mkdir(parents=True, exist_ok=True)
            export_tsv_metrics(
                tsv_path=args.tsv_out,
                within_metrics=within_metrics,
                between_metrics=between_metrics,
            )
            logging.info("Saved tabular metrics TSV to %s", args.tsv_out)

        logging.info("Done.")
        return 0

    except Exception as exc:
        logging.error("Fatal error during analysis: %s", exc, exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())

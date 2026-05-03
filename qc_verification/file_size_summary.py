"""
Summarise file sizes in a sequencing run directory.

Scans all files in a given directory, computes size statistics (total, count,
average, min, max, median), exports a per-file CSV, saves a histogram PNG, and
writes a machine-readable JSON summary suitable for downstream validation
reporting.
"""

import json
import logging
import os
import sys
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_FORMAT = "[%(asctime)s] <%(levelname)s> %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATEFMT)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Summarise file sizes across all samples in a sequencing run directory. "
            "Recursively scans <directory>/<sample>/ subfolders, computes size statistics, "
            "produces a per-file CSV, a size histogram, and a JSON summary "
            "for downstream validation reporting."
        ),
        epilog=(
            "Examples:\n"
            "  python file_size_summary.py -d /home/mdu/reads/X19XX-XXXXX/ -r X19XX-XXXXX\n"
            "  python file_size_summary.py -d /data/runs/R001/ -r R001 -o results/ --verbose\n"
            "  python file_size_summary.py -d /data/runs/R001/ -r R001 --no-plot\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    io_group = parser.add_argument_group("Input / Output")
    io_group.add_argument(
        "-d", "--directory",
        default=None,
        metavar="DIR",
        help="Run directory to scan recursively (e.g. /home/mdu/reads/<RUN_ID>/). Default: /home/mdu/reads/<RUN_ID>/.",
    )
    io_group.add_argument(
        "-r", "--run-id",
        required=True,
        metavar="RUN_ID",
        help="Run identifier used to name output files.",
    )
    io_group.add_argument(
        "-o", "--outdir",
        default=".",
        metavar="DIR",
        help="Output directory for all generated files. Default: current directory.",
    )
    io_group.add_argument(
        "-c", "--csv",
        default=None,
        metavar="FILE",
        help=(
            "Override the output CSV filename. "
            "Default: <outdir>/file_sizes_summary_<run_id>.csv"
        ),
    )
    io_group.add_argument(
        "-p", "--plot",
        default=None,
        metavar="FILE",
        help=(
            "Override the output histogram PNG filename. "
            "Default: <outdir>/file_sizes_histogram_<run_id>.png"
        ),
    )
    io_group.add_argument(
        "-j", "--detailed",
        default=None,
        metavar="FILE",
        help=(
            "Override the output detailed JSON summary filename. "
            "Default: <outdir>/file_sizes_detailed_<run_id>.json"
        ),
    )

    opts = parser.add_argument_group("Options")
    opts.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip histogram generation.",
    )
    opts.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug logging.",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def get_file_sizes(directory: str) -> dict[str, int]:
    """Return a mapping of relative path → size in bytes for all files found
    by recursively walking *directory* (i.e. <directory>/<sample>/*.fastq.gz)."""
    file_sizes: dict[str, int] = {}
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            file_path = os.path.join(root, fname)
            rel_path = os.path.relpath(file_path, directory)
            file_sizes[rel_path] = os.path.getsize(file_path)
    logger.debug("Found %d files under: %s", len(file_sizes), directory)
    return file_sizes


def human_readable_size(size: int, decimal_places: int = 2) -> str:
    """Convert *size* bytes to a human-readable string (e.g. '1.23 MB')."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"


def summarise_file_sizes(file_sizes: dict[str, int]) -> dict:
    """Compute aggregate size statistics from *file_sizes*."""
    sizes = list(file_sizes.values())
    num_files = len(sizes)
    total = sum(sizes)
    return {
        "num_files": num_files,
        "total_bytes": total,
        "avg_bytes": total / num_files if num_files else 0,
        "min_bytes": min(sizes) if sizes else 0,
        "max_bytes": max(sizes) if sizes else 0,
        "median_bytes": float(np.median(sizes)) if sizes else 0,
        "total_human": human_readable_size(total),
        "avg_human": human_readable_size(int(total / num_files)) if num_files else "0 B",
        "min_human": human_readable_size(min(sizes)) if sizes else "0 B",
        "max_human": human_readable_size(max(sizes)) if sizes else "0 B",
        "median_human": human_readable_size(int(np.median(sizes))) if sizes else "0 B",
    }


def save_csv(file_sizes: dict[str, int], output_path: str) -> None:
    """Write per-file size table to *output_path*."""
    df = pd.DataFrame(list(file_sizes.items()), columns=["Relative Path", "Size (bytes)"])
    df["Size (human readable)"] = df["Size (bytes)"].apply(human_readable_size)
    df.sort_values("Size (bytes)", ascending=False, inplace=True)
    df.to_csv(output_path, index=False)
    logger.info("CSV saved → %s", output_path)


def save_detailed_json(summary: dict, run_id: str, directory: str, output_path: str) -> None:
    """Write a machine-readable JSON summary to *output_path* for downstream validation."""
    payload = {
        "run_id": run_id,
        "directory": directory,
        "statistics": summary,
    }
    with open(output_path, "w") as fh:
        json.dump(payload, fh, indent=2)
    logger.info("Detailed JSON saved → %s", output_path)


def plot_histogram(file_sizes: dict[str, int], run_id: str, output_path: str) -> None:
    """Save a histogram of file sizes to *output_path*."""
    sizes = list(file_sizes.values())
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(sizes, bins=20, color="skyblue", edgecolor="black")
    ax.set_xlabel("Size (bytes)")
    ax.set_ylabel("Frequency")
    ax.set_title(f"Histogram of File Sizes — Run ID: {run_id}")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("Histogram saved → %s", output_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    args = parse_args()

    if args.verbose:
        logging.root.setLevel(logging.DEBUG)

    if args.directory is None:
        args.directory = os.path.join("/home/mdu/reads", args.run_id)

    os.makedirs(args.outdir, exist_ok=True)

    csv_path = args.csv or os.path.join(args.outdir, f"file_sizes_summary_{args.run_id}.csv")
    plot_path = args.plot or os.path.join(args.outdir, f"file_sizes_histogram_{args.run_id}.png")
    json_path = args.detailed or os.path.join(args.outdir, f"file_sizes_detailed_{args.run_id}.json")

    logger.info("Starting file size summary")
    logger.info("  Run ID    : %s", args.run_id)
    logger.info("  Directory : %s", args.directory)
    logger.info("  Output dir: %s", args.outdir)

    try:
        file_sizes = get_file_sizes(args.directory)

        if not file_sizes:
            logger.warning("No files found in: %s", args.directory)
            sys.exit(0)

        summary = summarise_file_sizes(file_sizes)

        logger.info("File count  : %d", summary["num_files"])
        logger.info("Total size  : %s", summary["total_human"])
        logger.info("Average size: %s", summary["avg_human"])
        logger.info("Min size    : %s", summary["min_human"])
        logger.info("Max size    : %s", summary["max_human"])
        logger.info("Median size : %s", summary["median_human"])

        save_csv(file_sizes, csv_path)
        save_detailed_json(summary, args.run_id, args.directory, json_path)

        if not args.no_plot:
            plot_histogram(file_sizes, args.run_id, plot_path)
        else:
            logger.info("Skipping histogram (--no-plot).")

    except Exception as exc:
        logger.error("Fatal error: %s", exc)
        raise SystemExit(1)

    logger.info("Done.")


if __name__ == "__main__":
    main()

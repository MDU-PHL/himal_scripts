"""
compare_excel.py
----------------
Generic comparison tool for two versions of an Excel file.

Aligns rows from both files using a user-supplied sort/join key column, then
compares every cell value. Produces three outputs:

  1. <out>.xlsx  — Three-sheet Excel workbook:
       • "v1"         : original v1 data
       • "v2"         : original v2 data
       • "comparison" : aligned cell-by-cell diff; differences highlighted red,
                        matches left white, rows only in one file highlighted orange

  2. <out>.log   — Human-readable text report with:
       • Row counts and rows unique to each file
       • Overall concordance percentage
       • Per-column concordance table
       • Full differences table (key | column | v1 value | v2 value)

The script stops immediately if the two files do not share identical column
headers (excluding the sort key).

Usage:
  python3 compare_excel.py v1.xlsx v2.xlsx -k "MDU ID"
  python3 compare_excel.py old.xlsx new.xlsx -k "MDU ID" -o report -v
  python3 compare_excel.py a.xlsx b.xlsx --no-key -o diff_report
"""

import sys
import logging
import argparse
import pathlib
import datetime

import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FILL_DIFF    = PatternFill(start_color="FF4444", end_color="FF4444", fill_type="solid")   # red
FILL_ONLY_V1 = PatternFill(start_color="FFB347", end_color="FFB347", fill_type="solid")   # orange
FILL_ONLY_V2 = PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid")   # amber
FILL_HEADER  = PatternFill(start_color="2E4057", end_color="2E4057", fill_type="solid")   # dark blue
FILL_MATCH   = PatternFill(fill_type=None)                                                 # no fill

FONT_HEADER  = Font(bold=True, color="FFFFFF")
FONT_ONLY    = Font(italic=True)

NA_VALUES = {"nan", "NaT", "None", "NA", "N/A", ""}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    epilog = """
Examples:
  # Compare two versions of TBsharepoint, joined on MDU ID
  python3 compare_excel.py TBsharepoint_v1.xlsx TBsharepoint_v2.xlsx -k "MDU ID"

  # Compare any two files with a custom key and output name
  python3 compare_excel.py old.xlsx new.xlsx -k "MDU ID" -o my_diff_report -v

  # Positional comparison (no join key — rows must already be aligned)
  python3 compare_excel.py a.xlsx b.xlsx --no-key -o positional_diff
    """
    parser = argparse.ArgumentParser(
        description="Compare two Excel files cell-by-cell and report differences.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "v1",
        help="Path to the first (reference / older) Excel file.",
    )
    parser.add_argument(
        "v2",
        help="Path to the second (new / updated) Excel file.",
    )
    parser.add_argument(
        "--key-col", "-k",
        default=None,
        metavar="COLUMN",
        help=(
            "Column to use as the join key for row alignment (e.g. 'MDU ID'). "
            "Rows are outer-joined on this column so mismatched row counts are handled correctly. "
            "Required unless --no-key is set."
        ),
    )
    parser.add_argument(
        "--no-key", "-K",
        action="store_true",
        help=(
            "Skip join-key alignment and compare rows positionally (row 1 vs row 1, etc.). "
            "Both files must already be in the same row order. Use when there is no suitable key column."
        ),
    )
    parser.add_argument(
        "--sheet", "-S",
        default=0,
        help="Sheet name or 0-based index to read from each file (default: first sheet).",
    )
    parser.add_argument(
        "--output", "-o",
        default="excel_comparison",
        metavar="STEM",
        help="Output filename stem (no extension). Produces <stem>.xlsx and <stem>.log (default: excel_comparison).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] <%(levelname)s> %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------------
# Load & validate
# ---------------------------------------------------------------------------

def load(path: str, sheet) -> pd.DataFrame:
    """Load an Excel sheet as all-string DataFrame."""
    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def validate_headers(df1: pd.DataFrame, df2: pd.DataFrame, key_col: str | None) -> list[str]:
    """
    Confirm column headers are identical (order-insensitive).
    Excludes the key column from the data columns returned.
    Raises SystemExit if headers differ.
    """
    h1, h2 = set(df1.columns), set(df2.columns)
    if h1 != h2:
        only_v1 = sorted(h1 - h2)
        only_v2 = sorted(h2 - h1)
        logging.error("Column headers differ between the two files — cannot compare.")
        if only_v1:
            logging.error(f"  Columns only in v1 : {only_v1}")
        if only_v2:
            logging.error(f"  Columns only in v2 : {only_v2}")
        logging.error("Fix the column headers so they are identical, then re-run.")
        sys.exit(1)

    cols = list(df1.columns)
    if key_col and key_col in cols:
        cols.remove(key_col)
    return cols


# ---------------------------------------------------------------------------
# Row alignment
# ---------------------------------------------------------------------------

def align_on_key(df1: pd.DataFrame, df2: pd.DataFrame, key_col: str) -> pd.DataFrame:
    """
    Outer-join df1 and df2 on key_col.
    Returns a merged DataFrame with suffixes _v1 and _v2 for each data column.
    Adds a '_row_status' column: 'both' | 'only_v1' | 'only_v2'.
    """
    df1 = df1.copy()
    df2 = df2.copy()
    df1["_src"] = "v1"
    df2["_src"] = "v2"

    merged = df1.merge(df2, on=key_col, how="outer", suffixes=("_v1", "_v2"), indicator=True)
    merged["_row_status"] = merged["_merge"].map(
        {"both": "both", "left_only": "only_v1", "right_only": "only_v2"}
    )
    merged = merged.drop(columns=["_merge", "_src_v1", "_src_v2"], errors="ignore")
    # pd.merge with indicator=True (and outer joins in general) can leave Categorical
    # dtype on string columns. fillna("") raises TypeError if "" is not a known category,
    # so cast all Categorical columns back to plain object/str first.
    cat_cols = merged.select_dtypes(include="category").columns.tolist()
    if cat_cols:
        merged[cat_cols] = merged[cat_cols].astype(str)
    merged = merged.fillna("")
    return merged


def align_positional(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    """
    Align rows positionally by index (row 0 vs row 0, etc.).
    Pads the shorter file with empty rows.
    Adds '_row_status': 'both' | 'only_v1' | 'only_v2'.
    """
    max_len = max(len(df1), len(df2))
    cols = list(df1.columns)

    rows = []
    for i in range(max_len):
        row: dict = {}
        if i < len(df1) and i < len(df2):
            for c in cols:
                row[f"{c}_v1"] = df1.iloc[i][c]
                row[f"{c}_v2"] = df2.iloc[i][c]
            row["_row_status"] = "both"
        elif i < len(df1):
            for c in cols:
                row[f"{c}_v1"] = df1.iloc[i][c]
                row[f"{c}_v2"] = ""
            row["_row_status"] = "only_v1"
        else:
            for c in cols:
                row[f"{c}_v1"] = ""
                row[f"{c}_v2"] = df2.iloc[i][c]
            row["_row_status"] = "only_v2"
        rows.append(row)

    return pd.DataFrame(rows).fillna("")


# ---------------------------------------------------------------------------
# Cell-level comparison
# ---------------------------------------------------------------------------

def _normalise(val: str) -> str:
    """Strip whitespace and normalise NA-like strings to empty string."""
    s = str(val).strip()
    return "" if s in NA_VALUES else s


def compare_aligned(aligned: pd.DataFrame, data_cols: list[str], key_col: str | None) -> dict:
    """
    Walk the aligned DataFrame and collect per-cell comparison results.

    Returns a dict with:
      diffs        : list of diff records {key, column, v1, v2, status}
      col_stats    : {col: {match, total}}
      overall      : {match, total}
    """
    diffs: list[dict] = []
    col_stats: dict[str, dict] = {c: {"match": 0, "total": 0} for c in data_cols}
    overall_match, overall_total = 0, 0

    for _, row in aligned.iterrows():
        status = row.get("_row_status", "both")
        key_val = str(row.get(key_col, "")) if key_col else f"row {_}"

        if status != "both":
            # Rows only in one file — count all cells as mismatches
            for col in data_cols:
                v1 = _normalise(row.get(f"{col}_v1", ""))
                v2 = _normalise(row.get(f"{col}_v2", ""))
                col_stats[col]["total"] += 1
                overall_total += 1
                diffs.append({
                    "key":    key_val,
                    "column": col,
                    "v1":     v1,
                    "v2":     v2,
                    "status": f"ROW ONLY IN {status.replace('only_', '').upper()}",
                })
            continue

        for col in data_cols:
            v1 = _normalise(row.get(f"{col}_v1", ""))
            v2 = _normalise(row.get(f"{col}_v2", ""))
            col_stats[col]["total"] += 1
            overall_total += 1

            if v1 == v2:
                col_stats[col]["match"] += 1
                overall_match += 1
                logging.debug(f"  MATCH  | key={key_val} | col={col} | '{v1}'")
            else:
                diffs.append({
                    "key":    key_val,
                    "column": col,
                    "v1":     v1,
                    "v2":     v2,
                    "status": "DIFFER",
                })
                logging.debug(f"  DIFFER | key={key_val} | col={col} | v1='{v1}' v2='{v2}'")

    return {
        "diffs":    diffs,
        "col_stats": col_stats,
        "overall":  {"match": overall_match, "total": overall_total},
    }


# ---------------------------------------------------------------------------
# Text log
# ---------------------------------------------------------------------------

def write_text_log(
    path: str,
    v1_path: str,
    v2_path: str,
    key_col: str | None,
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    aligned: pd.DataFrame,
    results: dict,
) -> None:
    only_v1_rows = (aligned["_row_status"] == "only_v1").sum()
    only_v2_rows = (aligned["_row_status"] == "only_v2").sum()
    both_rows    = (aligned["_row_status"] == "both").sum()

    overall = results["overall"]
    pct = (overall["match"] / overall["total"] * 100) if overall["total"] else 0.0

    lines: list[str] = []
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines += [
        "=" * 72,
        "Excel Comparison Report",
        f"Generated : {ts}",
        f"v1        : {v1_path}",
        f"v2        : {v2_path}",
        f"Key column: {key_col or '(none — positional)'}",
        "=" * 72,
        "",
        "--- Row Counts ---",
        f"  v1 rows              : {len(df1)}",
        f"  v2 rows              : {len(df2)}",
        f"  Rows matched (both)  : {both_rows}",
        f"  Rows only in v1      : {only_v1_rows}",
        f"  Rows only in v2      : {only_v2_rows}",
        "",
        "--- Overall Concordance ---",
        f"  Comparable cells : {overall['total']}",
        f"  Matching cells   : {overall['match']}",
        f"  Concordance      : {pct:.2f}%",
        "",
        "--- Per-Column Concordance ---",
    ]

    col_stats = results["col_stats"]
    col_w = max((len(c) for c in col_stats), default=10)
    lines.append(f"  {'Column':<{col_w}}  {'Match':>7}  {'Total':>7}  Concordance")
    lines.append(f"  {'-'*col_w}  {'-'*7}  {'-'*7}  -----------")
    for col, st in col_stats.items():
        cpct = (st["match"] / st["total"] * 100) if st["total"] else 0.0
        lines.append(f"  {col:<{col_w}}  {st['match']:>7}  {st['total']:>7}  {cpct:>10.2f}%")

    lines += ["", "--- Differences ---"]
    diffs = results["diffs"]
    if not diffs:
        lines.append("  ✓ No differences found.")
    else:
        lines.append(f"  {len(diffs)} difference(s) found.")
        lines.append("")
        key_w = max(max((len(str(d["key"])) for d in diffs), default=6), 6)
        col_w2 = max(max((len(d["column"]) for d in diffs), default=6), 6)
        val_w = 30
        hdr = (f"  {'Key':<{key_w}}  {'Column':<{col_w2}}  "
               f"{'v1 value':<{val_w}}  {'v2 value':<{val_w}}  Status")
        lines.append(hdr)
        lines.append("  " + "-" * (len(hdr) - 2))
        for d in diffs:
            v1_s = str(d["v1"])[:val_w]
            v2_s = str(d["v2"])[:val_w]
            lines.append(
                f"  {str(d['key']):<{key_w}}  {d['column']:<{col_w2}}  "
                f"{v1_s:<{val_w}}  {v2_s:<{val_w}}  {d['status']}"
            )

    lines += ["", "=" * 72, "End of report", "=" * 72]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logging.info(f"  Text log written: {path}")


# ---------------------------------------------------------------------------
# Excel workbook output
# ---------------------------------------------------------------------------

def _write_raw_sheet(ws, df: pd.DataFrame, title: str) -> None:
    """Write a plain data sheet with a styled header row."""
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start=1):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=value)
            if r_idx == 1:
                cell.fill = FILL_HEADER
                cell.font = FONT_HEADER
                cell.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"
    ws.title = title


def _write_comparison_sheet(
    ws,
    aligned: pd.DataFrame,
    data_cols: list[str],
    key_col: str | None,
    results: dict,
) -> None:
    """
    Write the comparison sheet.

    Layout (columns):
      [key_col?] | [row_status] | col1_v1 | col1_v2 | col1_status | col2_v1 | ...
    """
    diff_index: set[tuple] = {
        (d["key"], d["column"]) for d in results["diffs"]
    }

    # Build header
    header: list[str] = []
    if key_col:
        header.append(key_col)
    header.append("row_status")
    for col in data_cols:
        header += [f"{col} [v1]", f"{col} [v2]", f"{col} [status]"]

    # Write header row
    for c_idx, h in enumerate(header, start=1):
        cell = ws.cell(row=1, column=c_idx, value=h)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    # Write data rows
    for r_idx, (_, row) in enumerate(aligned.iterrows(), start=2):
        row_status = row.get("_row_status", "both")
        key_val    = str(row.get(key_col, "")) if key_col else str(r_idx - 1)

        col_cursor = 1
        if key_col:
            ws.cell(row=r_idx, column=col_cursor, value=key_val)
            col_cursor += 1

        ws.cell(row=r_idx, column=col_cursor, value=row_status)
        col_cursor += 1

        for col in data_cols:
            v1 = _normalise(row.get(f"{col}_v1", ""))
            v2 = _normalise(row.get(f"{col}_v2", ""))

            is_row_only = row_status != "both"
            is_diff = (key_val, col) in diff_index or is_row_only

            # v1 cell
            c1 = ws.cell(row=r_idx, column=col_cursor, value=v1)
            if is_row_only and row_status == "only_v1":
                c1.fill = FILL_ONLY_V1
                c1.font = FONT_ONLY
            elif is_diff and not is_row_only:
                c1.fill = FILL_DIFF
            col_cursor += 1

            # v2 cell
            c2 = ws.cell(row=r_idx, column=col_cursor, value=v2)
            if is_row_only and row_status == "only_v2":
                c2.fill = FILL_ONLY_V2
                c2.font = FONT_ONLY
            elif is_diff and not is_row_only:
                c2.fill = FILL_DIFF
            col_cursor += 1

            # status cell
            if is_row_only:
                status_val = f"ROW ONLY IN {row_status.replace('only_', '').upper()}"
            elif v1 == v2:
                status_val = "MATCH"
            else:
                status_val = "DIFFER"
            c3 = ws.cell(row=r_idx, column=col_cursor, value=status_val)
            if status_val == "DIFFER":
                c3.fill = FILL_DIFF
            col_cursor += 1

    # Auto-size columns (cap at 40)
    for col_cells in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max_len + 2, 40)

    ws.freeze_panes = "A2"
    ws.title = "comparison"


def _write_concordance_sheet(ws, results: dict, key_col: str | None) -> None:
    """Small summary sheet with overall and per-column concordance."""
    overall = results["overall"]
    pct = (overall["match"] / overall["total"] * 100) if overall["total"] else 0.0

    ws.title = "concordance"
    headers = ["Column", "Matching cells", "Total cells", "Concordance %"]
    for c_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c_idx, value=h)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER

    # Overall row
    c = ws.cell(row=2, column=1, value="OVERALL")
    c.font = Font(bold=True)
    ws.cell(row=2, column=2, value=overall["match"])
    ws.cell(row=2, column=3, value=overall["total"])
    ws.cell(row=2, column=4, value=round(pct, 2))

    for r_idx, (col, st) in enumerate(results["col_stats"].items(), start=3):
        cpct = (st["match"] / st["total"] * 100) if st["total"] else 0.0
        ws.cell(row=r_idx, column=1, value=col)
        ws.cell(row=r_idx, column=2, value=st["match"])
        ws.cell(row=r_idx, column=3, value=st["total"])
        ws.cell(row=r_idx, column=4, value=round(cpct, 2))

    for col_cells in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max_len + 2, 30)


def write_excel_report(
    out_path: str,
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    aligned: pd.DataFrame,
    data_cols: list[str],
    key_col: str | None,
    results: dict,
) -> None:
    wb = openpyxl.Workbook()

    # Sheet 1: v1
    ws_v1 = wb.active
    _write_raw_sheet(ws_v1, df1, "v1")

    # Sheet 2: v2
    ws_v2 = wb.create_sheet()
    _write_raw_sheet(ws_v2, df2, "v2")

    # Sheet 3: comparison
    ws_cmp = wb.create_sheet()
    _write_comparison_sheet(ws_cmp, aligned, data_cols, key_col, results)

    # Sheet 4: concordance summary
    ws_con = wb.create_sheet()
    _write_concordance_sheet(ws_con, results, key_col)

    wb.save(out_path)
    logging.info(f"  Excel report written: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    # Validate mutual exclusion of --key-col and --no-key
    if not args.key_col and not args.no_key:
        logging.error("Provide a join key column with -k/--key-col, or use --no-key for positional comparison.")
        sys.exit(1)
    if args.key_col and args.no_key:
        logging.error("--key-col and --no-key are mutually exclusive.")
        sys.exit(1)

    out_xlsx = f"{args.output}.xlsx"
    out_log  = f"{args.output}.log"

    logging.info("=" * 60)
    logging.info("compare_excel.py — Excel File Comparison")
    logging.info("=" * 60)
    logging.info(f"v1            : {args.v1}")
    logging.info(f"v2            : {args.v2}")
    logging.info(f"Key column    : {args.key_col or '(none — positional)'}")
    logging.info(f"Output xlsx   : {out_xlsx}")
    logging.info(f"Output log    : {out_log}")

    # Load
    logging.info("Loading files ...")
    df1 = load(args.v1, args.sheet)
    df2 = load(args.v2, args.sheet)
    logging.info(f"  v1: {len(df1)} rows x {len(df1.columns)} cols")
    logging.info(f"  v2: {len(df2)} rows x {len(df2.columns)} cols")

    # Validate headers
    logging.info("Validating column headers ...")
    data_cols = validate_headers(df1, df2, args.key_col)
    logging.info(f"  Headers match. {len(data_cols)} data column(s) to compare.")
    if args.key_col:
        if args.key_col not in df1.columns:
            logging.error(f"Key column '{args.key_col}' not found in v1 columns: {list(df1.columns)}")
            sys.exit(1)
        logging.info(f"  Key column '{args.key_col}' found in both files.")

    # Align rows
    logging.info("Aligning rows ...")
    if args.key_col:
        aligned = align_on_key(df1, df2, args.key_col)
        only_v1 = (aligned["_row_status"] == "only_v1").sum()
        only_v2 = (aligned["_row_status"] == "only_v2").sum()
        both    = (aligned["_row_status"] == "both").sum()
        logging.info(f"  Rows matched (in both) : {both}")
        logging.info(f"  Rows only in v1        : {only_v1}")
        logging.info(f"  Rows only in v2        : {only_v2}")
    else:
        aligned = align_positional(df1, df2)
        logging.info(f"  Positional alignment: {len(aligned)} row positions compared.")

    # Compare
    logging.info("Comparing cells ...")
    results = compare_aligned(aligned, data_cols, args.key_col)

    overall = results["overall"]
    pct = (overall["match"] / overall["total"] * 100) if overall["total"] else 0.0
    n_diffs = len([d for d in results["diffs"] if d["status"] == "DIFFER"])
    logging.info(f"  Overall concordance : {pct:.2f}%")
    logging.info(f"  Cells compared      : {overall['total']}")
    logging.info(f"  Differences         : {n_diffs}")

    # Write outputs
    logging.info("Writing outputs ...")
    write_excel_report(out_xlsx, df1, df2, aligned, data_cols, args.key_col, results)
    write_text_log(out_log, args.v1, args.v2, args.key_col, df1, df2, aligned, results)

    logging.info("=" * 60)
    logging.info(f"Done. Overall concordance: {pct:.2f}%")
    logging.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception(f"Fatal error: {exc}")
        sys.exit(1)


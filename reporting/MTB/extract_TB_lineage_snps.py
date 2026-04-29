#!/usr/bin/env python3
import argparse
import re
import sys
import os
from datetime import datetime

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg, fh=None):
    line = f"[{now()}] - {msg}"
    print(line)
    if fh:
        fh.write(line + "\n")

def parse_bed(bed_path):
    entries = []
    if not os.path.exists(bed_path):
        raise FileNotFoundError(bed_path)
    with open(bed_path) as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln or ln.lstrip().startswith("#"):
                continue
            parts = re.split(r"\s+", ln)
            # keep structured fields for easy output
            if len(parts) < 4:
                continue
            chrom = parts[0]
            start = parts[1]
            end = parts[2]
            label = parts[3]
            extras = parts[4:] if len(parts) > 4 else []
            ref_bed = extras[0] if len(extras) > 0 else ""
            clade = extras[1] if len(extras) > 1 else ""
            subgroup = extras[2] if len(extras) > 2 else ""
            entries.append({
                "chrom": chrom,
                "start": int(start),
                "end": int(end),
                "label": label,
                "raw": ln,
                "extras": extras,
                "ref_bed": ref_bed,
                "clade": clade,
                "subgroup": subgroup
            })
    return entries

def parse_vcf(vcf_path):
    """
    Parse vcf and return a map: pos -> list of dicts with key fields.
    Skips '##' meta lines and header line starting with #CHROM.
    """
    positions = {}  # pos -> list of dicts
    if not os.path.exists(vcf_path):
        raise FileNotFoundError(vcf_path)
    with open(vcf_path) as f:
        for ln in f:
            if ln.startswith("##"):
                continue
            if ln.startswith("#CHROM"):
                continue
            ln = ln.rstrip("\n")
            if not ln:
                continue
            parts = re.split(r"\s+", ln)
            if len(parts) < 5:
                continue
            try:
                pos = int(parts[1])
            except ValueError:
                continue
            chrom = parts[0]
            ref = parts[3]
            alt = parts[4]
            qual = parts[5] if len(parts) > 5 else ""
            info = parts[7] if len(parts) > 7 else ""
            dp_match = re.search(r'(?:^|;)DP=([0-9]+)', info)
            depth = dp_match.group(1) if dp_match else ""
            # join any sample columns so there's no embedded tabs
            sample = ""
            if len(parts) > 9:
                sample = ";".join(parts[9:])
            elif len(parts) > 9 - 1:
                sample = parts[9] if len(parts) > 9 else ""
            positions.setdefault(pos, []).append({
                "chrom": chrom,
                "pos": pos,
                "ref": ref,
                "alt": alt,
                "qual": qual,
                "depth": depth,
                "sample": sample
            })
    return positions

def match_lineage(entries, query):
    q = query.lower()
    matched = [e for e in entries if e["label"].lower().startswith(q)]
    return matched

def write_summary(out_path, matched_entries, vcf_pos_map, logfh):
    """
    Write a tab-separated summary with stable columns so downstream tools (csvtk) can parse it.
    Columns:
      chrom, start, end, label, ref_bed, clade, subgroup, present, vcf_chrom, vcf_pos, vcf_ref, vcf_alt, vcf_qual, sample
    If multiple VCF records exist for the same position, their values are joined with ';'
    """
    found = 0
    with open(out_path, "w") as out:
        out.write("\t".join([
            "chrom", "start", "end", "label", "ref_bed", "clade", "subgroup",
            "present", "vcf_chrom", "vcf_pos", "vcf_ref", "vcf_alt", "vcf_qual", "depth", "vcf_sample"
        ]) + "\n")
        for e in matched_entries:
            vpos = e["end"]  # BED end (0-based half-open) used as VCF POS (1-based) per script notes
            vrec_list = vcf_pos_map.get(vpos, [])
            present = "YES" if vrec_list else "NO"
            if vrec_list:
                found += 1
                vcf_chroms = ";".join([r["chrom"] for r in vrec_list])
                vcf_poss = ";".join([str(r["pos"]) for r in vrec_list])
                vcf_refs = ";".join([r["ref"] for r in vrec_list])
                vcf_alts = ";".join([r["alt"] for r in vrec_list])
                vcf_quals = ";".join([r["qual"] for r in vrec_list])
                vcf_depths = ";".join([r["depth"] for r in vrec_list])
                vcf_samples = ";".join([r["sample"] for r in vrec_list])
            else:
                vcf_chroms = vcf_poss = vcf_refs = vcf_alts = vcf_quals = vcf_depths = vcf_samples = ""
            row = [
                e.get("chrom", ""),
                str(e.get("start", "")),
                str(e.get("end", "")),
                e.get("label", ""),
                e.get("ref_bed", ""),
                e.get("clade", ""),
                e.get("subgroup", ""),
                present,
                vcf_chroms,
                vcf_poss,
                vcf_refs,
                vcf_alts,
                vcf_quals,
                vcf_depths,
                vcf_samples
            ]
            out.write("\t".join(row) + "\n")
    log(f"Wrote summary to {out_path}", logfh)
    log(f"Markers matched: {len(matched_entries)}; markers present in VCF: {found}", logfh)

def main():
    parser = argparse.ArgumentParser(
        description="Extract lineage-specific SNP markers from a barcode .bed and check presence in VCF.",
        epilog=(
            "Example:\n"
            "  python3 extract_TB_lineage_snps.py -l lineage2 -b /path/tbtamr.barcode.bed -v sample/snps.raw.vcf "
            "-o lineage2_snps.txt -L lineage2_snps.log\n\n"
            "Notes:\n"
            "- Matching is case-insensitive and matches labels that start with the query (e.g. 'lineage2' matches 'lineage2.1').\n"
            "- Output is a tab-separated file with fixed columns suitable for csvtk / csvkit.\n"
            "- BED is expected in standard 0-based half-open coordinates; this script uses the BED end coordinate as the 1-based VCF POS.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-l", "--lineage", dest="lineage", required=True,
                        help="Lineage string to match (e.g. lineage2 or La1). Case-insensitive, prefix match used.")
    parser.add_argument("-b", "--bed", dest="bed", required=True, help="Path to barcode .bed file")
    parser.add_argument("-v", "--vcf", dest="vcf", required=True, help="Path to VCF file (snps.raw.vcf)")
    parser.add_argument("-o", "--out", dest="out", required=True, help="Output summary file (tab-separated)")
    parser.add_argument("-L", "--log", dest="log", required=True, help="Log file path")
    args = parser.parse_args()

    # prepare log file
    try:
        logfh = open(args.log, "w")
    except Exception as e:
        print(f"Could not open log file {args.log}: {e}", file=sys.stderr)
        sys.exit(1)

    log("Starting extract_TB_lineage_snps.py", logfh)
    log(f"Args: lineage={args.lineage}, bed={args.bed}, vcf={args.vcf}, out={args.out}", logfh)

    try:
        bed_entries = parse_bed(args.bed)
        log(f"Read {len(bed_entries)} entries from BED", logfh)
    except Exception as e:
        log(f"Error reading BED: {e}", logfh)
        logfh.close()
        sys.exit(1)

    matched = match_lineage(bed_entries, args.lineage)
    if not matched:
        # provide summary of available labels
        labels = {}
        for e in bed_entries:
            labels[e["label"]] = labels.get(e["label"], 0) + 1
        log("No matching lineage markers found.", logfh)
        log("Available lineage labels (label:count):", logfh)
        for lbl, cnt in sorted(labels.items()):
            log(f"  {lbl}: {cnt}", logfh)
        logfh.close()
        sys.exit(0)

    log(f"Found {len(matched)} markers matching lineage '{args.lineage}'", logfh)

    try:
        vcf_map = parse_vcf(args.vcf)
        total_vcf_records = sum(len(v) for v in vcf_map.values())
        log(f"Read {total_vcf_records} VCF records for {len(vcf_map)} distinct positions", logfh)
    except Exception as e:
        log(f"Error reading VCF: {e}", logfh)
        logfh.close()
        sys.exit(1)

    write_summary(args.out, matched, vcf_map, logfh)

    log("Completed successfully", logfh)
    logfh.close()

if __name__ == "__main__":
    main()

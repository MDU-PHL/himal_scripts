import typer

def generate_run_me(
    job_id: str = typer.Argument(..., help="Job ID (e.g., XX_20xxxxxx_ecoli_STxxx)"),
    isolates_of_interest: str = typer.Argument(..., help="Isolates of Interest (comma-separated, e.g., 2024-interest1,2024-interest2)"),
    reference: str = typer.Option("reference", "--reference", "-r", help="Reference (optional)"),
    st: int = typer.Option(00, "--st", "-s", help="Sequence Type (optional, default: 00)"),
    user: str = typer.Option("user", "--user", "-u", help="User (optional, default: user)"),
    species: str = typer.Option("genus species", "--species", "-sp", help="Species (optional, default: genus species)")
):
    isolates = isolates_of_interest.split(',')
    content = f"""
mkdir /home/mdu/analysis/sharepoint/2024/{job_id} && cd /home/mdu/analysis/sharepoint/2024/{job_id}/
"""
    for isolate in isolates:
        content += f"""
mdu search -id {isolate} --csv | csvtk transpose | csvtk pretty
"""
    content += f"""
ls .. | grep -i st{st}
ls -lhart .. | grep -i st{st}
ls ../../../meistertask/*/ | grep -i st{st}
ls -lhart ../../../meistertask/*/ | grep -i st{st}

mdu search -sp "{species}" -st {st} --count  # xx isolates
mdu search -sp "{species}" -st {st} > search.tab 
csvtk split -t -f "QC" search.tab
csvtk cut -t -f "ISOLATE" search-PASS.tab > list.txt
sed -i '1d' list.txt ## remove the first/header line
"""
    for isolate in isolates:
        content += f"""
grep {isolate} list.txt
"""
    content += f"""
mdu reads --idfile list.txt > reads.tab
mdu contigs --idfile list.txt --assemblier shovill > contigs.tab
wc -l reads.tab contigs.tab list.txt
grep {reference} contigs.tab

cp <path_from_above_grep_command> {reference}-shovill-ref.fa

tmux new -s {job_id}
conda activate bohra_nf
bohra run -i reads.tab -c contigs.tab -r {reference}-shovill-ref.fa -j {job_id} -p default --cpus 150 --proceed

mkdir -p /home/{user}/public_html/MDU/REPORTS/CPO/{job_id}/
cp /home/mdu/analysis/sharepoint/2024/{job_id}/report/report_default.html /home/{user}/public_html/MDU/REPORTS/CPO/{job_id}/

# Go to the link below to see the report: https://bioinformatics.mdu.unimelb.edu.au/~{user}/MDU/REPORTS/CPO/{job_id}/report_default.html
"""
    for isolate in isolates:
        content += f"""
csvtk tab2csv report/distances.tab | csvtk cut -F -f Isolate,"*{isolate}" | csvtk sort -k 2:n | head
"""
    content += f"""
# Runing bohra-pretty
mkdir bohra-pretty && cd bohra-pretty
python /home/himals/3_resources/github-repos/himal_scripts/reporting/cpos/update_cpo_report.py -u "Himal Shrestha" -j "{job_id}" 

echo "Isolate" > ../report/Focus_isolates.txt
"""
    for isolate in isolates:
        content += f"""
echo "{isolate}" >> ../report/Focus_isolates.txt
"""
    content += f"""
ca my_renv
Rscript /home/himals/3_resources/tools/scripts/bohra-pretty/render_report.R ../report/
cp cpo_report.html /home/{user}/public_html/MDU/REPORTS/CPO/{job_id}/

# Go to the link below to see the report: https://bioinformatics.mdu.unimelb.edu.au/~{user}/MDU/REPORTS/CPO/{job_id}/cpo_report.html
"""
    for isolate in isolates:
        content += f"""
python /home/himals/3_resources/github-repos/himal_scripts/bohra/isolate_plasmids.py ../report/plasmid.txt {isolate}
python /home/himals/3_resources/github-repos/himal_scripts/bohra/process_resistome_virulome.py ../report/resistome.txt {isolate}
python /home/himals/3_resources/github-repos/himal_scripts/bohra/process_resistome_virulome.py ../report/virulome.txt {isolate}
python /home/himals/3_resources/github-repos/himal_scripts/bohra/process_resistome_virulome.py ../report/typer.txt {isolate}
"""
    content += f"""
# ---
Job ID
{job_id}
Bohra link
https://bioinformatics.mdu.unimelb.edu.au/~{user}/MDU/REPORTS/CPO/{job_id}/report_default.html
Bohra-pretty link
https://bioinformatics.mdu.unimelb.edu.au/~{user}/MDU/REPORTS/CPO/{job_id}/cpo_report.html
Reference
{reference}-shovill-ref.fa
Isolate of Interest
{isolates_of_interest}
SNPs
<Fill up SNP details>
Resistome: Nothing of Note
Virulome: Nothing of Note
Plasmids: Nothing of Note
"""
    
    filename = f"run_me_{job_id}.txt"
    with open(filename, "w") as f:
        f.write(content.strip())
    
    print(f"{filename} has been generated.")

if __name__ == "__main__":
    typer.run(generate_run_me)
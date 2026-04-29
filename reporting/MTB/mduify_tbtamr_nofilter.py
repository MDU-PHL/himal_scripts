#!/usr/bin/env python3
import re, sys, pandas, numpy,json,pathlib

 
MOD_DIR = pathlib.Path(__file__).parent
CFG = json.load(open(f"{MOD_DIR / 'tbtamr.json'}", 'r'))
MDUIDREG = re.compile(r'(?P<id>[0-9]{4}-[0-9]{5,6})-?(?P<itemcode>.{1,2})?')

def assign_itemcode(mduid):
    m = MDUIDREG.match(mduid)
    try:
        itemcode = m.group('itemcode') if m.group('itemcode') else ''
    except AttributeError:
        itemcode = ''
    return itemcode

def assign_mduid(mduid):

    m = MDUIDREG.match(mduid)
    try:
        mduid = m.group('id')
    except AttributeError:
        mduid = mduid.split('/')[-1]
    return mduid

#Add space between lineage and x and capitalise Lineage. Accomodate multiple lineages.
def lin(x):
    line = x.split(';')
    res = []
    for l in line:
        pl = l[:7].capitalize() + ' ' + l[7:]
        res.append(pl)
    return ';'.join(res)

#tbtamr_linelist_report.csv file
df = pandas.read_csv(f"{sys.argv[1]}")
#standard_bacteria_qc.csv file
qc = pandas.read_csv(f"{sys.argv[2]}")
runid = f"{sys.argv[3]}"

#Rename columns
qc = qc.rename(columns={"ISOLATE":"Seq_id", "TEST_QC":"Quality"})
#Merge qc with tbtamr output to gain quality col
df = df.merge(qc[['Seq_id','Quality']], how = "left")
df = df.fillna('')
df['MDU sample ID'] = df['Seq_id'].apply(lambda x: assign_mduid(x))
df['Item code'] = df['Seq_id'].apply(lambda x:assign_itemcode(x))
fails = list(df[df['Quality'].str.contains('FAIL')]['Seq_id'])
df = df.replace('Not reportable','')
df['Phylogenetic lineage'] = df['Phylogenetic lineage'].apply(lambda x:lin(x))
df['Phylogenetic lineage'] = numpy.where(df['Seq_id'].isin(fails), 'Fail QC', df['Phylogenetic lineage'])

#Rename columns
df.rename(columns=lambda x: x.replace("mechanisms", "ResMech").
          replace("confidence", "Confidence"). replace("Db version", "Database version").
          replace("interpretation", "Interpretation"), inplace=True)

#Add 'No mechanisms available' to 'Susceptible' drugs
for col in df.columns:
    if 'Interpretation' in col:
        #Dynamically identify corresponding ResMech column
        resmech_col = col.replace('Interpretation', 'ResMech')
        if resmech_col in df.columns:
            #If Susceptible in Interpretation column, change ResMech col to No mechanisms identified.
            df.loc[df[col].str.contains('Susceptible', na=False), resmech_col] = "No mechanisms identified"

#Add in columns not present in new tbtamr output
old_cols = ["Cycloserine - ResMech", "Cycloserine - Interpretation",
            "Cycloserine - Confidence", "Para-aminosalicylic acid - ResMech",
            "Para-aminosalicylic acid - Interpretation",
            "Para-aminosalicylic acid - Confidence"]

for col in old_cols:
    df[col] = '' #Initialise with empty values

#Replace row values
df['Quality'] = df['Quality'].replace({'PASS': 'Pass QC', 'FAIL': 'Fail QC'})
df = df.replace('\_+', ' ', regex=True)#Replace _ with ' '

for c in CFG["cols"]:
    if 'Interpretation' in c or 'Confidence' in c:
        df[c] = numpy.where(df['Seq_id'].isin(fails), '', df[c])
    elif c not in ["MDU sample ID","Item code"] or 'ResMech' in c:
         df[c] = numpy.where(df['Seq_id'].isin(fails), 'Fail QC', df[c])
    
#Drop unwanted cols
df = df.drop(columns=['Seq_id', 'Date analysed'])
print(df)

#writer = pandas.ExcelWriter(f'MMS155_{runid}.xlsx')
df[CFG["cols"]].to_csv(f"{runid}_MMS155.csv", index = False)
#df[CFG["cols"]].to_excel(writer, sheet_name = "MMS155", index = False)
#writer.close()

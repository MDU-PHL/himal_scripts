import argparse
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jinja2 import Template

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate summary HTML from PASS.tab file with interactive tables and plots.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input PASS.tab file")
    parser.add_argument("-o", "--output", default="summary.html", help="Path to the output HTML file (default: summary.html)")
    parser.add_argument("-c", "--category", choices=["SPECIES", "ST", "SCHEME"], default="SPECIES",
                        help="Category for violin plots (default: SPECIES)")
    parser.add_argument("-a", "--additional", help="Additional columns to plot (comma-separated)")
    return parser.parse_args()

def create_frequency_table(df, column):
    freq = df[column].value_counts().reset_index()
    freq.columns = [column, 'Count']
    return freq.to_html(index=False, classes="display compact", table_id=f"{column.lower()}_table")

def create_time_series_plot(df):
    df['DATE_SEQ'] = pd.to_datetime(df['DATE_SEQ'])
    time_series = df.groupby('DATE_SEQ').size().reset_index(name='Count')
    fig = px.line(time_series, x='DATE_SEQ', y='Count', title='Number of Isolates Sequenced Over Time')
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

def create_violin_plot(df, y_column, category):
    fig = px.violin(df, x=category, y=y_column, box=True, points="all",
                    color=category)
    fig.update_traces(points="all", pointpos=0, jitter=0.05)
    fig.update_layout(title=f'{y_column} Distribution by {category}')
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

def create_plot(df, column, category):
    if pd.api.types.is_numeric_dtype(df[column]):
        return create_violin_plot(df, column, category)
    else:
        return create_frequency_table(df, column)

def create_full_table(df):
    return df.to_html(index=False, classes="display compact", table_id="full_table")

def main():
    args = parse_arguments()
    
    # Read the input file
    df = pd.read_csv(args.input, sep='\t')
    
    # Create frequency tables
    species_table = create_frequency_table(df, 'SPECIES')
    st_table = create_frequency_table(df, 'ST')
    scheme_table = create_frequency_table(df, 'SCHEME')
    
    # Create plots
    time_series_plot = create_time_series_plot(df)
    genome_size_plot = create_violin_plot(df, 'GENOME_SIZE', args.category)
    contigs_plot = create_violin_plot(df, 'CONTIGS', args.category)
    
    # Create additional plots
    additional_plots = []
    if args.additional:
        additional_columns = args.additional.split(',')
        for column in additional_columns:
            column = column.strip()
            if column in df.columns:
                additional_plots.append((column, create_plot(df, column, args.category)))
            else:
                print(f"Warning: Column '{column}' not found in the input file.")
    
    # Create full table
    full_table = create_full_table(df)
    
    # Create HTML template
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Summary Report</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.25/css/jquery.dataTables.css">
        <script type="text/javascript" charset="utf8" src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.js"></script>
        <style>
            .tab {
                overflow: hidden;
                border: 1px solid #ccc;
                background-color: #f1f1f1;
            }
            .tab button {
                background-color: inherit;
                float: left;
                border: none;
                outline: none;
                cursor: pointer;
                padding: 14px 16px;
                transition: 0.3s;
            }
            .tab button:hover {
                background-color: #ddd;
            }
            .tab button.active {
                background-color: #ccc;
            }
            .tabcontent {
                display: none;
                padding: 6px 12px;
                border: 1px solid #ccc;
                border-top: none;
            }
        </style>
        <script>
            $(document).ready(function() {
                $('.display').DataTable();
                
                $('.tablinks').click(function() {
                    var tabName = $(this).attr('data-tab');
                    $('.tabcontent').hide();
                    $('.tablinks').removeClass('active');
                    $('#' + tabName).show();
                    $(this).addClass('active');
                });
                
                // Show the first tab by default
                $('.tablinks:first').click();
            });
        </script>
    </head>
    <body>
        <h1>Summary MDU search Report</h1>
        
        <div class="tab">
            <button class="tablinks" data-tab="summary">Summary</button>
            <button class="tablinks" data-tab="fullTable">Full Table</button>
        </div>
        
        <div id="summary" class="tabcontent">
            <h2>Species Frequency</h2>
            {{ species_table }}
            
            <h2>ST Frequency</h2>
            {{ st_table }}
            
            <h2>Scheme Frequency</h2>
            {{ scheme_table }}
            
            <h2>Time Series Plot</h2>
            {{ time_series_plot }}
            
            <h2>Genome Size Distribution</h2>
            {{ genome_size_plot }}
            
            <h2>Contigs Distribution</h2>
            {{ contigs_plot }}
            
            {% for title, plot in additional_plots %}
            <h2>{{ title }}</h2>
            {{ plot }}
            {% endfor %}
        </div>
        
        <div id="fullTable" class="tabcontent">
            <h2>Full Data Table</h2>
            {{ full_table }}
        </div>
    </body>
    </html>
    """)
    
    # Render HTML
    html_output = template.render(
        species_table=species_table,
        st_table=st_table,
        scheme_table=scheme_table,
        time_series_plot=time_series_plot,
        genome_size_plot=genome_size_plot,
        contigs_plot=contigs_plot,
        additional_plots=additional_plots,
        full_table=full_table
    )
    
    # Write HTML to file
    with open(args.output, 'w') as f:
        f.write(html_output)
    
    print(f"Summary HTML generated: {args.output}")

if __name__ == "__main__":
    main()
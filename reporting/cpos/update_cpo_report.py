import argparse
import os
import re
import shutil

def copy_file_to_current_directory(file_path):
    # Copy the file to the current directory
    shutil.copy(file_path, os.getcwd())

def update_yaml(file_path, new_author, new_user_id, new_job_id):
    # Read the file content
    with open(file_path, 'r') as file:
        lines = file.readlines()
    
    # Update the author, user_id, and job_id values using regex
    lines = [re.sub(r'^author:.*', f'author: "{new_author}"', line) for line in lines]
    lines = [re.sub(r'^  user_id:.*', f'  user_id: "{new_user_id}"', line) for line in lines]
    lines = [re.sub(r'^  job_id:.*', f'  job_id: "{new_job_id}"', line) for line in lines]
    
    # Write the updated content back to the file
    with open(file_path, 'w') as file:
        file.writelines(lines)

def main():
    parser = argparse.ArgumentParser(description='Update YAML content in cpo_report.Rmd.')
    parser.add_argument('-u', '--user_name', required=True, help='User name, e.g., "John Doe"')
    parser.add_argument('-j', '--job_id', required=True, help='Job ID, e.g., "XX_20240101_ecoli_ST123"')
    parser.add_argument('-f', '--file_path', default='/home/himals/3_resources/tools/scripts/bohra-pretty/cpo_report.Rmd', help='Path to the cpo_report.Rmd file (default: /home/himals/3_resources/tools/scripts/bohra-pretty/cpo_report.Rmd)')
    
    args = parser.parse_args()
    
    # Replace spaces with underscores for the author
    new_author = args.user_name.replace(" ", "_")
    new_user_id = args.user_name
    new_job_id = args.job_id
    file_path = os.path.abspath(args.file_path)
    
    # Copy the file to the current directory
    copy_file_to_current_directory(file_path)
    
    # Update the file in the current directory
    local_file_path = os.path.join(os.getcwd(), os.path.basename(file_path))
    update_yaml(local_file_path, new_author, new_user_id, new_job_id)

if __name__ == "__main__":
    main()

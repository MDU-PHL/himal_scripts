# himal_scripts

`himal_scripts` is a collection of custom scripts for processing MDU data. 

---

## Usage

To use these scripts, you need to clone this repository and make the scripts executable:

```bash
git clone https://github.com/MDU-PHL/himal_scripts.git
cd himal_scripts
chmod +x *.sh
```

### run_mlst

This script checks the MLST outputs for a sample with genomes assembled using `spades`, `shovill` and `skesa`. It takes two arguments: the `run ID` and the `sample ID`.

Example:

```bash
conda activate /home/khhor/conda/envs/mlst/
./run_mlst <runid> <sampleid>
```

This will output the MLST scheme using genomes from each assembly method.

### test-hicap-run.sh

This script runs hicap on a set of samples. It takes one argument: a file containing the sample IDs, one per line.

Before running this script, you need to create a new folder for the test run and copy the script to that folder. You also need to activate the conda environment for hicap:

```bash
mkdir 231205-test
cd 231205-test
cp /home/himals/3_resources/github-repos/himal_scripts/test-hicap-run.sh test-hicap-run.sh
conda activate /home/himals/.conda/envs/hicap_dev
```

Then, you need to create a file called `sample_ids` and paste the sample IDs in the file:

```bash
nano sample_ids
```

Finally, you can run the script with the following command:

```bash
./test-hicap-run.sh sample_ids
```

This will run hicap on each sample and generate a folder called `hicap_ssummary` files in the current directory, which contains the hicap results for each sample.


## Contributing

If you want to contribute to this project, please follow these steps:

- Fork this repository and create a new branch for your feature or bug fix.
- Make your changes and commit them with a clear and descriptive message.
- Push your branch to your fork and open a pull request to the main branch.
- Wait for a review and feedback from the maintainer.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/MDU-PHL/himal_scripts?tab=MIT-1-ov-file#readme) file for details.

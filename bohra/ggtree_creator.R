#!/usr/bin/env Rscript

# phylo_tree_creator.R
# A script to draw and save a phylogenetic tree from a Newick file

# Load required libraries
suppressPackageStartupMessages({
  library(ape)
  library(ggtree)
  library(phytools)
  library(optparse)
  library(ggplot2)
})

# Parse command line arguments
option_list <- list(
  make_option(c("-i", "--input"), type="character", default=NULL, 
              help="Input Newick file", metavar="FILE"),
  make_option(c("-o", "--output"), type="character", default="phylo_tree.png", 
              help="Output file name [default=%default]", metavar="FILE"),
  make_option(c("-f", "--focus"), type="character", default=NULL, 
              help="Comma-separated list of focus isolate names", metavar="STRING"),
  make_option(c("-w", "--width"), type="numeric", default=10, 
              help="Width of output image [default=%default]"),
  make_option(c("--height"), type="numeric", default=14, 
              help="Height of output image [default=%default]")
)

opt_parser <- OptionParser(option_list=option_list, 
                          description="Create a phylogenetic tree from a Newick file")
opt <- parse_args(opt_parser)

# Check if input file is provided
if (is.null(opt$input)) {
  stop("Input file is required. Use -i or --input to specify the Newick file.")
}

# Process the input Newick file
cat("Reading tree file:", opt$input, "\n")
if (!file.exists(opt$input)) {
  stop("Input file does not exist.")
}

# Read the tree
tree <- read.tree(opt$input)

# Ensure isolate names in the tree follow consistent format
tree$tip.label <- gsub("\\.", "-", tree$tip.label)

# Process focus isolates if provided
focus_isolates <- NULL
if (!is.null(opt$focus)) {
  focus_isolates <- strsplit(opt$focus, ",")[[1]]
  focus_isolates <- gsub("\\.", "-", focus_isolates)
  cat("Focus isolates:", paste(focus_isolates, collapse=", "), "\n")
}

# Create tree data
tree_data <- data.frame(Isolate = tree$tip.label)

# Add Shape column to indicate focus isolates
if (!is.null(focus_isolates)) {
  tree_data$Shape <- ifelse(tree_data$Isolate %in% focus_isolates, "Focus", "Other")
} else {
  tree_data$Shape <- "Other"
}

# Re-root the tree at the midpoint
cat("Re-rooting tree at midpoint...\n")
reroot_phylo_tree <- phytools::midpoint.root(tree)

# Update the tree plot 
cat("Generating tree plot...\n")
phylo_tree <- ggtree(reroot_phylo_tree) %<+% tree_data +
  geom_tippoint(aes(shape = Shape, size = Shape, color = Shape, alpha = Shape)) +
  geom_text2(aes(subset = (as.numeric(label) > 80), label = label), 
           size = 1.5, hjust = 1.75, vjust = -1.0, check_overlap = TRUE) +
  geom_tiplab(size = 2, align = FALSE)

# Add shapes, colors, and transparency for focus isolates
if (!is.null(focus_isolates)) {
  phylo_tree <- phylo_tree +
    scale_shape_manual(values = c("Focus" = 18, "Other" = 20)) +  # Diamond for focus, circle for others
    scale_size_manual(values = c("Focus" = 4, "Other" = 1)) +     # Larger size for focus isolates
    scale_color_manual(values = c("Focus" = "red", "Other" = "black")) +  # Red color for focus isolates
    scale_alpha_manual(values = c("Focus" = 0.7, "Other" = 1))     # 70% transparency for focus isolates
}
# Save the plot to a file
cat("Saving plot to:", opt$output, "\n")
ggsave(opt$output, plot = phylo_tree, width = opt$width, height = opt$height)
cat("Done!\n")
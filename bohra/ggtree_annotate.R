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
  library(tidyverse)
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
              help="Height of output image [default=%default]"),
  make_option(c("-a", "--annotation"), type="character", default=NULL,
              help="Path to annotation CSV file", metavar="FILE"),
  make_option(c("-c", "--columns"), type="character", default=NULL,
              help="Comma-separated list of columns to include in heatmap", metavar="STRING"),
  make_option(c("--align"), type="logical", default=FALSE, action="store_true",
              help="Align tip labels [default=%default]"),
  make_option(c("--color_column"), type="character", default=NULL,
              help="Column name in annotation file to use for tip label colors", metavar="STRING"),
  make_option(c("--match_column"), type="character", default=NULL,
              help="Column name in annotation file to match with tree leaf labels. Default is first column", metavar="STRING")
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
# tree$tip.label <- gsub("\\.", "-", tree$tip.label)

# Process focus isolates if provided
focus_isolates <- NULL
if (!is.null(opt$focus)) {
  focus_isolates <- strsplit(opt$focus, ",")[[1]]
  focus_isolates <- gsub("\\.", "-", focus_isolates)
  cat("Focus isolates:", paste(focus_isolates, collapse=", "), "\n")
}

# Create base tree data
tree_data <- data.frame(Isolate = tree$tip.label)

# Add Shape column to indicate focus isolates
if (!is.null(focus_isolates)) {
  tree_data$Shape <- ifelse(tree_data$Isolate %in% focus_isolates, "Focus", "Other")
} else {
  tree_data$Shape <- "Other"
}

# Read and process annotation file if provided
if (!is.null(opt$annotation)) {
  cat("Reading annotation file:", opt$annotation, "\n")
  if (!file.exists(opt$annotation)) {
    stop("Annotation file does not exist.")
  }
  
  # Read annotation data
  annot_data <- read.csv(opt$annotation, stringsAsFactors = FALSE)
  
  # Add debug info to show all column names
  cat("DEBUG: Available columns in annotation file:\n")
  cat(paste(colnames(annot_data), collapse=", "), "\n")

  # Check if match column is specified and exists in the annotation file
  cat("match_column provided: ", opt$match_column, "\n")

  # Identify the ID column - use match-column if provided, otherwise use first column
  if (!is.null(opt$match_column) && opt$match_column %in% colnames(annot_data)) {
    id_col <- opt$match_column
    cat("Using column '", id_col, "' for matching tree tips with annotation data\n", sep="")
  } else {
    id_col <- colnames(annot_data)[1]
    if (!is.null(opt$match_column) && !opt$match_column %in% colnames(annot_data)) {
      cat("WARNING: Specified match column '", opt$match_column, "' not found in annotation file.\n", sep="")
      cat("Using first column '", id_col, "' instead.\n", sep="")
    } else {
      cat("Using first column '", id_col, "' for matching tree tips with annotation data\n", sep="")
    }
  }
  
  # Check if all tree tips are present in the annotation file
  missing_tips <- tree$tip.label[!tree$tip.label %in% annot_data[[id_col]]]
  
  if (length(missing_tips) > 0) {
    cat("ERROR: The following tips are missing in the annotation file:\n")
    cat(paste(missing_tips, collapse="\n"), "\n")
    stop("Please add the missing tips to the annotation file or check if the correct match column is specified.")
  }
  
  # Ensure annot_data has the same IDs and order as the tree tips
  annot_data <- annot_data[match(tree$tip.label, annot_data[[id_col]]), ]
  
  # Merge the annotation data with the base tree data
  tree_data <- cbind(tree_data, annot_data[, !colnames(annot_data) %in% c("Isolate", "Shape")])
}

# Re-root the tree at the midpoint
cat("Re-rooting tree at midpoint...\n")
reroot_phylo_tree <- phytools::midpoint.root(tree)

# Update the tree plot 
cat("Generating tree plot...\n")
phylo_tree <- ggtree(reroot_phylo_tree) %<+% tree_data +
  geom_tippoint(aes(shape = Shape, size = Shape, color = Shape, alpha = Shape)) +
  geom_text2(aes(subset = (as.numeric(label) > 80), label = label), 
           size = 1.5, hjust = 1.75, vjust = -1.0, check_overlap = TRUE)

# Add tip labels with optional alignment and coloring
if (!is.null(opt$color_column) && opt$color_column %in% colnames(tree_data)) {
  # Get unique values of the color column to create a color palette
  unique_colors <- unique(tree_data[[opt$color_column]])
  color_count <- length(unique_colors)
  
  # Create a color palette - using a predefined palette or generating one
  if (color_count <= 8) {
    # For small number of categories, use a distinct palette
    color_palette <- RColorBrewer::brewer.pal(max(3, color_count), "Set1")
    if (color_count < 3) color_palette <- color_palette[1:color_count]
  } else {
    # For larger number of categories, generate colors
    color_palette <- scales::hue_pal()(color_count)
  }
  
  # Name the color palette with the unique color values
  names(color_palette) <- unique_colors
  
  # Set offset for labels
  offset <- 0.0002
  
  # Add tip labels with fill color and black text
  phylo_tree <- phylo_tree + 
    geom_tiplab(aes(fill = .data[[opt$color_column]]), 
                color = "black",  # Text color
                geom = "label",   # Use label geom for filled background
                label.size = 0.05, # Border size
                alpha = 0.7,      # Transparency
                align = opt$align,
                offset = offset,
                size = 2) +
    # Add color scales for both fill and color
    scale_fill_manual(values = color_palette, name = opt$color_column) +
    scale_color_manual(values = color_palette, name = opt$color_column, guide = "none")
} else {
  phylo_tree <- phylo_tree + 
    geom_tiplab(align = opt$align, 
                size = 2, 
                linesize = ifelse(opt$align, 0.3, 0))
}

# Add shapes, colors, and transparency for focus isolates
if (!is.null(focus_isolates)) {
  phylo_tree <- phylo_tree +
    scale_shape_manual(values = c("Focus" = 18, "Other" = 20)) +  # Diamond for focus, circle for others
    scale_size_manual(values = c("Focus" = 4, "Other" = 1)) +     # Larger size for focus isolates
    scale_color_manual(values = c("Focus" = "red", "Other" = "black")) +  # Red color for focus isolates
    scale_alpha_manual(values = c("Focus" = 0.7, "Other" = 1))     # 70% transparency for focus isolates
}

# Add heatmap if columns are specified
if (!is.null(opt$columns) && !is.null(opt$annotation)) {
  heatmap_cols <- strsplit(opt$columns, ",")[[1]]
  
  # Check if all columns exist in the annotation file
  missing_cols <- heatmap_cols[!heatmap_cols %in% colnames(annot_data)]
  if (length(missing_cols) > 0) {
    cat("WARNING: The following columns specified for the heatmap are missing in the annotation file:\n")
    cat(paste(missing_cols, collapse=", "), "\n")
    heatmap_cols <- heatmap_cols[heatmap_cols %in% colnames(annot_data)]
    if (length(heatmap_cols) == 0) {
      cat("No valid columns for heatmap. Skipping heatmap generation.\n")
    } else {
      cat("Proceeding with available columns:", paste(heatmap_cols, collapse=", "), "\n")
    }
  }
  
 if (length(heatmap_cols) > 0) {
  # Create a subset of the annotation data with only the columns for the heatmap
  heatmap_data <- annot_data[, c(id_col, heatmap_cols)]
  
  # Reset row names before setting them from a column
  rownames(heatmap_data) <- NULL
  
  # Now convert the column to row names
  heatmap_data <- column_to_rownames(heatmap_data, var = id_col)
  
  # Determine if the data is categorical or numeric
  # Check if any column contains non-numeric data
  is_categorical <- sapply(heatmap_data, function(x) {
    !is.numeric(x) || is.factor(x)
  })
  
  # Add the heatmap to the tree
  offset <- 0.003  # Offset to separate tree from heatmap
  phylo_tree <- gheatmap(phylo_tree, heatmap_data, offset = offset, width = 0.02 * length(heatmap_cols))
  
  # Apply appropriate color scale based on data type
  if (any(is_categorical)) {
    # For categorical data, use the discrete version of viridis
    phylo_tree <- phylo_tree + scale_fill_viridis_d(option = "viridis")
  } else {
    # For numeric data, use the continuous version of viridis
    phylo_tree <- phylo_tree + scale_fill_viridis_c(option = "viridis")
  }
  }
}


# Save the plot to a file
cat("Saving plot to:", opt$output, "\n")
ggsave(opt$output, plot = phylo_tree, width = opt$width, height = opt$height)
cat("✔Done!\n")
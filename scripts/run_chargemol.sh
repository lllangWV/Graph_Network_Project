#!/bin/bash

# Parent directory path
PARENT_DIR="/users/lllang/SCRATCH/projects/crystal_graph/data/raw/materials_project/calculations/MaterialsData"

# Loop through all directories in the parent directory
for dir in "$PARENT_DIR"/*; do
    if [ -d "$dir" ]; then
        # Change to the directory
        echo "$dir/chargemol"
        cd "$dir/chargemol"

        
        
        # Check if run.slurm exists in the directory
        if [ -f "run.slurm" ]; then
            # Submit the SLURM job
            sbatch run.slurm
        else
            echo "run.slurm not found in $dir"
        fi
    fi
done

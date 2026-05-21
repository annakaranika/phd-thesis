#!/bin/bash

# Exit on any error
set -e

# Pass --clear-biber-cache to delete the biber PAR cache before running.
# Use this if citations show as [0] or biber crashes silently.
if [[ "$*" == *--clear-biber-cache* || "$*" == *-c* ]]; then
    echo "Clearing biber cache..."
    rm -rf /var/folders/*/*/T/par-"$(id -un)"
fi

# Pass --draft (or -d) for a fast single-pass compile.
# Skips \printbibliography (citations still resolve from the cached .bbl).
# Run the full compile at least once before using --draft.
if [[ "$*" == *--draft* || "$*" == *-d* ]]; then
    echo "Draft mode: single pass, bibliography skipped."
    lualatex -interaction=nonstopmode -jobname=thesis '\def\draftmode{1}\input{thesis}'
    exit 0
fi

lualatex -interaction=nonstopmode thesis.tex
biber thesis
lualatex -interaction=nonstopmode thesis.tex
lualatex -interaction=nonstopmode thesis.tex

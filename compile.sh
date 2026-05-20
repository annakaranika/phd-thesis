#!/bin/bash

# Exit on any error
set -e

# Pass --clear-biber-cache to delete the biber PAR cache before running.
# Use this if citations show as [0] or biber crashes silently.
if [[ "$*" == *--clear-biber-cache* || "$*" == *-c* ]]; then
    echo "Clearing biber cache..."
    rm -rf /var/folders/*/*/T/par-"$(id -un)"
fi

lualatex -interaction=nonstopmode thesis.tex
biber thesis
lualatex -interaction=nonstopmode thesis.tex
lualatex -interaction=nonstopmode thesis.tex
biber thesis
lualatex -interaction=nonstopmode thesis.tex

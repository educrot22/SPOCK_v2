#!/bin/bash

# Build the documentation
sphinx-build -b html docs/ docs/build/html

# Copy the built HTML files to the docs root
cp -r docs/build/html/* ./docs

# Clean up the build directory (optional)
#rm -rf docs/build/html

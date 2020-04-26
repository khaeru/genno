#!/bin/sh

NAME=genno

# Make a directory for the new code
mkdir -p $NAME/tests/data

# Preserve files in new locations

# Code
if [ -d ixmp/reporting ]; then
  mv ixmp/reporting/* $NAME/
fi

# Tests and data
if [ -e tests/test_reporting.py ]; then
  mv tests/test_reporting* $NAME/tests/
  mv tests/data/report* $NAME/tests/data/
elif [ -d ixmp/tests/reporting ]; then
  mv ixmp/tests/reporting/* $NAME/tests/
  mv ixmp/tests/data/report* $NAME/tests/data/
fi

# Documentation
if [ -e doc/source/reporting.rst ]; then
  mv doc/source/reporting.rst doc/index.rst
fi

# Remove everything not preserved
#
# find is used to match all names, including those that
# no longer exist in the current tree

# Directories
#
# USE CARE when editing this line; could remove '.' or
# '.git' unintentionally
find . \
  -mindepth 1 -maxdepth 1 \
  -type d ! -regex "\./\(.git[^h]*\|doc\|$NAME\)" \
  -exec rm -r {} \;

# Other files at the top level
find . -maxdepth 1 -type f -delete

# Files in doc/ that are not index.rst
if [ -d doc ]; then
  rm -rf doc/source
  find doc/* ! -name index.rst -delete
fi

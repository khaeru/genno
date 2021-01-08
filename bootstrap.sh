#!/bin/sh

# Bootstrap the repository by importing ixmp.reporting,
# preserving its git history
#
# Requires git filter-repo; install using:
#
#   $ pip install git-filter-repo

# Echo commands for debugging
set -x

# Name and repo of the current package
NAME=genno
REPO=git@github.com:khaeru/$NAME.git

# Name of the other package
OTHER=ixmp
OTHER_REPO=git@github.com:iiasa/$OTHER.git

# Branch to create
BRANCH=$OTHER-filtered

# Echo a message on how to restart
echo "To undo, run:"
echo "  $ cd .. && rm -rf $NAME && git clone $REPO && cd $NAME"

# Store the initial commit
BASE=$(git rev-list --max-parents=0 HEAD)
[ -n "$BASE" ] || exit 1

# Add and fetch remote
git remote add --fetch $OTHER $OTHER_REPO

# Check out as a new local branch
git checkout -b $BRANCH $OTHER/master

# Use filter-repo tool
# - Only filter the $OTHER/master branch
# - Rename several paths:
#   - tests/ is an old location; $OTHER/tests/ is recent.
#   - The existing doc/index.rst is moved to avoid a conflict.
#   - doc/source is an old location; doc/ is recent.
git filter-repo \
  --refs $BRANCH --force --debug \
  --path-rename $OTHER/reporting:$NAME \
  --path-rename tests/test_reporting:$NAME/tests \
  --path-rename tests/data:$NAME/tests/data \
  --path-rename $OTHER/tests/reporting:$NAME/tests \
  --path-rename $OTHER/tests/data:$NAME/tests/data \
  --path-rename doc/index.rst:doc/index-$OTHER.rst \
  --path-rename doc/source/reporting.rst:doc/index.rst \
  --path-rename doc/reporting.rst:doc/index.rst

# Keep only a subset of files and directories
git filter-repo \
  --refs $BRANCH --force --debug \
  --path $NAME --path doc/index.rst

# Specifically remove non-reporting test data
git filter-repo \
  --refs $BRANCH --force --debug \
  --invert-paths \
  --path-regex "^$NAME/tests/data/[^r].*$"

# Store the initial commit of OTHER
OTHER_BASE=$(git rev-list --max-parents=0 $BRANCH)
[ -n "$OTHER_BASE" ] || exit 1

# Graft the $OTHER/master branch onto the first commit of
# master, so the two share a common initial commit
git replace --graft $OTHER_BASE $BASE
git filter-repo --force

# After this, inspect the history, and merge into master

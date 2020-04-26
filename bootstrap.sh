#!/bin/sh

# Bootstrap the repository by importing ixmp.reporting,
# preserving its git history

# Hide a copy of filter.sh in .git to avoid tree changes
cp filter.sh .git/

# Add and fetch remote
git remote add -f ixmp git@github.com:khaeru/ixmp.git
git checkout -b ixmp-import ixmp/issue/191

# Extract the reporting code, cleaning history
git filter-branch \
  --force \
  --tree-filter "$PWD/.git/filter.sh" \
  --prune-empty

# After this, inspect the history, and push as the new
# 'master' branch

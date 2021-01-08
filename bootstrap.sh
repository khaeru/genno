#!/bin/sh

# Bootstrap the repository by importing ixmp.reporting,
# preserving its git history

OTHER=ixmp

# Hide a copy of filter.sh in .git to avoid tree changes
cp filter.sh .git/

# Add and fetch remote
git remote add -f $OTHER git@github.com:iiasa/$OTHER.git
git checkout -b $OTHER-import $OTHER/master

# Extract the reporting code, cleaning history
git filter-branch \
  --force \
  --tree-filter "$PWD/.git/filter.sh" \
  --prune-empty

# After this, inspect the history, and push as the new
# 'master' branch

#!/bin/sh

# Undo and erase the effects of bootstrap.sh

git checkout master
git branch -D ixmp-import
git gc

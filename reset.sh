#!/bin/sh

# Undo and erase the effects of bootstrap.sh

OTHER=ixmp

git checkout master
git branch -D $OTHER-import
git gc

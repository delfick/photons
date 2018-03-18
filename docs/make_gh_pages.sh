#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [[ ! -d $DIR/gh-pages ]]; then
    git clone git@github.com:delfick/photons-core.git $DIR/gh-pages
else
    (
    cd $DIR/gh-pages
    git fetch origin
    )
fi

cd $DIR/gh-pages
git checkout gh-pages || exit 1
git reset --hard origin/gh-pages

$DIR/docs build_docs fresh || exit 1

rsync -avzr --delete --filter 'protect .git/' $DIR/res/result/ $DIR/gh-pages/

cd $DIR/gh-pages
touch .nojekyll
git status

echo "Up to you to commit and push"

#!/bin/bash

echo "Check if checkout on master"
CURRENT_BRANCH=$(git rev-parse --symbolic-full-name --abbrev-ref HEAD)

echo "Current branch is: $CURRENT_BRANCH"

if [ $CURRENT_BRANCH != "master" ]; then
    echo "Not checked out master, aborting..."
    exit 1
fi

echo "Creating new version"

FILE=pyproject.toml
CURRENT_VERSION=$(cat $FILE | grep version | awk '{print $3}' | cut -d '"' -f 2)
TO_UPDATE=(
    chart/Chart.yaml
    .github/workflows/main.yml
)

echo "Current version is: $CURRENT_VERSION. Enter new version:"

read NEW_VERSION

echo "New version is: $NEW_VERSION"

for file in "${TO_UPDATE[@]}"
do
    echo "Patching $file ..."
    sed -i '' "s/$CURRENT_VERSION/$NEW_VERSION/g" $file
    git add $file
done

git commit -m "Releasing v$NEW_VERSION"

git push

git tag -a v$NEW_VERSION -m "Release v$NEW_VERSION"

git push origin v$NEW_VERSION
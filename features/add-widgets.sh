#!/usr/bin/env bash
set -e

echo "Running feature script: add-widgets"
# For testing we'll create a marker file
mkdir -p /tmp/narchs-features
echo "widgets-installed" > /tmp/narchs-features/add-widgets.txt

echo "add-widgets completed"

#!/bin/bash

# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

# Build-time data loading script for Docker
# This script loads the bhume.txt data into the database during Docker build

set -e

echo "=== Build-time Data Loading ==="
echo "Loading BhuMe blog data into database..."

# Change to the application directory
cd /app

# Ensure data directory exists
mkdir -p /app/data/db

# Load the bhume.txt data using db_load tool
# This uses the qdrant_local endpoint configured in config_retrieval.yaml
echo "Loading data/bhume.txt as site 'bhume'"

# Run the db_load command
python -m tools.db_load data/bhume.txt bhume

# Verify the data was loaded
echo "=== Data Loading Complete ==="
echo "BhuMe blog data has been loaded into the database"
echo "The 'bhume' site should now be available via /sites endpoint"
echo "=================================================" 
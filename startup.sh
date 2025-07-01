#!/bin/bash

# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

# Startup script for Cloud Run deployment with runtime data loading

set -e

echo "=== NLWeb Cloud Run Startup ==="
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Directory contents:"
ls -la

# Check if OPENAI_API_KEY is available
if [ -z "$OPENAI_API_KEY" ]; then
    echo "WARNING: OPENAI_API_KEY not found. Data loading will be skipped."
    echo "The application will start but search functionality may not work."
else
    echo "OPENAI_API_KEY found. Proceeding with data loading..."
    
    # Load BhuMe blog data if not already loaded
    echo "=== Runtime Data Loading ==="
    echo "Loading BhuMe blog data into database..."
    
    # Ensure data directory exists
    mkdir -p /app/data/db
    
    # Load the bhume.txt data using db_load tool
    echo "Loading data/bhume.txt as site 'bhume'"
    python -m tools.db_load data/bhume.txt bhume
    
    echo "=== Data Loading Complete ==="
    echo "BhuMe blog data has been loaded into the database"
    echo "The 'bhume' site should now be available via /sites endpoint"
    echo "================================================="
fi

# Start the web server
echo "=== Starting Web Server ==="
echo "Starting NLWeb application on port ${PORT:-8080}..."

# Start the application
python -m webserver.WebServer
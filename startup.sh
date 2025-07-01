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
DATA_LOADING_SUCCESS=false
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
    
    # Use set +e to prevent the script from exiting if data loading fails
    set +e
    python -m tools.db_load data/bhume.txt bhume
    DATA_LOAD_EXIT_CODE=$?
    set -e
    
    if [ $DATA_LOAD_EXIT_CODE -eq 0 ]; then
        echo "=== Data Loading Complete ==="
        echo "BhuMe blog data has been loaded into the database"
        echo "The 'bhume' site should now be available via /sites endpoint"
        DATA_LOADING_SUCCESS=true
    else
        echo "=== Data Loading Failed ==="
        echo "Exit code: $DATA_LOAD_EXIT_CODE"
        echo "The application will continue to start but search functionality may not work"
    fi
    echo "================================================="
fi

# Start the web server regardless of data loading success
echo "=== Starting Web Server ==="
echo "Starting NLWeb application on port ${PORT:-8080}..."
echo "Data loading success: $DATA_LOADING_SUCCESS"

# Start the application
exec python -m webserver.WebServer
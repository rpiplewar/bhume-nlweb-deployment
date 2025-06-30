#!/bin/bash

# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

# Startup script for NLWeb with automatic data loading
# This script starts the web server and loads initial data if needed

set -e

echo "=== NLWeb Startup Script ==="
echo "Starting NLWeb with automatic data loading..."

# Change to the application directory
cd /app

# Check if data has already been loaded
DATA_LOADED_FLAG="/app/data/.bhume_loaded"

if [ ! -f "$DATA_LOADED_FLAG" ]; then
    echo "=== Loading Initial Data ==="
    echo "Loading BhuMe blog data..."
    
    # Wait a moment for the application to be ready
    sleep 2
    
    # Load the bhume.txt data
    if [ -f "/app/data/bhume.txt" ]; then
        echo "Found bhume.txt, loading data..."
        python -m tools.db_load /app/data/bhume.txt bhume --batch-size 50
        
        if [ $? -eq 0 ]; then
            echo "Successfully loaded BhuMe data!"
            # Create flag file to prevent reloading
            touch "$DATA_LOADED_FLAG"
            echo "$(date): BhuMe data loaded successfully" > "$DATA_LOADED_FLAG"
        else
            echo "Failed to load BhuMe data, but continuing with startup..."
        fi
    else
        echo "Warning: bhume.txt not found in /app/data/"
    fi
    
    echo "=== Data Loading Complete ==="
else
    echo "=== Data Already Loaded ==="
    echo "BhuMe data already loaded (flag file exists)"
    cat "$DATA_LOADED_FLAG"
fi

echo "=== Starting Web Server ==="
echo "Starting NLWeb application on port 8080..."

# Start the main application
exec python app-file.py 
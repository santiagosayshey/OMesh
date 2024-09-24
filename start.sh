#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Run the deploy script
echo "Running deploy script..."
./deploy.sh

# Build and start Docker containers
echo "Building and starting Docker containers..."
docker-compose down
docker-compose up --build

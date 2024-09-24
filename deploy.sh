#!/bin/bash

# Set the paths
ROOT_DIR="$(pwd)"                         # Root directory of your project
FRONTEND_DIR="$ROOT_DIR/frontend"         # Frontend directory
BUILD_DIR="$FRONTEND_DIR/build"           # Build output directory
CLIENT_DIR="$ROOT_DIR/client"             # Flask application directory
FLASK_TEMPLATES_DIR="$CLIENT_DIR/templates"
FLASK_STATIC_DIR="$CLIENT_DIR/static"

# Navigate to the frontend directory
cd "$FRONTEND_DIR" || exit

# Install dependencies if needed
# Uncomment the following line if you need to install dependencies
# npm install

# Build the React application
echo "Building the React application..."
npm run build

# Check if the build was successful
if [ $? -ne 0 ]; then
  echo "React build failed. Exiting."
  exit 1
fi

# Ensure the Flask directories exist
mkdir -p "$FLASK_TEMPLATES_DIR"
mkdir -p "$FLASK_STATIC_DIR"

# Remove old static files
echo "Cleaning old static files..."
rm -rf "$FLASK_STATIC_DIR"/*

# Copy index.html to Flask templates
echo "Copying index.html to Flask templates..."
cp "$BUILD_DIR/index.html" "$FLASK_TEMPLATES_DIR/"

# Copy static assets to Flask static directory
echo "Copying static assets to Flask static directory..."
cp -r "$BUILD_DIR/assets" "$FLASK_STATIC_DIR/"

# Optional: Copy other static files if necessary
# cp "$BUILD_DIR/vite.svg" "$FLASK_STATIC_DIR/"

echo "Deployment completed successfully."

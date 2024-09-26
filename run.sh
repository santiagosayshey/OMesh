#!/bin/bash

set -e

function usage() {
    echo "Usage: $0 [start|rebuild] [options]"
    echo "Options:"
    echo "  --detach                 Run containers in detached mode"
    echo "  --info                   Retrieve server information from volumes"
    echo "  --add-key <path>         Add a public key to the neighbours volume"
    echo "  --help                   Display this help message"
    exit 1
}

# Default values
ACTION=""
DETACH_MODE=""
INFO_MODE=0
ADD_KEY_PATH=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        start)
            ACTION="start"
            shift
            ;;
        rebuild)
            ACTION="rebuild"
            shift
            ;;
        --detach)
            DETACH_MODE="--detach"
            shift
            ;;
        --info)
            INFO_MODE=1
            shift
            ;;
        --add-key)
            ADD_KEY_PATH="$2"
            if [[ -z "$ADD_KEY_PATH" ]]; then
                echo "Error: --add-key requires a path to the public key file"
                exit 1
            fi
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            ;;
    esac
done

if [[ -z "$ACTION" ]]; then
    echo "Error: You must specify 'start' or 'rebuild'"
    usage
fi

# Function to add public key to neighbours volume
function add_public_key() {
    if [[ -f "$ADD_KEY_PATH" ]]; then
        docker cp "$ADD_KEY_PATH" olaf_server:/app/server/neighbours/
        echo "Public key added to neighbours volume."
    else
        echo "Error: File '$ADD_KEY_PATH' does not exist."
        exit 1
    fi
}

# Function to retrieve server info
function get_server_info() {
    echo "Retrieving server information..."
    docker exec olaf_server sh -c 'cat /app/server/config/server_public_key.pem' > server_public_key.pem
    SERVER_ADDRESS=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' olaf_server)
    SERVER_PORT=$(docker port olaf_server 8765 | cut -d: -f2)
    HTTP_PORT=$(docker port olaf_server 8081 | cut -d: -f2)
    echo "Server Address: $SERVER_ADDRESS"
    echo "Server Port: $SERVER_PORT"
    echo "HTTP Port: $HTTP_PORT"
    echo "Public Key saved to server_public_key.pem"
}

# Start or rebuild containers
if [[ "$ACTION" == "rebuild" ]]; then
    echo "Rebuilding containers and removing volumes..."
    docker-compose -f docker-compose-integration.yml down -v
    docker-compose -f docker-compose-integration.yml build
fi

if [[ "$INFO_MODE" -eq 1 ]]; then
    get_server_info
    exit 0
fi

echo "Starting containers..."
docker-compose -f docker-compose-integration.yml up $DETACH_MODE

if [[ -n "$ADD_KEY_PATH" ]]; then
    add_public_key
fi

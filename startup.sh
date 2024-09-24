#!/bin/bash

echo "Starting Docker Compose services..."
docker-compose up -d

echo "Waiting for services to start..."
sleep 1  # Adjust as necessary

echo -e "\nWelcome to OMesh!"

# Function to display the status table
display_status() {
  clear
  echo -e "\nWelcome to OMesh!\n"
  echo "Press [Ctrl+C] to stop monitoring."
  printf "%-15s %-20s %-10s %-30s\n" "SERVICE" "CONTAINER ID" "STATUS" "URL"
  printf "%-15s %-20s %-10s %-30s\n" "-------" "------------" "------" "---"

  services=$(docker-compose ps --services)

  for service in $services; do
    container_id=$(docker-compose ps -q $service)
    status=$(docker inspect -f '{{.State.Status}}' $container_id)
    ports=$(docker port $container_id)
    url=""

    if [[ ! -z "$ports" ]]; then
      # Extract the port mapping
      host_port=$(echo $ports | awk -F'[:]' '{print $2}')
      container_port=$(echo $ports | awk -F'->' '{print $2}')
      url="http://localhost:$host_port"
    fi

    printf "%-15s %-20s %-10s %-30s\n" "$service" "${container_id:0:12}" "$status" "$url"
  done

  echo -e "\nRecent Logs (Last 5 entries per service):\n"
  
  for service in $services; do
    echo "Service: $service"
    docker-compose logs --tail=5 $service
    echo ""
  done
}

# Run the status display in a loop
while true; do
  display_status
  sleep 50  # Update interval in seconds
done

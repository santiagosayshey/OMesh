# OMesh: OLAF/Neighbourhood Protocol Implementation

This project implements the OLAF/Neighbourhood protocol for secure, decentralized communication.

## High-Level Classes

1. `User`: Represents a client in the network.
2. `Server`: Manages client connections and message routing.
3. `Message`: Encapsulates the structure and handling of messages.
4. `Neighbourhood`: Manages the topology of interconnected servers.
5. `Crypto`: Utility class for cryptographic operations.
6. `FileHandler`: Manages file operations within the network.

## Directory Structure

```
omesh/
├── app/
│   ├── __init__.py
│   ├── app.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── server.py
│   │   ├── message.py
│   │   └── neighbourhood.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── crypto.py
│   │   └── file_handler.py
│   └── routes/
│       ├── __init__.py
│       ├── client_routes.py
│       └── server_routes.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Development Setup

1. Clone the repository:

   ```
   git clone https://github.com/santiagosayshey/OMesh.git
   cd OMesh
   ```

2. Build and run the Docker container:

   ```
   docker-compose up --build
   ```

3. Access the application at `http://localhost:5995`

4. To stop the application:
   ```
   docker-compose down
   ```

## Running Tests

To run the tests for this project:

1. Build the Docker image (if you haven't already):

   ```
   docker build -t omesh .
   ```

2. Run the tests using the following command:
   ```
   docker run --rm omesh pytest /app/tests/<test>.py
   ```

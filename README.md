# OMesh: An Implementation of OLAF's Neighbourhood Protocol

OMesh is an implementation of OLAF's Neighbourhood protocol, designed to facilitate secure and decentralized messaging across a network of servers and clients. It leverages end-to-end encryption and a combination of symmetric and asymmetric cryptography to ensure data privacy and integrity. **This version of the code is intentionally backdoored.**

**Group Members:** Samuel Chau and Menno Brandt

---

## Table of Contents

- [Requirements](#requirements)
- [Setup](#setup)
- [Usage](#usage)
- [Backdoors](#backdoors)
- [Testing Protocol](#testing-protocol)
- [Appendix](#appendix)
  - [Key Features and Implementation Details](#key-features-and-implementation-details)
  - [Technologies Used](#technologies-used)
  - [Docker Compose Setup](#docker-compose-setup-for-omesh)
  - [Basic Docker Compose Commands](#basic-docker-compose-commands)
  - [Server Configuration](#server)
  - [Client Configuration](#client-environment-variables)

---

## Requirements

- **Docker**: Ensure Docker is installed and running on your system.
- **Docker Compose**: Required for orchestrating multi-container Docker applications.
- **Node.js and NPM**: For building the React frontend.
- **Python 3.9**: Necessary for running test scripts outside Docker, if needed.

**Note for Markers:** Please make sure you have Docker Compose 2.10+ installed. Python is necessary for testing purposes, but not for the main application. A standalone Python image is used in the Docker containers.

---

## Setup

Before proceeding, you need to clone the repo or download the ZIP file (already provided if you are marking this assignment), then install the frontend dependencies:

1. Cloning the Repository (only if you haven't already downloaded the ZIP)

   ```bash
   git clone https://github.com/santiagosayshey/OMesh.git
   cd OMesh
   ```

2. Navigate to the frontend directory:

   ```bash
   cd frontend
   ```

3. Install the necessary npm packages:

   ```bash
   npm install
   ```

4. Return to the root directory:

   ```bash
   cd ..
   ```

The remaining section is split into two main parts: I. Production and II. Testing. If you want to use OMesh in a production environment, please follow the instructions noted there. **If you are marking this assignment, please follow the testing instructions instead.**

**Note for Markers:** If you would like to test OMesh with your implementations, please follow the production steps to set up a custom server/client container. Otherwise, the testing setup will be sufficient to give feedback. If you have any problems setting it up, please reach out to `@santiagosayshey` on Discord, or email me at `schau22@pm.me`

### I. Production

1. **Build the Frontend**

   To build the React frontend, run:

   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

   This script will:

   - Build the React front end using Vite.
   - Deploy the build to the Flask client.

2. **Build a Server Container**

   Create a Docker Compose file for a server setup. Ensure that the necessary addresses, ports, and environment variables are included.

   **Note:** Two server compose files have been provided in `/compose`. An appendix explaining its structure has been provided in this README's appendix.

3. **Deploy a Server Container**

   Run:

   ```bash
   docker compose -f "<server>.yml" up --build
   ```

   This will build and serve the server instance using the provided details in your compose file.

   - If this is the first time that the server runs, it will generate and save its public key inside its config volume. This public key can be found by navigating to `<server_address>:<http_port>/pub`
   - To add a server to your neighbourhood, you must:
     1. Define the address and port of the remote server inside the `NEIGHBOUR_ADDRESSES` field inside your compose file.
     2. Upload the server's public key at `<server_address>:<http_port>/upload_key`
        - Make sure that the public key is named `<server_address>_<server_websocket_port>_public_key.pem`
     3. Restart the server
        - If you have done it correctly, your server will attempt to send a hello to every server identified.
        - It will retry up to 5 times before failing.

4. **Build a Client Container**

   Similar to the server compose file, create a new Docker Compose file for a client. Make sure to include all the necessary addresses, the **client** WebSocket port defined in your server, and all environment variables.

   **Note:** Three client compose files have been provided in `/compose`. An appendix explaining its structure has been provided in this README's appendix.

5. **Deploy a Client Container**

   Make sure your server is running, then run:

   ```bash
   docker compose -f "<client>.yml" up --build
   ```

   - If this is the first time that the client runs, it will generate and save its public/private key inside its config volume. These files are not accessible without accessing the Docker volume for safety.
   - This will attempt to connect to your server on its defined client WebSocket port. If successful, the client will be registered and will be provided a fingerprint.
   - You can now access your client's messaging interface at `<client_address>:<client_port>` and begin messaging other people! Any registered client known to your neighbourhood will be visible in the recipients' section.

   Move on to [Usage](#usage)

### II. Testing

To make marking easier, a bash script and complete Docker Compose file have been provided for you.

- All the necessary files are provided in the ZIP file you should have received.
- The bash script will attempt to build and move the frontend to the server's volume.
- It will run the compose file and create 3 clients, connected to 1 server each.
- The testing environment defines a `testing_neighborhood` volume which the servers will use to _automatically_ share public keys. You DO NOT need to adjust this volume or manually share public keys!
- Simply run the following script and everything will be set up for you automatically:

  ```bash
  chmod +x deploy.sh
  chmod +x start.sh
  ./start.sh
  ```

**Note:** The clients will fail to connect to servers on their first attempt—this is expected. The servers take a few seconds to set themselves up and share public keys. The clients will successfully connect on their subsequent attempts!

The following table links all the necessary interfaces and ports for the testing setup, including the WebSocket and HTTP ports for each server, and the web interface for each client.

**Important:** Please make sure that the following ports are _available_; you will not be able to run the test suite if they are not. You can change the assigned ports in the `docker-compose.yml` file. They do not need to be port forwarded.

| Name     | Description              | Links                                                                                                               |
| -------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| Server 1 | Main server for Client 1 | Client WebSocket: `ws://localhost:8765`<br>Server WebSocket: `ws://localhost:8766`<br>HTTP: `http://localhost:8081` |
| Server 2 | Main server for Client 2 | Client WebSocket: `ws://localhost:8767`<br>Server WebSocket: `ws://localhost:8768`<br>HTTP: `http://localhost:8082` |
| Server 3 | Main server for Client 3 | Client WebSocket: `ws://localhost:8769`<br>Server WebSocket: `ws://localhost:8770`<br>HTTP: `http://localhost:8083` |
| Client 1 | Connected to Server 1    | Web Interface: `http://localhost:5001`                                                                              |
| Client 2 | Connected to Server 2    | Web Interface: `http://localhost:5002`                                                                              |
| Client 3 | Connected to Server 3    | Web Interface: `http://localhost:5003`                                                                              |

---

## Usage

After navigating to your client's interface, you will now be able to use the application. You may:

- **Send Messages**: Use the chat interface to send public or private messages to other users.
- **Upload Files**: Click the file upload button (represented by a '+' icon) to send files to other users. This will upload the file to _your_ server, then send a link to this file.
- **Select Recipients**: Choose recipients from the list to send private messages or files. You can select multiple users or opt for a global chat.

---

## Backdoors

This version of the code **contains 4 intentional vulnerabilities that compromise the system's security**. These backdoors have been carefully obfuscated and are designed to be challenging to identify and exploit.

## Testing Protocol

To ensure the correctness and reliability of the OMesh implementation, we have developed a comprehensive testing protocol. This protocol covers various aspects of the system, including cryptographic operations, message structure compliance, and end-to-end functionality.

### Overview of Testing Protocol

Our testing protocol is designed to verify:

1. **Cryptographic Function Testing**: Ensures all cryptographic operations (key generation, encryption/decryption, digital signatures) are implemented correctly.
2. **Message Structure Compliance Testing**: Verifies that all messages adhere to the protocol's data structures and field requirements.
3. **End-to-End Testing**: Checks the overall functionality of the system in various scenarios.

### Accessing the Testing Protocol

For a detailed explanation of our testing methodology and specific test cases, please refer to our [Testing Protocol Document](tests/README.md). This document provides in-depth information on:

- Test case descriptions and objectives
- Step-by-step procedures for each test
- Expected and actual results
- Guidelines for interpreting test outcomes

### Running the Tests

To run the automated tests for OMesh:

1. Ensure you have set up the requirements described in the [Requirements](#requirements) section.
2. Navigate to the project root directory.
3. Run the testing script:

   ```bash
   ./run_tests.sh
   ```

### Interoperability Testing

- TODO

---

## Appendix

### Key Features and Implementation Details

#### Users

- **Identification**: Users are identified by RSA key pairs. Each user generates a unique RSA key pair, and the public key is used to derive a fingerprint.
- **Fingerprints**: A user's fingerprint is derived from their public key and serves as their unique identifier in the network.
- **Authentication**: Clients authenticate themselves to servers using their public keys and digital signatures.

#### Servers

- **Role**: Servers act as intermediaries, relaying messages between clients and forwarding messages to other servers in the neighborhood.
- **Communication**: Servers use WebSocket connections for real-time communication with clients and other servers.
- **Public Key Distribution**: Each server has a public/private key pair. The public key is shared with neighboring servers to establish trust.
- **Neighbourhood Formation**: Servers form neighbourhoods by manually sharing their public keys and configuring neighbour addresses.

#### Neighbourhoods

- **Definition**: A neighbourhood is a meshed network of interconnected servers that collaborate to relay messages across the network.
- **Manual Configuration**: Neighbourhoods are manually defined by specifying neighbour server addresses and exchanging public keys.
- **Server Discovery**: Servers send `hello_server` messages to establish connections with neighbouring servers.
- **Message Propagation**: Messages are propagated across the neighbourhood to reach clients connected to different servers.

#### Messages

- **Format**: Messages are JSON-formatted and UTF-8 encoded.
- **Encryption**: Messages are encrypted end-to-end using a combination of RSA and AES-GCM encryption.
  - **Asymmetric Encryption**: RSA is used for encrypting symmetric keys and for digital signatures.
  - **Symmetric Encryption**: AES-GCM is used for encrypting the actual message content.
- **Security Features**:
  - **Digital Signatures**: Messages include digital signatures for authentication and integrity verification.
  - **Replay Attack Prevention**: Messages include counters and timestamps to prevent replay attacks.

#### Communication Protocol

- **Client-Server Communication**:
  - Clients establish a WebSocket connection to the server's client WebSocket port.
  - Clients send a `hello` message to register with the server, including their public key and other necessary information.
  - The server responds with a confirmation and assigns the client a unique fingerprint.
- **Server-Server Communication**:
  - Servers establish WebSocket connections to neighbouring servers using the server WebSocket port.
  - Servers send `hello_server` messages to authenticate and establish trust with neighbouring servers.
  - Servers exchange public keys and verify each other's identities.

#### File Transfers

- **HTTP API**: Files are transferred via HTTP APIs provided by the servers.
- **Process**:
  - Clients upload files to their connected server using the HTTP API.
  - The server stores the file and provides a link to the file.
  - The client sends the file link to the recipient(s) via the messaging system.
  - Recipients download the file from the server using the provided link.
- **Security**:
  - File links are secured and include tokens or parameters to prevent unauthorized access.

#### Asynchronous Programming

- **Asyncio**: The implementation utilizes Python's `asyncio` library for non-blocking, asynchronous operations.
- **Concurrency**: Asynchronous programming allows the system to handle multiple connections and operations concurrently without blocking.

#### Dockerized Services

- **Containerization**: All components (clients and servers) are containerized using Docker for easy deployment and scaling.
- **Orchestration**: Docker Compose is used to manage multi-container setups and orchestrate services.
- **Volume Management**: Docker volumes are used to persist data such as configuration files, keys, and message logs.

#### Frontend Interface

- **React and Vite**: The user interface is built with React and served using Vite for efficient development and optimized builds.
- **User Experience**: Provides a web-based interface for users to send messages, upload files, and interact with the system.

---

### Technologies Used

- **Python 3.9**: Core language for server and client implementations.
- **WebSockets (RFC 6455)**: For real-time communication between clients and servers.
- **Flask**: A micro web framework for the client-side API.
- **React**: For the frontend user interface.
- **Vite**: A build tool for frontend assets, providing faster builds and optimized outputs.
- **Docker & Docker Compose**: Containerization and orchestration of services.
- **Cryptography Library**: For RSA and AES encryption implementations.
- **aiohttp**: Asynchronous HTTP client/server framework.
- **Asyncio**: For asynchronous programming in Python.

---

### Docker Compose Setup for OMesh

- **Containerization**: Each OMesh component (clients/servers) is containerized.
- **Orchestration**: Docker Compose manages multi-container setup.
- **Data Management**: Volumes persist configuration, chat data, and server info.
- **Networking**: Custom network (`olaf_network`) for inter-container communication.
- **Environment Reset**: `docker compose down -v` removes containers, networks, and volumes.

### Basic Docker Compose Commands

- **Start services**: `docker compose up -d`
- **Stop services**: `docker compose down`
- **View logs**: `docker compose logs -f`
- **Rebuild and start services**: `docker compose up -d --build`
- **Stop services and remove volumes**: `docker compose down -v`

### Server

Sample Docker Compose file for a server:

```yaml
version: "3.8"
services:
  server1:
    build:
      context: .
      dockerfile: ./server/Dockerfile
    container_name: olaf_server1
    ports:
      - "8765:8765" # External:Internal WebSocket port for clients
      - "8766:8766" # External:Internal WebSocket port for servers
      - "8081:8081" # External:Internal HTTP port for file transfers
    volumes:
      - clients1:/app/server/clients
      - files1:/app/server/files
      - config1:/app/server/config
      - neighbours1:/app/server/neighbours
    environment:
      - BIND_ADDRESS=0.0.0.0
      - CLIENT_WS_PORT=8765
      - SERVER_WS_PORT=8766
      - HTTP_PORT=8081
      - NEIGHBOUR_ADDRESSES=<neighbor_ip>:<neighbor_port>
      - LOG_MESSAGES=True
      - EXTERNAL_ADDRESS=<server_public_ip>
    networks:
      - olaf_network

volumes:
  clients1:
  files1:
  config1:
  neighbours1:

networks:
  olaf_network:
    driver: bridge
```

#### Server Environment Variables

| Environment Variable  | Description                                                                        | Example Value         |
| --------------------- | ---------------------------------------------------------------------------------- | --------------------- |
| `BIND_ADDRESS`        | IP address the server binds to. `0.0.0.0` allows connections from any interface.   | `0.0.0.0`             |
| `CLIENT_WS_PORT`      | Internal port for client WebSocket connections.                                    | `8765`                |
| `SERVER_WS_PORT`      | Internal port for server-to-server WebSocket connections.                          | `8766`                |
| `HTTP_PORT`           | Internal port for HTTP-based file transfers.                                       | `8081`                |
| `NEIGHBOUR_ADDRESSES` | Comma-separated list of neighbouring server addresses (IP:Port).                   | `203.221.52.227:8766` |
| `LOG_MESSAGES`        | Enables (`True`) or disables (`False`) message logging for debugging.              | `True`                |
| `EXTERNAL_ADDRESS`    | Public IP address of the server, used for client connections and key distribution. | `65.108.216.173`      |

#### Port Mapping

The `ports` section in the Docker Compose file maps external (host) ports to internal (container) ports. For example:

- `"8765:8765"`: Maps the host's port 8765 to the container's port 8765 for client connections.
- `"8766:8766"`: Maps the host's port 8766 to the container's port 8766 for server-to-server connections.
- `"8081:8081"`: Maps the host's port 8081 to the container's port 8081 for HTTP file transfers.

This mapping allows external connections to reach the correct services inside the container. Ensure that the external ports match the ports you want to expose on your host machine.

### Client Environment Variables

Sample Docker Compose file for a client:

```yaml
version: "3.8"
services:
  client1:
    build:
      context: .
      dockerfile: ./client/Dockerfile
    container_name: olaf_client1
    ports:
      - "5001:5000" # External:Internal port for web interface
    volumes:
      - config_client1:/app/client/config
      - chat_data_client1:/app/client/chat_data
    environment:
      - SERVER_ADDRESS=<server_public_ip>
      - SERVER_PORT=8765
      - HTTP_PORT=8081
      - LOG_MESSAGES=True
      - CLIENT_NAME=<unique_client_name>
      - MESSAGE_EXPIRY_TIME=-1
    networks:
      - olaf_network

volumes:
  config_client1:
  chat_data_client1:

networks:
  olaf_network:
    driver: bridge
```

#### Client Environment Variables

| Environment Variable  | Description                                                                                             | Example Value    |
| --------------------- | ------------------------------------------------------------------------------------------------------- | ---------------- |
| `SERVER_ADDRESS`      | Public IP address of the server the client connects to.                                                 | `65.108.216.173` |
| `SERVER_PORT`         | External WebSocket port on the server for client connections.                                           | `8765`           |
| `HTTP_PORT`           | External HTTP port on the server for file transfers.                                                    | `8081`           |
| `LOG_MESSAGES`        | Enables (`True`) or disables (`False`) message logging for debugging.                                   | `True`           |
| `CLIENT_NAME`         | Unique identifier for the client, used ONLY for local identification.                                   | `my_client`      |
| `MESSAGE_EXPIRY_TIME` | Controls message retention: `-1` (never delete), `0` (always delete), `>0` (keep for specified seconds) | `-1`             |

---

# End of README

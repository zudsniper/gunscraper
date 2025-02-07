#!/bin/bash

# Default values
CONTAINER_NAME="gun_market_mongodb"
MONGO_PORT=27017
MONGO_USERNAME="admin"
MONGO_PASSWORD="password"  # You should change this in production
MONGO_DB_NAME="gun_market_data"
DATA_DIR="./mongodb_data"  # Local directory to persist MongoDB data

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running${NC}"
        exit 1
    fi
}

# Function to check if container exists
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Function to check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"

# Check if Docker is running
check_docker

# Check if container exists
if container_exists; then
    if container_running; then
        echo -e "${YELLOW}MongoDB container is already running${NC}"
        exit 0
    else
        echo -e "${GREEN}Starting existing MongoDB container...${NC}"
        docker start "$CONTAINER_NAME"
        exit 0
    fi
fi

# Create and start new container
echo -e "${GREEN}Creating and starting new MongoDB container...${NC}"
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$MONGO_PORT:27017" \
    -v "$DATA_DIR:/data/db" \
    -e MONGO_INITDB_ROOT_USERNAME="$MONGO_USERNAME" \
    -e MONGO_INITDB_ROOT_PASSWORD="$MONGO_PASSWORD" \
    -e MONGO_INITDB_DATABASE="$MONGO_DB_NAME" \
    --restart unless-stopped \
    mongo:latest

# Wait for MongoDB to start
echo -e "${YELLOW}Waiting for MongoDB to start...${NC}"
sleep 5

# Create initial user and database
echo -e "${GREEN}Setting up database and user...${NC}"
docker exec "$CONTAINER_NAME" mongosh \
    -u "$MONGO_USERNAME" \
    -p "$MONGO_PASSWORD" \
    --authenticationDatabase admin \
    "$MONGO_DB_NAME" \
    --eval '
        db.createUser({
            user: "app_user",
            pwd: "app_password",  // You should change this in production
            roles: [
                { role: "readWrite", db: "gun_market_data" }
            ]
        });
    '

echo -e "${GREEN}MongoDB is ready!${NC}"
echo -e "Container name: ${YELLOW}$CONTAINER_NAME${NC}"
echo -e "Port: ${YELLOW}$MONGO_PORT${NC}"
echo -e "Data directory: ${YELLOW}$DATA_DIR${NC}"

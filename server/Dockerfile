# server/Dockerfile

FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy server requirements and install dependencies
COPY ./server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code and the common module into the container
COPY ./server ./server
COPY ./common ./common

# Set the working directory to the server directory
WORKDIR /app/server

# Expose the necessary ports
EXPOSE 8765 8766 8080

# Define environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Command to run when the container starts
CMD ["python", "server.py"]

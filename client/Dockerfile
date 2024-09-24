# client/Dockerfile

FROM python:3.9-slim

WORKDIR /app

# Copy client requirements and install dependencies
COPY ./client/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the client code and the common module into the container
COPY ./client ./client
COPY ./common ./common

# Set the working directory to the client directory
WORKDIR /app/client

EXPOSE 5000

# Define environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "client.py"]

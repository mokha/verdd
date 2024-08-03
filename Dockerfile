FROM python:3.12-slim-bullseye AS build

# Set the working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies
RUN pip3 install --upgrade pip setuptools wheel
COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt  --no-cache-dir

# Copy the project code into the container
COPY . /app/
# Python installation
FROM python:3.11-slim

# Creating directory
WORKDIR /app

# Copy requirements to directory
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy code into container
COPY . .

# Run Dockerfile
CMD ["python", "main.py"]
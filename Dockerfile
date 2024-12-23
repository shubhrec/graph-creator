FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including git and Rust
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    curl \
    build-essential \
    nodejs \
    npm \   
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install ast-grep CLI globally
RUN npm install --global @ast-grep/cli

# Create test directory
RUN mkdir -p /app/test

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Keep container running
CMD ["tail", "-f", "/dev/null"]
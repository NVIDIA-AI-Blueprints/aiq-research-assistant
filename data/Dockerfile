FROM nvcr.io/nvidia/base/ubuntu:22.04_20240212

# Install uv package manager
# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

RUN uv python install 3.12

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /tmp-data/uploaded_files

# Install dependencies using uv
COPY requirements.txt .
RUN uv venv --python-preference managed
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy the sync script and files
COPY ./sync_files2.py .
COPY ./files/* .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run script using uv
CMD ["uv", "run", "python", "sync_files2.py"]

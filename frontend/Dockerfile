FROM nvcr.io/nvidia/base/ubuntu:jammy-20250415.1


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

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN uv venv --python-preference managed && uv pip install -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

EXPOSE 3003

# Run app.py when the container launches
ENTRYPOINT ["uv", "run", "streamlit", "run", "app.py", "--server.port=3003", "--server.address=0.0.0.0"]

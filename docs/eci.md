# Enterprise Content Intelligence (ECI) Tools

## Setup

Ensure the project has been installed and the virtual environment has been activated.

```bash
# Create a virtual environment
uv venv --seed .venv --python 3.12
source .venv/bin/activate
uv sync --all-groups --all-extras

# Test the install
uv run aira eci --help
```

## Usage

At any time, you can run the following command to see the available commands:

```bash
uv run aira --help
```

### Starfleet

To login to Starfleet, run the following command:

```bash
uv run aira auth starfleet
# or for production
uv run aira auth --prod starfleet <commands>
```

Once you have logged in, your credentials will be saved to the default `appdata` directory and will be used automatically from then on.

To force a login to Starfleet, run the following command:
```bash
uv run aira auth starfleet --force-login
```

To force a refresh of the Starfleet credentials, run the following command:
```bash
uv run aira auth starfleet --force-refresh
```

### SSA

To login to SSA, run the following command:

```bash
uv run aira auth ssa
# or for production
uv run aira auth --prod ssa <commands>
```

Once you have logged in, your credentials will be saved to the default `appdata` directory and will be used automatically from then on.

To force a login to SSA, run the following command:
```bash
uv run aira auth ssa --force-login
```

### ECI

To make a request to ECI, run the following command:

```bash
uv run aira eci --query="NIM"
# or for production
uv run aira eci --prod --query="NIM"
```

This will make a request to the ECI endpoint and print the response to the console. If there are more than one page of results, the response will be paginated and you will need to make multiple requests to get the entire response. Simply press `ENTER` to get the next page of results when you see this message:

```
Additional results found. Press Enter to continue or Ctrl-C to exit...
```


## Setup

1. Create a virtual environment

   ```bash
   uv venv --seed .venv --python 3.11
   source .venv/bin/activate
   ```

2. Install the dependencies

   ```bash
   uv pip install -r ./scripts/eci_auth/requirements.txt
   ```

3. Test the install

   ```bash
   python -m scripts.eci_auth.cli --help
   ```

## Usage

At any time, you can run the following command to see the available commands:

```bash
python -m scripts.eci_auth.cli --help
```

### Starfleet

To login to Starfleet, run the following command:

```bash
python -m scripts.eci_auth.cli starfleet
```

Once you have logged in, your credentials will be saved to the default `appdata` directory and will be used automatically from then on.

To force a login to Starfleet, run the following command:
```bash
python -m scripts.eci_auth.cli starfleet --force-login
```

To force a refresh of the Starfleet credentials, run the following command:
```bash
python -m scripts.eci_auth.cli starfleet --force-refresh
```

### SSA

To login to SSA, run the following command:

```bash
python -m scripts.eci_auth.cli ssa
```

Once you have logged in, your credentials will be saved to the default `appdata` directory and will be used automatically from then on.

To force a login to SSA, run the following command:
```bash
python -m scripts.eci_auth.cli ssa --force-login
```

### ECI

To make a request to ECI, run the following command:

```bash
python -m scripts.eci_auth.cli eci --query="NIM"
```

This will make a request to the ECI endpoint and print the response to the console. If there are more than one page of results, the response will be paginated and you will need to make multiple requests to get the entire response. Simply press `ENTER` to get the next page of results when you see this message:

```
Additional results found. Press Enter to continue or Ctrl-C to exit...
```

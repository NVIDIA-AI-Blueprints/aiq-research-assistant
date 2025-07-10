# Testing with ECI 

1. Checkout git repo 

```
git clone ssh://git@gitlab-master.nvidia.com:12051/chat-labs/OpenSource/agentiq-blueprint/aiq-bp-internal.git
git fetch origin eci-search && git checkout eci-search
```

2. Create a virtualenv 

```
uv venv --python 3.12
source .venv/bin/activate
```

3. Create a file, test.env with value

```
AIQ_STARFLEET_CLIENT_ID=""
```

4. Create starfleet token

```
uv pip install -r scripts/eci_auth/requirements.txt
uv run --env-file test.env scripts/eci_auth/cli.py --prod starfleet
```

Copy the ID token, set this as the `Authorization` header in requests
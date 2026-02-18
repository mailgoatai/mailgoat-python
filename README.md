# mailgoat-python (Beta)

[![CI](https://github.com/mailgoatai/mailgoat-python/actions/workflows/ci.yml/badge.svg)](https://github.com/mailgoatai/mailgoat-python/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/mailgoatai/mailgoat-python/branch/main/graph/badge.svg)](https://codecov.io/gh/mailgoatai/mailgoat-python)

`mailgoat` is the official Python SDK for the MailGoat API.

## Installation

```bash
pip install mailgoat
```

For development:

```bash
pip install -e .[test]
```

## Quickstart

```python
from mailgoat import MailGoat

mg = MailGoat(server="https://postal.example.com", api_key="your-api-key")

message_id = mg.send(
    to="user@example.com",
    subject="Hello from MailGoat",
    body="This message was sent with the Python SDK.",
    from_address="noreply@example.com",
)

message = mg.read(message_id)
print(message.subject)
```

## Send with attachments

```python
from pathlib import Path
from mailgoat import MailGoat

mg = MailGoat(server="https://postal.example.com", api_key="your-api-key")

message_id = mg.send(
    to=["user@example.com"],
    subject="Report",
    body="Please find the report attached.",
    attachments=[Path("./report.pdf")],
)
```

## Error handling

```python
from mailgoat import MailGoat, MailGoatAPIError, MailGoatNetworkError

mg = MailGoat(server="https://postal.example.com", api_key="your-api-key")

try:
    mg.send(to="user@example.com", subject="Hello", body="world")
except MailGoatAPIError as err:
    print(err.status_code, err)
except MailGoatNetworkError as err:
    print(err)
```

## API

- `MailGoat(server, api_key, timeout=15.0)`
- `send(to, subject, body, from_address=None, attachments=None) -> str`
- `read(message_id) -> Message`

## Batch Sending

Send many messages from CSV:

```bash
mailgoat send-batch \
  --profile work \
  --csv ./recipients.csv \
  --template ./template.json \
  --continue-on-error \
  --rate-limit 5
```

Send from JSON array:

```bash
mailgoat send-batch \
  --profile work \
  --json ./recipients.json
```

Send from stdin:

```bash
cat recipients.json | mailgoat send-batch \
  --profile work \
  --stdin
```

Check batch status:

```bash
mailgoat batch status <batch_id>
```

### CSV Format

Required columns:

- `to`
- `subject` and `body` (unless `--template` is used)

Example:

```csv
to,subject,body,name
user1@example.com,Welcome,Hello user1,Ada
user2@example.com,Welcome,Hello user2,Lin
```

### Template Syntax

Template file is JSON:

```json
{
  "subject": "Hello {{name}}",
  "body": "Your code is {{code}}",
  "from": "noreply@example.com"
}
```

Variables like `{{name}}` and `{{code}}` come from each CSV/JSON row.

## Profiles (Aliases / Multi-Account)

Configure named profiles for multiple sender identities/accounts:

```bash
mailgoat profile add work
mailgoat profile add personal
mailgoat profile list
mailgoat profile use work
```

Use default profile:

```bash
mailgoat send-batch --json recipients.json
```

Override for one command:

```bash
mailgoat send-batch --profile personal --json recipients.json
```

Environment variable override:

```bash
export MAILGOAT_PROFILE=personal
mailgoat send-batch --json recipients.json
```

Each profile stores:

- `server`
- `api_key`
- `from_address`
- `from_name`

## Testing

Run unit tests:

```bash
pytest tests/unit
```

Run integration tests against a real Postal server:

```bash
export MAILGOAT_TEST_SERVER="https://postal.example.com"
export MAILGOAT_TEST_API_KEY="..."
export MAILGOAT_TEST_TO="recipient@example.com"
pytest tests/integration -m integration
```

## Development Workflow

Push directly to `main` after local verification.

Required before every push:

```bash
make test
make build
make check-dist
```

Run full release readiness checks:

```bash
make release-check
```

## Publishing (beta)

Build and upload `1.0.0b1`:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

Or use GitHub Actions:

- `CI` workflow runs tests/build/twine checks on PRs and `main`.
- `Publish` workflow is manual (`workflow_dispatch`) and publishes to TestPyPI then PyPI using trusted publishing.

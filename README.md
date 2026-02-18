# mailgoat-python (Beta)

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

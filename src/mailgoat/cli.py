from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch import BatchStore, load_recipients, load_template, send_batch
from .client import MailGoat


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mailgoat")
    sub = parser.add_subparsers(dest="command", required=True)

    send_batch_parser = sub.add_parser("send-batch", help="Send a batch of emails")
    send_batch_parser.add_argument("--server", required=True)
    send_batch_parser.add_argument("--api-key", required=True)
    send_batch_parser.add_argument("--csv", dest="csv_path")
    send_batch_parser.add_argument("--json", dest="json_path")
    send_batch_parser.add_argument("--stdin", action="store_true", dest="use_stdin")
    send_batch_parser.add_argument("--template", dest="template_path")
    send_batch_parser.add_argument("--continue-on-error", action="store_true")
    send_batch_parser.add_argument("--rate-limit", type=float)
    send_batch_parser.add_argument("--error-log")
    send_batch_parser.add_argument("--db-path", default="~/.mailgoat/batches.db")

    batch_parser = sub.add_parser("batch", help="Batch operations")
    batch_sub = batch_parser.add_subparsers(dest="batch_command", required=True)
    batch_status = batch_sub.add_parser("status", help="Show status for one batch")
    batch_status.add_argument("batch_id")
    batch_status.add_argument("--db-path", default="~/.mailgoat/batches.db")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "send-batch":
        stdin_data = sys.stdin.read() if args.use_stdin else None
        recipients = load_recipients(csv_path=args.csv_path, json_path=args.json_path, stdin_data=stdin_data)
        template = load_template(args.template_path)

        with MailGoat(server=args.server, api_key=args.api_key) as client:
            summary = send_batch(
                client=client,
                recipients=recipients,
                template=template,
                continue_on_error=args.continue_on_error,
                rate_limit=args.rate_limit,
                error_log_path=args.error_log,
                db_path=args.db_path,
            )

        print(
            json.dumps(
                {
                    "batch_id": summary.batch_id,
                    "status": summary.status,
                    "total": summary.total,
                    "sent": summary.sent,
                    "failed": summary.failed,
                    "started_at": summary.started_at,
                    "finished_at": summary.finished_at,
                }
            )
        )
        return 0

    if args.command == "batch" and args.batch_command == "status":
        store = BatchStore(db_path=args.db_path)
        try:
            record = store.get_batch(args.batch_id)
        finally:
            store.close()

        if record is None:
            print(json.dumps({"error": "batch not found", "batch_id": args.batch_id}))
            return 1

        print(
            json.dumps(
                {
                    "batch_id": record.batch_id,
                    "status": record.status,
                    "total": record.total_count,
                    "sent": record.sent_count,
                    "failed": record.failed_count,
                    "continue_on_error": record.continue_on_error,
                    "rate_limit": record.rate_limit,
                    "started_at": record.started_at,
                    "finished_at": record.finished_at,
                }
            )
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Create a private production env file without displaying any credential values."""

import argparse
import os
import secrets
from pathlib import Path
from urllib.parse import quote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, default=Path(".env.prod"))
    parser.add_argument("--host", default="event-ticket-booking.duckdns.org")
    args = parser.parse_args()
    required = {"GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "DUCKDNS_API_TOKEN"}
    values = {}
    for line in args.source.read_text().splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key.strip() in required:
            key = key.strip()
            if key in values:
                parser.error(f"Duplicate setting: {key}")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    if any(not values.get(key) for key in required):
        parser.error("Source must contain Gmail address, App Password, and DuckDNS token")
    address = values["GMAIL_ADDRESS"].strip()
    password = "".join(values["GMAIL_APP_PASSWORD"].split())
    if "@" not in address or any(c.isspace() for c in address) or len(password) != 16:
        parser.error("Check Gmail address and 16-character App Password")
    if not args.host.endswith(".duckdns.org") or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-." for c in args.host
    ):
        parser.error("Expected a DuckDNS hostname")
    db_password = secrets.token_hex(32)
    settings = {
        "RELEASE_TAG": "local",
        "PUBLIC_HOST": args.host,
        "SECRET_KEY": secrets.token_urlsafe(64),
        "POSTGRES_PASSWORD": db_password,
        "DATABASE_URL": f"postgres://ticketing:{db_password}@db:5432/ticketing",
        "EMAIL_URL": (
            f"smtp+tls://{quote(address, safe='')}:{quote(password, safe='')}@smtp.gmail.com:587"
        ),
        "DEFAULT_FROM_EMAIL": f"Ticket Booking <{address}>",
        "ACME_EMAIL": address,
        "DUCKDNS_API_TOKEN": values["DUCKDNS_API_TOKEN"],
        "ORDER_TTL_MINUTES": "15",
    }
    # Single-quoted dotenv values suppress Compose interpolation, including '$'.
    if any("'" in value or "\n" in value or "\r" in value for value in settings.values()):
        parser.error("A setting contains unsupported quoting or newlines")
    try:
        with open(
            args.output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)
        ) as stream:
            stream.write("\n".join(f"{key}='{value}'" for key, value in settings.items()) + "\n")
    except FileExistsError:
        parser.error("Output already exists; refusing to replace database/signing credentials")
    print(f"Private production settings created at {args.output}; no values displayed.")


if __name__ == "__main__":
    main()

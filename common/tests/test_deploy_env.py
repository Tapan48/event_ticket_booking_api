"""Credential provisioning must not disclose or silently replace production secrets."""

import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "make_env.py"


def test_private_env_normalizes_password_and_refuses_overwrite(tmp_path):
    source = tmp_path / "source.env"
    output = tmp_path / "production.env"
    source.write_text(
        "GMAIL_ADDRESS=demo+ticket@gmail.com\n"
        "GMAIL_APP_PASSWORD='abcd efgh ijkl mnop'\n"
        "DUCKDNS_API_TOKEN=test-duckdns-token\n"
    )
    command = [sys.executable, str(SCRIPT), "--source", str(source), "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    contents = output.read_text()
    values = dict(shlex.split(line)[0].split("=", 1) for line in contents.splitlines())
    smtp = urlsplit(values["EMAIL_URL"])
    assert unquote(smtp.username) == "demo+ticket@gmail.com"
    assert unquote(smtp.password) == "abcdefghijklmnop"
    assert smtp.scheme == "smtp+tls"
    assert smtp.port == 587
    assert values["POSTGRES_PASSWORD"] in values["DATABASE_URL"]
    assert len(values["SECRET_KEY"]) >= 50
    if os.name == "posix":
        assert output.stat().st_mode & 0o777 == 0o600
    for secret in ("abcdefghijklmnop", "test-duckdns-token", values["SECRET_KEY"]):
        assert secret not in result.stdout + result.stderr
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert output.read_text() == contents


def test_private_env_rejects_missing_credentials_without_writing(tmp_path):
    source = tmp_path / "source.env"
    output = tmp_path / "production.env"
    source.write_text("GMAIL_ADDRESS=demo@gmail.com\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not output.exists()

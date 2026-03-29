"""
Run ATIM with HTTPS locally.
Generates certificates if needed and launches Uvicorn with SSL.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_https_server() -> None:
    """Generate certificates and start the HTTPS server."""
    project_root = Path(__file__).resolve().parents[2]
    cert_dir = project_root / "certs"
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"

    if not (cert_file.exists() and key_file.exists()):
        result = subprocess.run(
            [sys.executable, str(project_root / "scripts" / "https" / "generate_certs.py")],
            cwd=str(project_root),
        )
        if result.returncode != 0:
            print("Error generating SSL certificates")
            sys.exit(1)

    print("Starting ATIM HTTPS server on https://localhost:8000")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--ssl-keyfile",
            str(key_file),
            "--ssl-certfile",
            str(cert_file),
            "--reload",
        ],
        cwd=str(project_root),
        env=os.environ.copy(),
    )


if __name__ == "__main__":
    run_https_server()

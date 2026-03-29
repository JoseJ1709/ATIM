"""
Generate self-signed SSL certificates for local HTTPS development.
"""

from datetime import datetime, timedelta
from ipaddress import IPv4Address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from cryptography.x509.oid import NameOID


def generate_ssl_certificates(cert_dir: str = "certs") -> tuple[str, str]:
    """Generate cert.pem and key.pem for localhost if they don't exist."""
    cert_path = Path(cert_dir)
    cert_path.mkdir(parents=True, exist_ok=True)

    cert_file = cert_path / "cert.pem"
    key_file = cert_path / "key.pem"

    if cert_file.exists() and key_file.exists():
        print(f"Certificates already exist in {cert_path}/")
        return str(cert_file), str(key_file)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ATIM"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                    x509.DNSName("*.localhost"),
                    x509.IPAddress(IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(private_key, hashes.SHA256())
    )

    cert_file.write_bytes(cert.public_bytes(Encoding.PEM))
    key_file.write_bytes(
        private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        )
    )

    print(f"Certificate generated: {cert_file}")
    print(f"Private key generated: {key_file}")
    return str(cert_file), str(key_file)


if __name__ == "__main__":
    generate_ssl_certificates()

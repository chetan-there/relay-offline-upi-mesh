"""
Generates a fresh RSA-2048 keypair once when the app starts, exactly like
the Node.js and Java rebuilds. In production the private key would live in
an HSM/KMS and never touch application memory in plaintext; the public key
would be baked into client apps rather than fetched at runtime.
"""
from .crypto_service import generate_server_keypair, public_key_to_base64

_private_key, _public_key = generate_server_keypair()
_public_key_b64 = public_key_to_base64(_public_key)


def get_private_key():
    return _private_key


def get_public_key():
    return _public_key


def get_public_key_base64() -> str:
    return _public_key_b64

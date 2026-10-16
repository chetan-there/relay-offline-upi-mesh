"""
Hybrid encryption: RSA-OAEP wraps a fresh AES-256 key per packet;
AES-256-GCM encrypts the actual JSON payload (fast + authenticated).

Wire format (concatenated, then base64-encoded) - identical across all
three rebuilds of this project (Node.js, Java, Python):
  [RSA-2048 encrypted AES key : 256 bytes]
  [AES-GCM IV                 : 12 bytes]
  [AES-GCM ciphertext + 16-byte auth tag appended]

cryptography's AESGCM.encrypt() already appends the auth tag to the
ciphertext and AESGCM.decrypt() verifies it automatically, raising
InvalidTag on any tampering - so a single flipped bit anywhere in the
ciphertext throws before any plaintext is returned.
"""
import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from .schemas import PaymentInstruction

RSA_KEY_SIZE_BYTES = 256  # 2048-bit key
AES_IV_BYTES = 12


class DecryptionError(Exception):
    """Raised for any malformed or tampered ciphertext. Callers treat this as INVALID."""


def generate_server_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _oaep_padding():
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )


def public_key_to_base64(public_key) -> str:
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(der).decode("ascii")


def encrypt_for_server(public_key, payload: PaymentInstruction) -> str:
    plaintext = json.dumps(
        {
            "sender": payload.sender,
            "receiver": payload.receiver,
            "amount": payload.amount,
            "pinHash": payload.pin_hash,
            "nonce": payload.nonce,
            "signedAt": payload.signed_at,
        }
    ).encode("utf-8")

    aes_key = AESGCM.generate_key(bit_length=256)
    iv = os.urandom(AES_IV_BYTES)
    aesgcm = AESGCM(aes_key)
    encrypted_with_tag = aesgcm.encrypt(iv, plaintext, None)  # tag is appended automatically

    wrapped_key = public_key.encrypt(aes_key, _oaep_padding())

    packet = wrapped_key + iv + encrypted_with_tag
    return base64.b64encode(packet).decode("ascii")


def decrypt_from_client(private_key, ciphertext_b64: str) -> PaymentInstruction:
    try:
        packet = base64.b64decode(ciphertext_b64, validate=True)
    except Exception as e:
        raise DecryptionError("Ciphertext is not valid base64") from e

    if len(packet) < RSA_KEY_SIZE_BYTES + AES_IV_BYTES + 16:
        raise DecryptionError("Ciphertext too short to be a valid packet")

    wrapped_key = packet[:RSA_KEY_SIZE_BYTES]
    iv = packet[RSA_KEY_SIZE_BYTES:RSA_KEY_SIZE_BYTES + AES_IV_BYTES]
    encrypted_with_tag = packet[RSA_KEY_SIZE_BYTES + AES_IV_BYTES:]

    try:
        aes_key = private_key.decrypt(wrapped_key, _oaep_padding())
    except Exception as e:
        raise DecryptionError("RSA unwrap failed") from e

    try:
        aesgcm = AESGCM(aes_key)
        decrypted = aesgcm.decrypt(iv, encrypted_with_tag, None)
    except InvalidTag as e:
        raise DecryptionError("AES-GCM authentication failed (tampered ciphertext)") from e
    except Exception as e:
        raise DecryptionError("AES-GCM decryption failed") from e

    try:
        data = json.loads(decrypted)
        return PaymentInstruction(
            sender=data["sender"],
            receiver=data["receiver"],
            amount=data["amount"],
            pin_hash=data["pinHash"],
            nonce=data["nonce"],
            signed_at=data["signedAt"],
        )
    except Exception as e:
        raise DecryptionError("Decrypted payload was not valid PaymentInstruction JSON") from e


def hash_ciphertext(ciphertext_b64: str) -> str:
    return hashlib.sha256(ciphertext_b64.encode("utf-8")).hexdigest()

import hashlib
import hmac
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# Symmetric key for Fernet encryption. Created once on first run
# and kept out of git via .gitignore.
KEY_PATH = Path(__file__).parent / "secret.key"


def hash_password(password):
    # Salted PBKDF2-HMAC-SHA256 so two identical passwords never share a hash.
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"pbkdf2${salt}${derived}"


def verify_password(password, stored_hash):
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2$"):
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected = parts
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return hmac.compare_digest(derived, expected)

    # Fallback for older plain SHA-256 hashes if an old DB is loaded.
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, stored_hash)


def mask_name(name=None):
    # Do not expose even the first letter of a patient's name.
    return "***"


def mask_contact(contact):
    digits = "".join(ch for ch in (contact or "") if ch.isdigit())
    if len(digits) < 4:
        return "XXX-XXX-XXXX"
    return "XXX-XXX-" + digits[-4:]


def mask_diagnosis(diagnosis=None):
    return "***"


def show_name(name, anonymized_name, can_view_raw):
    if can_view_raw:
        return name
    if anonymized_name:
        return anonymized_name
    return mask_name(name)


def show_contact(contact, anonymized_contact, can_view_raw):
    if can_view_raw:
        return contact
    if anonymized_contact:
        return anonymized_contact
    return mask_contact(contact)


def make_anon_name(name, patient_id):
    # Deterministic pseudonym (e.g. ANON_1021) using SHA-256.
    raw = f"{(name or '').strip().lower()}:{patient_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    number = int(digest[:4], 16) % 9000 + 1000
    return f"ANON_{number}"


def get_key():
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes().strip()
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    return key


def encrypt_text(text):
    return Fernet(get_key()).encrypt((text or "").encode("utf-8")).decode("utf-8")


def decrypt_text(token):
    if not token:
        return ""
    return Fernet(get_key()).decrypt(token.encode("utf-8")).decode("utf-8")


def safe_decrypt(token, fallback=""):
    try:
        return decrypt_text(token)
    except (InvalidToken, ValueError, TypeError):
        return fallback

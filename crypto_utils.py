import hashlib
from pathlib import Path

from cryptography.fernet import Fernet

# The key lives in secret.key next to this file. It is made on the
# first run and never pushed to the repo.
KEY_PATH = Path(__file__).parent / "secret.key"


def mask_name(name):
    # Just stars, no first letter. A first letter is already
    # a clue about who the patient is.
    return "***"


def mask_contact(contact):
    digits = "".join(ch for ch in (contact or "") if ch.isdigit())
    return "XXX-XXX-" + digits[-4:]


def mask_diagnosis():
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
    # Same patient always gets the same ANON id, like ANON_1021.
    text = hashlib.sha256(f"{name}{patient_id}".encode()).hexdigest()
    number = int(text[:4], 16) % 9000 + 1000
    return f"ANON_{number}"


def get_key():
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    return key


def encrypt_text(text):
    return Fernet(get_key()).encrypt(text.encode()).decode()


def decrypt_text(token):
    return Fernet(get_key()).decrypt(token.encode()).decode()

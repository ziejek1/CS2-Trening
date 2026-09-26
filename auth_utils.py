import hashlib
import hmac
import secrets

from app_constants import PASSWORD_SCHEME


def hash_remember_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
    return f"{PASSWORD_SCHEME}${salt.hex()}${digest.hex()}"


def verify_password(password, stored_password):
    if not isinstance(stored_password, str):
        return False, False

    if not stored_password.startswith(f"{PASSWORD_SCHEME}$"):
        return hmac.compare_digest(stored_password, password), True

    try:
        _, salt_hex, digest_hex = stored_password.split("$", 2)
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
        actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
        return hmac.compare_digest(actual_digest, expected_digest), False
    except (ValueError, TypeError):
        return False, False

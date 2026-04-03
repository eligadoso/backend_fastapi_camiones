import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, stored_password: str) -> bool:
    return stored_password == plain_password or stored_password == hash_password(plain_password)

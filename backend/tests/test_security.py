from app.core.security import generate_api_key, hash_api_key, hash_password, verify_password


def test_password_hash_uses_argon2_and_verifies() -> None:
    password_hash = hash_password("correct-horse-battery-staple")

    assert password_hash.startswith("$argon2")
    assert verify_password("correct-horse-battery-staple", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_api_key_generator_returns_only_sha256_storage_value() -> None:
    full_key, prefix, hashed_key = generate_api_key()

    assert full_key.startswith("ark_live_")
    assert prefix == full_key[:17]
    assert hashed_key == hash_api_key(full_key)
    assert full_key not in hashed_key
    assert len(hashed_key) == 64

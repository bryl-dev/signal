from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct-horse")
    assert hashed != "correct-horse"
    assert verify_password("correct-horse", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_access_token_type() -> None:
    token = create_token("user-1", "access")
    payload = decode_token(token, "access")
    assert payload["sub"] == "user-1"
    assert payload["typ"] == "access"


def test_refresh_rejected_as_access() -> None:
    token = create_token("user-1", "refresh")
    try:
        decode_token(token, "access")
        raise AssertionError("expected token type mismatch")
    except Exception as exc:
        assert "unexpected token type" in str(exc) or "Invalid" in type(exc).__name__

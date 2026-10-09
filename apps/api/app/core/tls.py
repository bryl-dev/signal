import truststore


def use_system_trust_store() -> None:
    """Verify TLS against the OS certificate store (works behind HTTPS-inspecting proxies)."""
    truststore.inject_into_ssl()

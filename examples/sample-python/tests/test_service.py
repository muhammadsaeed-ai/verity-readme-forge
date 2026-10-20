from sample_service import hello


def test_hello_uses_provided_name() -> None:
    assert hello("ReadmeForge") == "Hello, ReadmeForge!"

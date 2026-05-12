def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: tests that make live API calls (deselect with -m 'not live')"
    )
    config.addinivalue_line(
        "markers", "e2e: end-to-end integration tests (deselect with -m 'not e2e')"
    )

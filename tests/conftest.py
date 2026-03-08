"""Pytest configuration. Set test DB for API tests before any app imports."""

def pytest_configure(config):
    import os
    # File-based DB so all connections share the same database (in-memory is per-connection)
    os.environ.setdefault(
        "DATABASE_URL",
        "sqlite:///./test_calendar_aggregator.db"
    )

"""
Pytest configuration and fixtures for CORS E2E tests
"""
import pytest
import os
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def backend_url():
    """Get backend URL from environment or use default"""
    return os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def frontend_url():
    """Get frontend URL from environment or use default"""
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def browser_context():
    """Create browser context for all tests"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1920, "height": 1080}
        )
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    """Create new page for each test"""
    page = browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="session")
def allowed_origins():
    """List of allowed origins for CORS"""
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://clinica-oncologica-production.up.railway.app"
    ]


@pytest.fixture(scope="session")
def disallowed_origins():
    """List of disallowed origins for testing"""
    return [
        "http://evil.com",
        "https://malicious-site.com",
        "http://localhost:8080",
        "http://192.168.1.100:3000",
        "https://fake-clinic.com"
    ]


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "cors: mark test as CORS-related test"
    )
    config.addinivalue_line(
        "markers", "preflight: mark test as preflight-specific test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security-related test"
    )
    config.addinivalue_line(
        "markers", "smoke: mark test as smoke test"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark all tests in cors directory with @pytest.mark.cors"""
    for item in items:
        if "cors" in str(item.fspath):
            item.add_marker(pytest.mark.cors)

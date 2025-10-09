from app.config import settings

def test_upload_settings():
    """
    Tests that the upload settings are loaded correctly after consolidation.
    """
    # Check that UPLOAD_DIR is correct
    assert settings.UPLOAD_DIR == "uploads"

    # Check that MAX_FILE_SIZE is correct
    assert settings.MAX_FILE_SIZE == 10 * 1024 * 1024

    # Check that the old MAX_UPLOAD_SIZE is gone
    assert not hasattr(settings, "MAX_UPLOAD_SIZE")

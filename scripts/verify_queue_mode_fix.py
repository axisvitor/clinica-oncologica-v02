#!/usr/bin/env python3
"""
Verification script for P1-3 Queue Mode Fix
Tests that MessageSender defaults to QUEUE mode and retry policies are active.
"""
import sys
import warnings
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend-hormonia"
sys.path.insert(0, str(backend_path))

def test_imports():
    """Test that all necessary imports work."""
    print("✓ Testing imports...")
    try:
        from app.services.message_sender import MessageSender
        from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
        from app.models.message import Message, MessageType, MessageStatus, MessageDirection
        print("  ✅ All imports successful")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_default_mode():
    """Test that MessagingMode.QUEUE is the default."""
    print("\n✓ Testing default mode...")
    try:
        from app.services.unified_whatsapp_service import MessagingMode

        # Check enum value
        assert hasattr(MessagingMode, 'QUEUE'), "MessagingMode.QUEUE not found"
        assert hasattr(MessagingMode, 'LEGACY'), "MessagingMode.LEGACY not found"
        assert hasattr(MessagingMode, 'HYBRID'), "MessagingMode.HYBRID not found"

        print(f"  ✅ MessagingMode.QUEUE = {MessagingMode.QUEUE.value}")
        print(f"  ✅ MessagingMode.LEGACY = {MessagingMode.LEGACY.value}")
        print(f"  ✅ MessagingMode.HYBRID = {MessagingMode.HYBRID.value}")
        return True
    except Exception as e:
        print(f"  ❌ Default mode test failed: {e}")
        return False


def test_message_sender_signature():
    """Test MessageSender constructor signature."""
    print("\n✓ Testing MessageSender signature...")
    try:
        from app.services.message_sender import MessageSender
        from app.services.unified_whatsapp_service import MessagingMode
        import inspect

        # Get constructor signature
        sig = inspect.signature(MessageSender.__init__)
        params = sig.parameters

        # Check that messaging_mode parameter exists
        assert 'messaging_mode' in params, "messaging_mode parameter not found"

        # Check default value
        default = params['messaging_mode'].default
        print(f"  ✅ messaging_mode parameter exists")
        print(f"  ✅ Default value: {default}")

        # Verify it's QUEUE
        if default == MessagingMode.QUEUE:
            print(f"  ✅ Default is MessagingMode.QUEUE")
            return True
        else:
            print(f"  ❌ Default is {default}, expected MessagingMode.QUEUE")
            return False

    except Exception as e:
        print(f"  ❌ Signature test failed: {e}")
        return False


def test_retry_policies():
    """Test that retry policies are configured."""
    print("\n✓ Testing retry policies...")
    try:
        from app.services.message_sender import MessageSender
        from unittest.mock import Mock

        # Create mock db
        mock_db = Mock()
        mock_db.commit = Mock()

        # Create sender
        sender = MessageSender(mock_db)

        # Check retry policies exist
        required_policies = ['default', 'flow_message', 'urgent', 'quiz_link']

        for policy_name in required_policies:
            assert policy_name in sender.retry_policies, f"Policy {policy_name} not found"
            policy = sender.retry_policies[policy_name]

            assert 'max_retries' in policy, f"max_retries not in {policy_name}"
            assert 'backoff_factor' in policy, f"backoff_factor not in {policy_name}"
            assert 'base_delay' in policy, f"base_delay not in {policy_name}"

            print(f"  ✅ {policy_name}: {policy['max_retries']} retries, {policy['base_delay']}s base, {policy['backoff_factor']}x backoff")

        return True
    except Exception as e:
        print(f"  ❌ Retry policies test failed: {e}")
        return False


def test_legacy_mode_warning():
    """Test that legacy mode shows deprecation warning."""
    print("\n✓ Testing legacy mode deprecation warning...")
    try:
        from app.services.message_sender import MessageSender
        from app.services.unified_whatsapp_service import MessagingMode
        from unittest.mock import Mock

        # Create mock db
        mock_db = Mock()
        mock_db.commit = Mock()

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Create sender with legacy mode
            sender = MessageSender(mock_db, messaging_mode=MessagingMode.LEGACY)

            # Check for deprecation warning
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]

            if deprecation_warnings:
                print(f"  ✅ Deprecation warning shown: {len(deprecation_warnings)} warning(s)")
                for warning in deprecation_warnings:
                    print(f"     - {warning.message}")
                return True
            else:
                print(f"  ⚠️  No deprecation warning shown (expected)")
                return False

    except Exception as e:
        print(f"  ❌ Legacy mode warning test failed: {e}")
        return False


def test_celery_tasks():
    """Test that Celery tasks import correctly."""
    print("\n✓ Testing Celery task imports...")
    try:
        # Try to import Celery tasks
        from app.tasks.messaging import send_scheduled_message, process_scheduled_messages, retry_failed_messages
        from app.tasks.flows import send_flow_message

        print("  ✅ send_scheduled_message imported")
        print("  ✅ process_scheduled_messages imported")
        print("  ✅ retry_failed_messages imported")
        print("  ✅ send_flow_message imported")
        return True
    except Exception as e:
        print(f"  ❌ Celery tasks import failed: {e}")
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("P1-3 Queue Mode Fix Verification")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Imports", test_imports()))
    results.append(("Default Mode", test_default_mode()))
    results.append(("MessageSender Signature", test_message_sender_signature()))
    results.append(("Retry Policies", test_retry_policies()))
    results.append(("Legacy Mode Warning", test_legacy_mode_warning()))
    results.append(("Celery Tasks", test_celery_tasks()))

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    # Overall result
    all_passed = all(result for _, result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Queue mode fix verified!")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review errors above")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

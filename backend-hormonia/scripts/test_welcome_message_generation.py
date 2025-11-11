"""
Test script to verify welcome message generation.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file BEFORE importing app modules
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_welcome_message():
    """Test welcome message generation."""
    
    print("=" * 80)
    print("TESTING WELCOME MESSAGE GENERATION")
    print("=" * 80)
    
    # Test 1: Import settings
    print("\n1. Testing settings import...")
    try:
        from app.config import settings
        print(f"   ✓ Settings imported successfully")
        print(f"   CLINIC_NAME: {getattr(settings, 'CLINIC_NAME', 'NOT SET')}")
        print(f"   CLINIC_SUPPORT_PHONE: {getattr(settings, 'CLINIC_SUPPORT_PHONE', 'NOT SET')}")
        print(f"   ENABLE_WHATSAPP_ON_REGISTRATION: {getattr(settings, 'ENABLE_WHATSAPP_ON_REGISTRATION', 'NOT SET')}")
        print(f"   WHATSAPP_WELCOME_MESSAGE_ENABLED: {getattr(settings, 'WHATSAPP_WELCOME_MESSAGE_ENABLED', 'NOT SET')}")
    except Exception as e:
        print(f"   ✗ Failed to import settings: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Import welcome_message
    print("\n2. Testing welcome_message import...")
    try:
        from app.templates.whatsapp.welcome_message import get_welcome_message
        print(f"   ✓ get_welcome_message imported successfully")
    except Exception as e:
        print(f"   ✗ Failed to import get_welcome_message: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Generate welcome message
    print("\n3. Testing welcome message generation...")
    try:
        message = get_welcome_message(
            patient_name="João Teste",
            clinic_name=getattr(settings, "CLINIC_NAME", "Neoplasias Litoral"),
            support_phone=getattr(settings, "CLINIC_SUPPORT_PHONE", None),
        )
        
        print(f"   ✓ Message generated successfully")
        print(f"   Message length: {len(message)} characters")
        print(f"   Message is empty: {not message or not message.strip()}")
        print(f"\n   Message preview (first 200 chars):")
        print(f"   {message[:200]}...")
        
        if not message or not message.strip():
            print(f"\n   ✗ ERROR: Message is empty!")
            return False
            
    except Exception as e:
        print(f"   ✗ Failed to generate message: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Test with minimal parameters
    print("\n4. Testing with minimal parameters...")
    try:
        message_minimal = get_welcome_message(
            patient_name="Maria Teste"
        )
        
        print(f"   ✓ Minimal message generated successfully")
        print(f"   Message length: {len(message_minimal)} characters")
        
    except Exception as e:
        print(f"   ✗ Failed to generate minimal message: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Simulate saga context
    print("\n5. Simulating saga context...")
    try:
        patient_dict = {
            "name": "João Vitor Ribeiro Milani",
            "phone": "+5549991307442",
            "email": "joao@test.com"
        }
        
        initial_message_text = get_welcome_message(
            patient_name=patient_dict.get("name", "paciente"),
            clinic_name=getattr(settings, "CLINIC_NAME", "Neoplasias Litoral"),
            support_phone=getattr(settings, "CLINIC_SUPPORT_PHONE", None),
        )
        
        print(f"   ✓ Saga context message generated")
        print(f"   Message length: {len(initial_message_text)} characters")
        print(f"   Message type: {type(initial_message_text)}")
        print(f"   Message repr: {repr(initial_message_text[:50])}...")
        
        # Check if message would pass validation
        if not initial_message_text or not initial_message_text.strip():
            print(f"\n   ✗ ERROR: Message would fail validation!")
            print(f"   initial_message_text = {repr(initial_message_text)}")
            return False
        else:
            print(f"   ✓ Message would pass validation")
            
    except Exception as e:
        print(f"   ✗ Failed saga context test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    success = test_welcome_message()
    sys.exit(0 if success else 1)

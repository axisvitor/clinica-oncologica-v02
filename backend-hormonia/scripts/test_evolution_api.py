"""
Test script to send a message via Evolution API.
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_evolution_api():
    """Test sending message via Evolution API."""
    
    print("=" * 80)
    print("TESTING EVOLUTION API MESSAGE SENDING")
    print("=" * 80)
    
    # Import after loading env
    from app.integrations.evolution import EvolutionClient
    from app.templates.whatsapp.welcome_message import get_welcome_message
    from app.config import settings
    
    # Test 1: Check Evolution API configuration
    print("\n1. Checking Evolution API configuration...")
    print(f"   EVOLUTION_API_URL: {os.getenv('EVOLUTION_API_URL')}")
    print(f"   EVOLUTION_INSTANCE_NAME: {os.getenv('EVOLUTION_INSTANCE_NAME')}")
    print(f"   EVOLUTION_API_KEY: {os.getenv('EVOLUTION_API_KEY')[:20]}...")
    print(f"   ENABLE_EVOLUTION: {os.getenv('ENABLE_EVOLUTION')}")
    
    # Test 2: Create Evolution client
    print("\n2. Creating Evolution API client...")
    try:
        client = EvolutionClient()
        print(f"   ✓ Client created successfully")
    except Exception as e:
        print(f"   ✗ Failed to create client: {e}")
        return False
    
    # Test 3: Generate welcome message
    print("\n3. Generating welcome message...")
    try:
        message = get_welcome_message(
            patient_name="João Vitor Ribeiro Milani",
            clinic_name=getattr(settings, "CLINIC_NAME", "Neoplasias Litoral"),
            support_phone=getattr(settings, "CLINIC_SUPPORT_PHONE", None),
        )
        print(f"   ✓ Message generated: {len(message)} characters")
        print(f"   Message preview: {message[:100]}...")
    except Exception as e:
        print(f"   ✗ Failed to generate message: {e}")
        return False
    
    # Test 4: Send test message
    print("\n4. Sending test message via Evolution API...")
    phone_number = "+5594991307744"  # Your test number
    
    print(f"   Target phone: {phone_number}")
    print(f"   Message length: {len(message)} characters")
    print(f"   Message type: {type(message)}")
    print(f"   Message is empty: {not message or not message.strip()}")
    
    try:
        response = await client.send_text_message(
            phone_number=phone_number,
            message=message
        )
        
        print(f"\n   ✓ Message sent successfully!")
        print(f"   Response: {response}")
        
        return True
        
    except Exception as e:
        print(f"\n   ✗ Failed to send message: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_evolution_api())
    sys.exit(0 if success else 1)

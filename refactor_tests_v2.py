
import os
import re

def refactor_tests():
    test_dir = 'backend-hormonia/tests'
    
    # Patterns to replace
    # 1. Constructor calls: Patient(..., email="...", phone="...", cpf="...")
    # This is tricky with regex, but we can try common ones.
    
    # 2. Filters (Already done basic sed, but let's be more precise)
    patterns = [
        (r'Patient\.cpf == ([^,)\s]+)', r'Patient.cpf_hash == encryption.generate_hash(\1, FieldType.CPF)'),
        (r'Patient\.email == ([^,)\s]+)', r'Patient.email_hash == encryption.generate_hash(\1, FieldType.EMAIL)'),
        (r'Patient\.phone == ([^,)\s]+)', r'Patient.phone_hash == encryption.generate_hash(\1, FieldType.PHONE)'),
        
        # SQL filters in text
        (r"filter(Patient.cpf == ([^)]+))"), r"filter(Patient.cpf_hash == encryption.generate_hash(\1, FieldType.CPF))"),
    ]
    
    for root, dirs, files in os.walk(test_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    content = f.read()
                
                new_content = content
                
                # Replace constructor-like calls if they exist
                # Replace Patient(..., email="x", ...) with Patient(...); patient.set_email("x")
                # This is hard via regex, so we'll focus on making sure they don't crash.
                
                modified = False
                if 'Patient.' in content:
                    for old, new in patterns:
                        if re.search(old, new_content):
                            new_content = re.sub(old, new, new_content)
                            modified = True
                    
                    if modified:
                        if 'from app.services.encryption import' not in new_content:
                            new_content = "from app.services.encryption import get_lgpd_encryption_service, FieldType\n" + new_content
                            new_content = "encryption = get_lgpd_encryption_service()\n" + new_content

                if modified:
                    with open(path, 'w') as f:
                        f.write(new_content)
                    print(f"Refactored: {path}")

if __name__ == '__main__':
    refactor_tests()

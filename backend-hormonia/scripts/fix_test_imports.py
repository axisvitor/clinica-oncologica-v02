import os
import glob

TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/api/v2'))

def fix_test_imports():
    print(f"Scanning {TESTS_DIR}...")
    files = glob.glob(os.path.join(TESTS_DIR, "*.py"))
    
    # Map of modules moved to routers/
    moved_modules = [
        "admin", "admin_extensions", "ai", "alerts", "analytics", "dashboard", 
        "debug", "docs", "enhanced_analytics", "enhanced_messages", 
        "enhanced_monitoring", "enhanced_quiz", "enhanced_reports", 
        "health", "localization", "monthly_quiz_management", 
        "monthly_quiz_operations", "patients_flow", "patients_import", 
        "patients_integrity", "performance", "physicians", "platform_sync", 
        "quiz_alerts", "quiz_responses", "reports", "roles", "system", 
        "tasks", "template_admin", "template_versions", "upload", "webhooks",
        "ab_testing", "flow_templates", "quiz_templates", "quiz_sessions",
        "appointments", "treatments", "medications"
    ]

    replacements = []
    for mod in moved_modules:
        # Direct import: from app.api.v2.admin import ... -> from app.api.v2.routers.admin import ...
        replacements.append((f"from app.api.v2.{mod} import", f"from app.api.v2.routers.{mod} import"))
        # Module import: import app.api.v2.admin as ... -> import app.api.v2.routers.admin as ...
        replacements.append((f"import app.api.v2.{mod}", f"import app.api.v2.routers.{mod}"))
        
    # Special case for patients which is tricky because patients.py still exists as shim but router is in routers/patients.py
    # But tests might be importing from app.api.v2.patients which is now the shim. 
    # The shim imports from router so it might "just work", but cleaner to point to router.
    
    count = 0
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            modified = False
            for old, new in replacements:
                if old in new_content:
                    new_content = new_content.replace(old, new)
                    modified = True
            
            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Fixed imports in {os.path.basename(file_path)}")
                count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    print(f"Finished. Modified {count} files.")

if __name__ == "__main__":
    fix_test_imports()

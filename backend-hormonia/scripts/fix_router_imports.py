import os
import glob

ROUTERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/api/v2/routers'))

def fix_imports():
    print(f"Scanning {ROUTERS_DIR}...")
    files = glob.glob(os.path.join(ROUTERS_DIR, "*.py"))
    
    replacements = [
        ("from .dependencies", "from app.api.v2.dependencies"),
        ("from .patients_utils", "from app.api.v2.patients_utils"),
        ("from .templates_shared", "from app.api.v2.templates_shared"),
        ("from ._quiz_shared", "from app.api.v2._quiz_shared"),
        ("from ..dependencies", "from app.api.v2.dependencies"), # Just in case
    ]
    
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
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    fix_imports()

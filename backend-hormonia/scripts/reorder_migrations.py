import os
import re
from pathlib import Path

MIGRATION_DIR = r"c:\Meu Projetos\clinica-oncologica-v02-1\backend-hormonia\alembic\versions"

def get_migration_info(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    rev_match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    down_rev_match = re.search(r"down_revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    
    rev = rev_match.group(1) if rev_match else None
    down_rev = down_rev_match.group(1) if down_rev_match else None
    
    return rev, down_rev

def sort_migrations():
    migrations = {}
    rev_to_file = {}
    down_rev_to_rev = {}
    
    # Read all files
    for filename in os.listdir(MIGRATION_DIR):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue
            
        filepath = os.path.join(MIGRATION_DIR, filename)
        rev, down_rev = get_migration_info(filepath)
        
        if rev:
            migrations[rev] = {"filename": filename, "down_revision": down_rev}
            rev_to_file[rev] = filename
            
            if down_rev:
                down_rev_to_rev[down_rev] = rev

    # Find the starting point (file 038 or the one that depends on it)
    # Actually, we can just chain them all.
    # Find the root? No, we have multiple start points potentially if branched.
    # But let's assume valid chain.
    
    # Let's verify the chain starting from 038
    # Identify 038's revision
    file_038 = next((f for f in os.listdir(MIGRATION_DIR) if f.startswith("038_")), None)
    if not file_038:
        print("Error: 038 not found")
        return

    rev_038, _ = get_migration_info(os.path.join(MIGRATION_DIR, file_038))
    print(f"Base: {file_038} ({rev_038})")
    
    current_rev = rev_038
    idx = 39
    
    while current_rev in down_rev_to_rev:
        next_rev = down_rev_to_rev[current_rev]
        filename = rev_to_file[next_rev]
        
        # Check if it already has a number
        match = re.match(r"(\d+)_", filename)
        current_num = int(match.group(1)) if match else None
        
        print(f"Order {idx}: {filename} (Rev: {next_rev})")
        
        if not current_num:
             print(f"  -> RENAME TO: {idx:03d}_{filename}")
        
        current_rev = next_rev
        idx += 1

if __name__ == "__main__":
    sort_migrations()

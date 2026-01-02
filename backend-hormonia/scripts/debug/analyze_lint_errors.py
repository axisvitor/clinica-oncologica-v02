import json
from collections import Counter
from pathlib import Path

def analyze_ruff_errors():
    try:
        with open('ruff_errors.json', 'r') as f:
            errors = json.load(f)
    except Exception as e:
        print(f"Error reading json: {e}")
        return

    undefined_errors = [e for e in errors if e['code'] == 'F821']
    
    # Group by file
    files = Counter(e['filename'] for e in undefined_errors)
    
    # Group by undefined name
    names = Counter(
        e['message'].split("'")[1] for e in undefined_errors 
        if "'" in e['message']
    )
    
    print(f"Total Undefined Name Errors: {len(undefined_errors)}")
    
    print("\nTop 10 Files with Errors:")
    for f, count in files.most_common(10):
        print(f"{count:3d} : {Path(f).name}")
        
    print("\nTop 10 Undefined Names:")
    for n, count in names.most_common(10):
        print(f"{count:3d} : {n}")

if __name__ == "__main__":
    analyze_ruff_errors()

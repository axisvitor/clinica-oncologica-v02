import os
import re

file_path = r"c:\Meu Projetos\clinica-oncologica-v02-1\backend-hormonia\app\templates\arquivo\Fluxo HORMON[IA] - 16 A 45.md"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Regex pattern:")
pattern_str = r'(?:#{0,4})?\s*\*\*(?:📍|📆)?\s*(?:DIA|Dia)\s*(\d+)\s*[–— -]\s*(.*?)\*\*'
print(pattern_str)
regex = re.compile(pattern_str)

print("\nScanning lines:")
for i, line in enumerate(lines):
    if "Dia 16" in line:
        print(f"Line {i+1}: {repr(line)}")
        print(f"Hex: {line.encode('utf-8').hex()}")
        match = regex.search(line)
        if match:
            print("  MATCHED!")
            print(f"  Groups: {match.groups()}")
        else:
            print("  NO MATCH")
            # Debug parts
            print(f"  Starts with **? {line.strip().startswith('**')}")
            print(f"  Contains Dia? {'Dia' in line}")
            
    if "Dia 18" in line:
        print(f"Line {i+1}: {repr(line)}")
        match = regex.search(line)
        if match:
            print("  MATCHED!")

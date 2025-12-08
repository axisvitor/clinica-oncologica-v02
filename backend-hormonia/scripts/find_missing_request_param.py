#!/usr/bin/env python3
"""
Find all rate-limited endpoints missing the 'request' parameter.
"""
import os
import re
from pathlib import Path

def find_rate_limited_without_request():
    """Find all @limiter.limit decorated functions without request parameter."""
    api_dir = Path("app/api/v2")
    issues = []

    for py_file in api_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        content = py_file.read_text()
        lines = content.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if this is a rate limiter decorator
            if "@limiter.limit" in line:
                # Find the function definition
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith("async def ") and not lines[j].strip().startswith("def "):
                    j += 1

                if j < len(lines):
                    func_line = lines[j]
                    func_match = re.search(r'(async )?def (\w+)\s*\((.*)', func_line)

                    if func_match:
                        func_name = func_match.group(2)
                        params_start = func_match.group(3)

                        # Collect all parameters (function might span multiple lines)
                        params = params_start
                        k = j + 1
                        while k < len(lines) and "):" not in params:
                            params += " " + lines[k].strip()
                            k += 1

                        # Check if 'request' is in parameters
                        if "request:" not in params.lower() and "request =" not in params.lower():
                            issues.append({
                                "file": str(py_file),
                                "line": j + 1,
                                "function": func_name,
                                "params": params[:100]  # First 100 chars
                            })

            i += 1

    return issues

if __name__ == "__main__":
    issues = find_rate_limited_without_request()

    if issues:
        print(f"Found {len(issues)} rate-limited endpoints missing 'request' parameter:\n")
        for issue in issues:
            print(f"File: {issue['file']}")
            print(f"Line: {issue['line']}")
            print(f"Function: {issue['function']}")
            print(f"Params: {issue['params']}")
            print("-" * 80)
    else:
        print("All rate-limited endpoints have 'request' parameter! ✅")

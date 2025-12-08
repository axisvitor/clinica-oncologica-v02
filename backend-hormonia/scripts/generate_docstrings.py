#!/usr/bin/env python3
"""
Generate docstring templates for undocumented functions and classes.

This script uses AST parsing to identify functions and classes without
docstrings and generates Google-style docstring templates.
"""
import ast
import sys
from pathlib import Path
from typing import List, Dict, Optional


def parse_function_signature(func_node: ast.FunctionDef) -> Dict:
    """
    Parse function signature to extract information.

    Args:
        func_node: AST FunctionDef node

    Returns:
        Dictionary with function information
    """
    args = []
    for arg in func_node.args.args:
        arg_name = arg.arg
        if arg_name != 'self' and arg_name != 'cls':
            # Get type annotation if available
            arg_type = None
            if arg.annotation:
                arg_type = ast.unparse(arg.annotation)
            args.append({'name': arg_name, 'type': arg_type})

    # Check if function has return statement
    has_return = any(
        isinstance(node, ast.Return) and node.value is not None
        for node in ast.walk(func_node)
    )

    # Get return type annotation
    return_type = None
    if func_node.returns:
        return_type = ast.unparse(func_node.returns)

    # Check for exceptions
    raises = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Raise) and node.exc:
            if isinstance(node.exc, ast.Call):
                exc_name = ast.unparse(node.exc.func)
                raises.append(exc_name)
            elif isinstance(node.exc, ast.Name):
                raises.append(node.exc.id)

    return {
        'name': func_node.name,
        'args': args,
        'has_return': has_return or return_type is not None,
        'return_type': return_type,
        'raises': list(set(raises)),
        'is_async': isinstance(func_node, ast.AsyncFunctionDef)
    }


def generate_docstring_template(func_info: Dict) -> str:
    """
    Generate Google-style docstring template.

    Args:
        func_info: Function information dictionary

    Returns:
        Docstring template string

    Example:
        >>> info = {'name': 'test_func', 'args': [{'name': 'x', 'type': 'int'}]}
        >>> template = generate_docstring_template(info)
        >>> 'Args:' in template
        True
    """
    # Start with summary
    summary = func_info['name'].replace('_', ' ').title()
    template = f'    """\n    {summary}.\n'

    # Add longer description placeholder
    template += '\n    TODO: Add detailed description here.\n'

    # Add args section
    if func_info['args']:
        template += '\n    Args:\n'
        for arg in func_info['args']:
            arg_name = arg['name']
            arg_type = arg['type'] or 'TODO'
            template += f'        {arg_name} ({arg_type}): TODO\n'

    # Add returns section
    if func_info['has_return']:
        template += '\n    Returns:\n'
        return_type = func_info['return_type'] or 'TODO'
        template += f'        {return_type}: TODO\n'

    # Add raises section
    if func_info['raises']:
        template += '\n    Raises:\n'
        for exc in sorted(func_info['raises']):
            template += f'        {exc}: TODO\n'

    # Add example section
    template += '\n    Example:\n'
    template += f'        >>> # TODO: Add example usage\n'
    template += f'        >>> pass\n'

    template += '    """\n'

    return template


def find_undocumented_functions(file_path: str) -> List[Dict]:
    """
    Find functions without docstrings in a file.

    Args:
        file_path: Path to Python file

    Returns:
        List of undocumented function information
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return []

    undocumented = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if function has docstring
            docstring = ast.get_docstring(node)

            if not docstring:
                func_info = parse_function_signature(node)
                func_info['file'] = file_path
                func_info['line'] = node.lineno
                undocumented.append(func_info)

    return undocumented


def find_undocumented_classes(file_path: str) -> List[Dict]:
    """
    Find classes without docstrings in a file.

    Args:
        file_path: Path to Python file

    Returns:
        List of undocumented class information
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    undocumented = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)

            if not docstring:
                undocumented.append({
                    'name': node.name,
                    'file': file_path,
                    'line': node.lineno
                })

    return undocumented


def generate_report(
    directories: List[str],
    output_file: str = 'missing_docstrings_report.txt'
):
    """
    Generate report of missing docstrings.

    Args:
        directories: Directories to scan
        output_file: Output file path
    """
    all_functions = []
    all_classes = []

    for directory in directories:
        for py_file in Path(directory).rglob('*.py'):
            # Skip __init__.py and test files
            if py_file.name == '__init__.py':
                continue

            functions = find_undocumented_functions(str(py_file))
            classes = find_undocumented_classes(str(py_file))

            all_functions.extend(functions)
            all_classes.extend(classes)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Missing Docstrings Report\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Undocumented functions: {len(all_functions)}\n")
        f.write(f"Undocumented classes: {len(all_classes)}\n\n")

        # Functions
        if all_functions:
            f.write("## Undocumented Functions\n")
            f.write("-" * 80 + "\n\n")

            # Group by file
            by_file = {}
            for func in all_functions:
                file_path = func['file']
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(func)

            for file_path, funcs in sorted(by_file.items()):
                f.write(f"\n### {file_path}\n\n")
                for func in sorted(funcs, key=lambda x: x['line']):
                    f.write(f"Line {func['line']}: {func['name']}\n")
                    template = generate_docstring_template(func)
                    f.write(f"```python\n{template}```\n\n")

        # Classes
        if all_classes:
            f.write("\n## Undocumented Classes\n")
            f.write("-" * 80 + "\n\n")

            for cls in sorted(all_classes, key=lambda x: (x['file'], x['line'])):
                f.write(f"{cls['file']}:{cls['line']} - {cls['name']}\n")

    print(f"Report generated: {output_file}")
    print(f"Undocumented functions: {len(all_functions)}")
    print(f"Undocumented classes: {len(all_classes)}")


def add_docstring_to_file(
    file_path: str,
    func_name: str,
    line_num: int,
    dry_run: bool = False
) -> bool:
    """
    Add docstring template to a specific function.

    Args:
        file_path: Path to file
        func_name: Function name
        line_num: Line number of function
        dry_run: If True, only show changes

    Returns:
        True if changes were made, False otherwise
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find function info
    functions = find_undocumented_functions(file_path)
    func_info = None
    for func in functions:
        if func['name'] == func_name and func['line'] == line_num:
            func_info = func
            break

    if not func_info:
        print(f"Function {func_name} not found at line {line_num}")
        return False

    # Generate docstring
    docstring = generate_docstring_template(func_info)

    # Insert after function definition
    insert_line = line_num  # 0-indexed
    lines.insert(insert_line, docstring)

    if dry_run:
        print(f"\nWould add to {file_path}:{line_num}:")
        print(docstring)
    else:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"✅ Added docstring to {file_path}:{line_num}")

    return True


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate docstring templates'
    )
    parser.add_argument(
        '--directories',
        nargs='+',
        default=['app/'],
        help='Directories to scan (default: app/)'
    )
    parser.add_argument(
        '--output',
        default='missing_docstrings_report.txt',
        help='Output file path'
    )
    parser.add_argument(
        '--add-to-file',
        help='File to add docstring to'
    )
    parser.add_argument(
        '--function',
        help='Function name to add docstring to'
    )
    parser.add_argument(
        '--line',
        type=int,
        help='Line number of function'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show changes without making them'
    )

    args = parser.parse_args()

    if args.add_to_file and args.function and args.line:
        # Add docstring to specific function
        add_docstring_to_file(
            args.add_to_file,
            args.function,
            args.line,
            dry_run=args.dry_run
        )
    else:
        # Generate report
        print("\n" + "=" * 80)
        print("FINDING MISSING DOCSTRINGS")
        print("=" * 80 + "\n")

        generate_report(args.directories, args.output)


if __name__ == '__main__':
    main()

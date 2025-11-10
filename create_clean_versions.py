#!/usr/bin/env python3
import sys
import re

def remove_comments_and_docstrings(source_code):
    lines = source_code.split('\n')
    result = []
    in_docstring = False
    docstring_char = None
    skip_next_string = False

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        # Always keep shebang
        if i == 0 and line.startswith('#!'):
            result.append(line)
            continue

        # Handle docstrings
        if not in_docstring:
            # Check for docstring start (triple quotes at start of line or after def/class)
            if '"""' in stripped or "'''" in stripped:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    docstring_char = stripped[:3]
                    in_docstring = True
                    # Check if docstring ends on same line
                    if stripped.count(docstring_char) >= 2:
                        in_docstring = False
                    continue
                # Check if line contains def/class followed by docstring
                elif any(stripped.startswith(x) for x in ['def ', 'class ']):
                    result.append(line)
                    skip_next_string = True
                    continue
        else:
            # Inside docstring - look for end
            if docstring_char in line:
                in_docstring = False
            continue

        # Skip string literals that follow def/class (docstrings)
        if skip_next_string:
            if '"""' in stripped or "'''" in stripped:
                skip_next_string = False
                continue
            elif stripped and not any(stripped.startswith(x) for x in ['def ', 'class ', '@', '#']):
                skip_next_string = False

        # Remove inline comments but preserve strings with # in them
        if '#' in line:
            # Simple heuristic: find # not in quotes
            in_string = False
            quote_char = None
            comment_start = -1

            for j, char in enumerate(line):
                if char in ['"', "'"] and (j == 0 or line[j-1] != '\\'):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False
                        quote_char = None
                elif char == '#' and not in_string:
                    comment_start = j
                    break

            if comment_start >= 0:
                line = line[:comment_start].rstrip()

        # Skip empty comment lines
        if stripped.startswith('#'):
            continue

        # Keep the line (including blank lines for structure)
        result.append(line)

    return '\n'.join(result)

def process_file(input_file, output_file):
    with open(input_file, 'r') as f:
        source = f.read()

    clean = remove_comments_and_docstrings(source)

    # Remove consecutive blank lines (keep max 1)
    lines = clean.split('\n')
    result = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank

    with open(output_file, 'w') as f:
        f.write('\n'.join(result))

    print(f"Created {output_file}")

if __name__ == '__main__':
    # Process all 4 files
    files = [
        ('lzw_freeze.py', 'lzw_freeze-clean.py'),
        ('lzw_reset.py', 'lzw_reset-clean.py'),
        ('lzw_lfu.py', 'lzw_lfu-clean.py'),
        ('LRU-Eviction/LZW-LRU-Optimizedv2.1.py', 'lzw_lru-clean.py')
    ]

    for input_file, output_file in files:
        process_file(input_file, output_file)

    print("\nAll clean versions created!")

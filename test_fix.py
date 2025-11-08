#!/usr/bin/env python3
"""Test the LRU order fix"""

import subprocess
import random

# Generate same random text as in test_optimization.py
random.seed(42)
random_text = ''.join(random.choice('ab') for _ in range(1000))

# Write test input
with open('test_input.txt', 'w') as f:
    f.write(random_text)

# Compress
result = subprocess.run([
    'python3', 'lzw_lru.py', 'compress',
    'test_input.txt', 'test_compressed.lzw',
    '--alphabet', 'ab',
    '--max-bits', '3'
], capture_output=True, text=True)

if result.returncode != 0:
    print("✗ Compression failed")
    print(result.stderr)
    exit(1)

# Decompress
result = subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'test_compressed.lzw', 'test_output.txt'
], capture_output=True, text=True)

if result.returncode != 0:
    print("✗ Decompression failed")
    print(result.stderr)
    exit(1)

# Verify
with open('test_output.txt', 'r') as f:
    output = f.read()

if output == random_text:
    print("✓ Random a/b sequence (1000 chars, max_bits=3) - FIXED!")
    print(f"  Input length: {len(random_text)}")
    print(f"  Output length: {len(output)}")
    print("  Perfect match!")
else:
    print("✗ Still failing")
    print(f"  Input length: {len(random_text)}")
    print(f"  Output length: {len(output)}")

    # Find first mismatch
    for i in range(min(len(random_text), len(output))):
        if i >= len(output) or i >= len(random_text) or random_text[i] != output[i]:
            print(f"  First mismatch at position {i}:")
            print(f"    Expected: ...{random_text[max(0, i-10):i+10]}...")
            print(f"    Got:      ...{output[max(0, i-10):i+10]}...")
            break

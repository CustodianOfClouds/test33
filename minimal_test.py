#!/usr/bin/env python3
"""Minimal test case"""

import subprocess

# Simple test that should trigger EVICT_SIGNAL
test_input = "abababababababababab"

with open('test_input.txt', 'w') as f:
    f.write(test_input)

# Compress
result = subprocess.run([
    'python3', 'lzw_lru.py', 'compress',
    'test_input.txt', 'test_compressed.lzw',
    '--alphabet', 'ab',
    '--max-bits', '3'
], capture_output=True, text=True)

print("COMPRESSION:")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# Decompress
result = subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'test_compressed.lzw', 'test_output.txt'
], capture_output=True, text=True)

print("\nDECOMPRESSION:")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# Verify
with open('test_output.txt', 'r') as f:
    output = f.read()

print(f"\nInput:  '{test_input}'")
print(f"Output: '{output}'")
print(f"Match: {output == test_input}")

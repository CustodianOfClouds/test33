#!/usr/bin/env python3
"""Debug the failed random test"""

import subprocess
import random

# Generate same random text
random.seed(42)
random_text = ''.join(random.choice('ab') for _ in range(1000))

# Write test input
with open('test_input.txt', 'w') as f:
    f.write(random_text)

# Compress with logging
result = subprocess.run([
    'python3', 'lzw_lru.py', 'compress',
    'test_input.txt', 'test_compressed.lzw',
    '--alphabet', 'ab',
    '--max-bits', '3',
    '--log'
], capture_output=True, text=True)

print("=== COMPRESSION OUTPUT ===")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# Decompress with logging
result = subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'test_compressed.lzw', 'test_output.txt',
    '--log'
], capture_output=True, text=True)

print("\n=== DECOMPRESSION OUTPUT ===")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# Verify
with open('test_output.txt', 'r') as f:
    output = f.read()

print(f"\n=== VERIFICATION ===")
print(f"Input length: {len(random_text)}")
print(f"Output length: {len(output)}")
print(f"Match: {output == random_text}")

if output != random_text:
    # Find first mismatch
    for i in range(min(len(random_text), len(output))):
        if i >= len(output) or i >= len(random_text) or random_text[i] != output[i]:
            print(f"\nFirst mismatch at position {i}:")
            print(f"  Expected: ...{random_text[max(0, i-10):i+10]}...")
            print(f"  Got:      ...{output[max(0, i-10):i+10]}...")
            break

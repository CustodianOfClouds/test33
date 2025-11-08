#!/usr/bin/env python3
"""Test the previously failing files"""

import subprocess
import os

files_to_test = ['all.tar', 'large.txt', 'texts.tar']

for filename in files_to_test:
    filepath = os.path.join('TestFiles', filename)

    if not os.path.exists(filepath):
        print(f"✗ {filename}: File not found")
        continue

    print(f"\nTesting {filename}...")
    print("=" * 60)

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        filepath, 'test_compressed.lzw',
        '--alphabet', 'extendedascii'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ Compression failed:")
        print(result.stderr)
        continue

    print(f"✓ Compression succeeded")

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        'test_compressed.lzw', 'test_output.txt'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ Decompression failed:")
        print(result.stderr)
        continue

    print(f"✓ Decompression succeeded")

    # Verify
    with open(filepath, 'rb') as f1:
        original = f1.read()
    with open('test_output.txt', 'rb') as f2:
        decoded = f2.read()

    if original == decoded:
        print(f"✓ {filename}: Perfect match!")
        print(f"  Original size: {len(original):,} bytes")
        print(f"  Decoded size:  {len(decoded):,} bytes")
    else:
        print(f"✗ {filename}: Mismatch")
        print(f"  Original size: {len(original):,} bytes")
        print(f"  Decoded size:  {len(decoded):,} bytes")

        # Find first mismatch
        for i in range(min(len(original), len(decoded))):
            if i >= len(decoded) or i >= len(original) or original[i] != decoded[i]:
                print(f"  First byte mismatch at position {i}:")
                print(f"    Expected: {original[i]} (0x{original[i]:02x})")
                print(f"    Got:      {decoded[i]} (0x{decoded[i]:02x})")
                break

# Cleanup
for f in ['test_compressed.lzw', 'test_output.txt']:
    if os.path.exists(f):
        os.remove(f)

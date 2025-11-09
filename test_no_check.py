#!/usr/bin/env python3
"""
Test what happens when we remove the next_code < EVICT_SIGNAL check from decoder
"""

import subprocess
import os
import hashlib

def md5_file(filepath):
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def test_file(input_file, alphabet, max_bits):
    compressed = "test_no_check.lzw"
    decompressed = "test_no_check_decompressed.txt"

    # Compress
    print(f"  Compressing with max-bits={max_bits}...")
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        input_file, compressed,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  Compression failed: {result.stderr}")
        return False

    comp_size = os.path.getsize(compressed)
    print(f"  Compressed size: {comp_size:,} bytes")

    # Decompress
    print(f"  Decompressing...")
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        compressed, decompressed
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  Decompression FAILED!")
        print(f"  Error: {result.stderr}")
        if os.path.exists(compressed):
            os.remove(compressed)
        return False

    # Compare
    orig_md5 = md5_file(input_file)
    decomp_md5 = md5_file(decompressed)

    # Cleanup
    os.remove(compressed)
    os.remove(decompressed)

    if orig_md5 == decomp_md5:
        print(f"  ✓ MD5 MATCH - Files identical!")
        return True
    else:
        print(f"  ✗ MD5 MISMATCH!")
        print(f"    Original:     {orig_md5}")
        print(f"    Decompressed: {decomp_md5}")
        return False

print("="*80)
print("TEST: Decoder WITHOUT next_code < EVICT_SIGNAL check")
print("="*80)
print()
print("This tests whether the check is actually necessary.")
print("If the encoder handles everything, decoder should still work.")
print()

# Test with a file that will definitely trigger evictions (small max-bits)
print("Test 1: code.txt with max-bits=9 (will trigger evictions)")
print("-" * 80)
test_file('TestFiles/code.txt', 'extendedascii', 9)

print()
print("Test 2: large.txt with max-bits=9 (many evictions)")
print("-" * 80)
test_file('TestFiles/large.txt', 'extendedascii', 9)

print()
print("Test 3: bmps.tar with max-bits=9 (diverse data)")
print("-" * 80)
test_file('TestFiles/bmps.tar', 'extendedascii', 9)

print()
print("="*80)

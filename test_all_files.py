#!/usr/bin/env python3
"""
Comprehensive testing script for lzw_lru_optimized.py
Tests all files in TestFiles/ directory with ASCII alphabet and max-bits=9
"""

import subprocess
import os
import sys

def run_test(input_file, max_bits=9, alphabet='extendedascii'):
    """Test compression and decompression for a single file"""
    base_name = os.path.basename(input_file)
    name_only = os.path.splitext(base_name)[0]

    compressed_opt = f"{name_only}_opt.lzw"
    compressed_full = f"{name_only}_full.lzw"
    decompressed_opt = f"{name_only}_opt_dec.txt"
    decompressed_full = f"{name_only}_full_dec.txt"

    print(f"\n{'='*70}")
    print(f"Testing: {base_name}")
    print(f"{'='*70}")

    # Get original file size
    orig_size = os.path.getsize(input_file)
    print(f"Original size: {orig_size:,} bytes")

    # Test optimized version
    print(f"\n[1/4] Compressing with optimized version...")
    result = subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'compress',
        input_file, compressed_opt,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR in compression: {result.stderr}")
        return False

    opt_size = os.path.getsize(compressed_opt)
    print(f"Optimized compressed: {opt_size:,} bytes ({100*opt_size/orig_size:.2f}%)")

    # Test full version (always send EVICT_SIGNAL)
    print(f"\n[2/4] Compressing with full EVICT_SIGNAL version...")
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        input_file, compressed_full,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR in full compression: {result.stderr}")
        return False

    full_size = os.path.getsize(compressed_full)
    print(f"Full compressed: {full_size:,} bytes ({100*full_size/orig_size:.2f}%)")

    if opt_size < full_size:
        savings = full_size - opt_size
        print(f"✓ Optimization saved: {savings:,} bytes ({100*savings/full_size:.2f}%)")
    else:
        print(f"⚠ No savings (optimized >= full)")

    # Decompress optimized
    print(f"\n[3/4] Decompressing optimized version...")
    result = subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'decompress',
        compressed_opt, decompressed_opt
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR in decompression: {result.stderr}")
        return False

    # Decompress full
    print(f"[4/4] Decompressing full version...")
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        compressed_full, decompressed_full
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR in full decompression: {result.stderr}")
        return False

    # Verify both match original
    print(f"\nVerifying decompressed files...")

    # Compare optimized decompressed with original
    result = subprocess.run(['diff', '-q', input_file, decompressed_opt],
                          capture_output=True)
    if result.returncode == 0:
        print(f"✓ Optimized version: MATCH")
    else:
        print(f"✗ Optimized version: MISMATCH")
        return False

    # Compare full decompressed with original
    result = subprocess.run(['diff', '-q', input_file, decompressed_full],
                          capture_output=True)
    if result.returncode == 0:
        print(f"✓ Full version: MATCH")
    else:
        print(f"✗ Full version: MISMATCH")
        return False

    # Cleanup
    for f in [compressed_opt, compressed_full, decompressed_opt, decompressed_full]:
        if os.path.exists(f):
            os.remove(f)

    return True

def main():
    test_dir = 'TestFiles'

    # Get all files in TestFiles directory
    test_files = [
        os.path.join(test_dir, f)
        for f in os.listdir(test_dir)
        if os.path.isfile(os.path.join(test_dir, f))
    ]

    # Sort by size for organized testing
    test_files.sort(key=lambda f: os.path.getsize(f))

    print(f"Found {len(test_files)} files to test")
    print(f"Using alphabet: extendedascii")
    print(f"Using max-bits: 9")

    passed = 0
    failed = 0

    for test_file in test_files:
        try:
            if run_test(test_file):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"EXCEPTION: {e}")
            failed += 1

    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Passed: {passed}/{len(test_files)}")
    print(f"Failed: {failed}/{len(test_files)}")

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())

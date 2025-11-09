#!/usr/bin/env python3
"""
Test designed to trigger fallback in optimization 2
Creates pattern with 256+ unique outputs between evict-then-use
"""

import subprocess
import os

def test_fallback():
    """
    Create pattern designed to force fallback:
    1. Section A: repetitive pattern (builds dictionary, evicts)
    2. Section B: 300 unique outputs (pushes Section A out of history)
    3. Section C: return to Section A pattern (evict-then-use with stale history)
    """

    print("="*70)
    print("FALLBACK TRIGGER TEST")
    print("="*70)
    print()
    print("Creating file with pattern designed to exceed 255-entry buffer...")
    print()

    # Create test file
    with open('fallback_test.txt', 'w') as f:
        # Section A: Repetitive 'a' pattern (will fill dict and evict)
        print("[Section A] Writing 10k 'a's...")
        f.write('a' * 10000)

        # Section B: Many unique 2-letter patterns to push history
        # Need 300+ unique outputs to guarantee buffer overflow
        print("[Section B] Writing 300 unique patterns...")
        for i in range(300):
            # Use patterns like "b0", "b1", ... "b299"
            # These are unique and will be output
            pattern = f"b{i:03d}"
            f.write(pattern)

        # Section C: Return to 'a' pattern
        print("[Section C] Writing 10k 'a's again...")
        f.write('a' * 10000)

    orig_size = os.path.getsize('fallback_test.txt')
    print(f"\nOriginal size: {orig_size:,} bytes")

    # Compress with debug to see fallback stats
    print("\n" + "-"*70)
    print("Compressing with debug output...")
    print("-"*70)

    result = subprocess.run([
        'python3', 'lzw_lru_optimization2.py', 'compress',
        'fallback_test.txt', 'fallback_test.lzw',
        '--alphabet', 'extendedascii',
        '--max-bits', '9',
        '--debug'
    ], capture_output=True, text=True)

    # Extract fallback stats from debug output
    for line in result.stderr.split('\n'):
        if 'Offset-based signals' in line or 'Fallback' in line or 'Signals sent' in line:
            print(f"  {line}")

    if result.returncode != 0:
        print("\nCompression failed!")
        print(result.stderr[:500])
        return False

    comp_size = os.path.getsize('fallback_test.lzw')
    print(f"\nCompressed size: {comp_size:,} bytes")

    # Decompress to verify correctness
    print("\nDecompressing...")
    result = subprocess.run([
        'python3', 'lzw_lru_optimization2.py', 'decompress',
        'fallback_test.lzw', 'fallback_test.out'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print("Decompression failed!")
        return False

    # Verify
    with open('fallback_test.txt', 'rb') as f1, open('fallback_test.out', 'rb') as f2:
        if f1.read() == f2.read():
            print("✓ Decompression successful - files match!")
        else:
            print("✗ Files don't match!")
            return False

    # Cleanup
    os.remove('fallback_test.txt')
    os.remove('fallback_test.lzw')
    os.remove('fallback_test.out')

    print()
    print("="*70)
    print("If 'Fallback (full entry): 0', then 255 was sufficient.")
    print("If 'Fallback (full entry): N', then N signals used fallback mode.")
    print("="*70)

    return True

if __name__ == '__main__':
    test_fallback()

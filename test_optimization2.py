#!/usr/bin/env python3
"""
Test suite for Optimization 2: Minimal EVICT_SIGNAL
Tests with max-bits=3 for ab, max-bits=9 for extendedascii
"""

import subprocess
import os
import random

def test_compress_decompress(name, input_file, alphabet, max_bits):
    """Test compression and decompression, verify correctness"""
    compressed = f"test_opt2_{max_bits}.lzw"
    decompressed = f"test_opt2_{max_bits}.out"

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru_optimization2.py', 'compress',
        input_file, compressed,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ {name}: Compression failed")
        print(f"    Error: {result.stderr[:200]}")
        return False

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru_optimization2.py', 'decompress',
        compressed, decompressed
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ {name}: Decompression failed")
        print(f"    Error: {result.stderr[:200]}")
        return False

    # Verify
    with open(input_file, 'rb') as f1, open(decompressed, 'rb') as f2:
        original = f1.read()
        decoded = f2.read()

        if original != decoded:
            print(f"  ✗ {name}: Size mismatch ({len(original)} vs {len(decoded)})")
            return False

    # Get compressed size
    comp_size = os.path.getsize(compressed)
    orig_size = os.path.getsize(input_file)
    ratio = comp_size / orig_size * 100 if orig_size > 0 else 0

    print(f"  ✓ {name}: {orig_size:,} → {comp_size:,} ({ratio:.1f}%)")

    # Cleanup
    os.remove(compressed)
    os.remove(decompressed)

    return True

def main():
    print("="*80)
    print("OPTIMIZATION 2 TEST SUITE")
    print("="*80)
    print()

    results = []

    # ========================================================================
    print("[CATEGORY 1: AB ALPHABET - max-bits=3]")
    print("-"*80)

    # Test 1: Repeating 'ab' 250k times
    print("\n[1] Creating 250k repeats of 'ab' (500k bytes)...")
    with open('test_repeat_ab.txt', 'w') as f:
        f.write('ab' * 250000)

    results.append(test_compress_decompress(
        "Repeating 'ab' × 250k",
        'test_repeat_ab.txt',
        'ab',
        3
    ))

    os.remove('test_repeat_ab.txt')

    # Test 2: Random 'ab' 500k times
    print("\n[2] Creating 500k random 'ab' characters...")
    random.seed(42)
    with open('test_random_ab.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))

    results.append(test_compress_decompress(
        "Random 'ab' × 500k",
        'test_random_ab.txt',
        'ab',
        3
    ))

    os.remove('test_random_ab.txt')

    # ========================================================================
    print("\n" + "="*80)
    print("[CATEGORY 2: EXTENDED ASCII - max-bits=9]")
    print("-"*80)
    print()

    test_files = [
        'TestFiles/code.txt',
        'TestFiles/medium.txt',
        'TestFiles/frosty.jpg',
        'TestFiles/assig2.doc',
        'TestFiles/large.txt',
        'TestFiles/texts.tar',
        'TestFiles/all.tar',
    ]

    for filepath in test_files:
        if os.path.exists(filepath):
            filename = os.path.basename(filepath)
            results.append(test_compress_decompress(
                filename,
                filepath,
                'extendedascii',
                9
            ))

    # ========================================================================
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    passed = sum(results)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print("\nOptimization 2 is working correctly!")
        print("EVICT_SIGNAL no longer sends dictionary entry bytes.")
        print("Decoder successfully reconstructs entries using prev + prev[0]")
        return True
    else:
        print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)

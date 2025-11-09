#!/usr/bin/env python3
"""
Comprehensive correctness test for Optimization 2
Verifies original == decompressed for all test cases
"""

import subprocess
import os
import random
import hashlib

def md5_file(filepath):
    """Calculate MD5 hash of file"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def test_compress_decompress(name, input_file, alphabet, max_bits):
    """
    Test compression and decompression, verify byte-for-byte correctness
    """
    compressed = f"test_opt2_{name.replace(' ', '_')}.lzw"
    decompressed = f"test_opt2_{name.replace(' ', '_')}.out"

    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"  Input: {input_file}")
    print(f"  Alphabet: {alphabet}, max-bits: {max_bits}")
    print(f"{'='*70}")

    # Get original size and hash
    orig_size = os.path.getsize(input_file)
    orig_md5 = md5_file(input_file)
    print(f"  Original size: {orig_size:,} bytes")
    print(f"  Original MD5:  {orig_md5}")

    # Compress
    print(f"\n  [1] Compressing...")
    result = subprocess.run([
        'python3', 'lzw_lru_optimization2.py', 'compress',
        input_file, compressed,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ COMPRESSION FAILED!")
        print(f"    Error: {result.stderr[:500]}")
        return False

    comp_size = os.path.getsize(compressed)
    ratio = comp_size / orig_size * 100
    print(f"  Compressed size: {comp_size:,} bytes ({ratio:.1f}%)")

    # Decompress
    print(f"\n  [2] Decompressing...")
    result = subprocess.run([
        'python3', 'lzw_lru_optimization2.py', 'decompress',
        compressed, decompressed
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ DECOMPRESSION FAILED!")
        print(f"    Error: {result.stderr[:500]}")
        os.remove(compressed)
        return False

    # Verify size
    decomp_size = os.path.getsize(decompressed)
    print(f"  Decompressed size: {decomp_size:,} bytes")

    if decomp_size != orig_size:
        print(f"  ✗ SIZE MISMATCH!")
        print(f"    Expected: {orig_size:,}")
        print(f"    Got:      {decomp_size:,}")
        print(f"    Diff:     {decomp_size - orig_size:+,} bytes")
        os.remove(compressed)
        os.remove(decompressed)
        return False

    # Verify hash (byte-for-byte comparison)
    decomp_md5 = md5_file(decompressed)
    print(f"  Decompressed MD5: {decomp_md5}")

    if decomp_md5 != orig_md5:
        print(f"  ✗ HASH MISMATCH!")
        print(f"    Expected: {orig_md5}")
        print(f"    Got:      {decomp_md5}")

        # Show first difference
        with open(input_file, 'rb') as f1, open(decompressed, 'rb') as f2:
            pos = 0
            while True:
                b1 = f1.read(1)
                b2 = f2.read(1)
                if b1 != b2:
                    print(f"    First diff at byte {pos}:")
                    print(f"      Original:     {b1.hex() if b1 else 'EOF'}")
                    print(f"      Decompressed: {b2.hex() if b2 else 'EOF'}")
                    break
                if not b1:
                    break
                pos += 1

        os.remove(compressed)
        os.remove(decompressed)
        return False

    print(f"\n  ✓ PASS - Files match exactly!")

    # Cleanup
    os.remove(compressed)
    os.remove(decompressed)

    return True

def main():
    print("="*70)
    print("COMPREHENSIVE OPTIMIZATION 2 CORRECTNESS TEST")
    print("="*70)
    print("\nThis test verifies byte-for-byte correctness using MD5 hashing.")
    print()

    results = []

    # ========================================================================
    print("\n" + "="*70)
    print("CATEGORY 1: AB ALPHABET - max-bits=3")
    print("="*70)

    # Test 1: Repeating 'ab' 250k times
    print("\n[Creating test file: repeating 'ab' × 250k]")
    with open('test_repeat_ab_250k.txt', 'w') as f:
        f.write('ab' * 250000)

    results.append(test_compress_decompress(
        "Repeating ab 250k",
        'test_repeat_ab_250k.txt',
        'ab',
        3
    ))

    os.remove('test_repeat_ab_250k.txt')

    # Test 2: Random 'ab' 500k times
    print("\n[Creating test file: random 'ab' × 500k]")
    random.seed(42)
    with open('test_random_ab_500k.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))

    results.append(test_compress_decompress(
        "Random ab 500k",
        'test_random_ab_500k.txt',
        'ab',
        3
    ))

    os.remove('test_random_ab_500k.txt')

    # ========================================================================
    print("\n" + "="*70)
    print("CATEGORY 2: EXTENDED ASCII - max-bits=9")
    print("="*70)

    # Get all files in TestFiles/
    test_files = []
    if os.path.exists('TestFiles'):
        for filename in sorted(os.listdir('TestFiles')):
            filepath = os.path.join('TestFiles', filename)
            if os.path.isfile(filepath):
                test_files.append((filepath, filename))

    if not test_files:
        print("\nWarning: No files found in TestFiles/")
    else:
        print(f"\nFound {len(test_files)} files in TestFiles/")

    for filepath, filename in test_files:
        results.append(test_compress_decompress(
            filename,
            filepath,
            'extendedascii',
            9
        ))

    # ========================================================================
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)

    passed = sum(results)
    total = len(results)

    print(f"\nTotal tests: {total}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {total - passed}")
    print()

    if passed == total:
        print("✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print()
        print("Optimization 2 is CORRECT!")
        print("All files decompressed to exactly match the originals.")
        print("Byte-for-byte verification via MD5 hash: ✓")
        return True
    else:
        print("✗✗✗ SOME TESTS FAILED ✗✗✗")
        print()
        print("Optimization 2 has bugs!")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)

#!/usr/bin/env python3
"""
Test lzw_lru.py after removing LRU tracker from decoder
Verifies that decoder still works correctly by following encoder's EVICT_SIGNAL
"""

import subprocess
import os
import hashlib
import random

def md5_file(filepath):
    """Calculate MD5 hash of file"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def test_compress_decompress(input_file, alphabet, max_bits, test_name):
    """Test compression and decompression, verify files match"""
    compressed = f"test_{test_name}.lzw"
    decompressed = f"test_{test_name}_decompressed.txt"

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        input_file, compressed,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ Compression failed: {result.stderr}")
        return False

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        compressed, decompressed
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ Decompression failed: {result.stderr}")
        return False

    # Compare MD5
    orig_md5 = md5_file(input_file)
    decomp_md5 = md5_file(decompressed)

    # Cleanup
    os.remove(compressed)
    os.remove(decompressed)

    if orig_md5 == decomp_md5:
        print(f"  ✓ PASS")
        return True
    else:
        print(f"  ✗ FAIL - MD5 mismatch!")
        return False

def main():
    print("="*80)
    print("TESTING lzw_lru.py WITHOUT DECODER LRU TRACKER")
    print("="*80)
    print()
    print("Verifying decoder works by following encoder's EVICT_SIGNAL instructions")
    print()

    passed = 0
    failed = 0

    # Create test files
    print("Creating test files...")

    # AB repeating
    with open('test_ab_repeat.txt', 'w') as f:
        f.write('ab' * 250000)

    # AB random
    random.seed(42)
    with open('test_ab_random.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))

    print()
    print("="*80)
    print("AB ALPHABET TESTS (max-bits=3)")
    print("="*80)

    # Test AB with max-bits=3
    print("\n1. Repeating ab × 250k")
    if test_compress_decompress('test_ab_repeat.txt', 'ab', 3, 'ab_repeat'):
        passed += 1
    else:
        failed += 1

    print("\n2. Random ab × 500k")
    if test_compress_decompress('test_ab_random.txt', 'ab', 3, 'ab_random'):
        passed += 1
    else:
        failed += 1

    # Cleanup AB test files
    os.remove('test_ab_repeat.txt')
    os.remove('test_ab_random.txt')

    print()
    print("="*80)
    print("EXTENDED ASCII TESTS (max-bits=9)")
    print("="*80)

    # Test all files in TestFiles
    if os.path.exists('TestFiles'):
        test_files = sorted([f for f in os.listdir('TestFiles') if os.path.isfile(os.path.join('TestFiles', f))])

        for i, filename in enumerate(test_files, 3):
            filepath = os.path.join('TestFiles', filename)
            print(f"\n{i}. {filename}")
            if test_compress_decompress(filepath, 'extendedascii', 9, filename.replace('.', '_')):
                passed += 1
            else:
                failed += 1

    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()

    if failed == 0:
        print("✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print()
        print("Decoder works correctly WITHOUT LRU tracker!")
        print("Encoder sends EVICT_SIGNAL with eviction instructions,")
        print("decoder simply follows orders. Clean and simple!")
    else:
        print("✗✗✗ SOME TESTS FAILED ✗✗✗")

    print("="*80)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Test the optimized EVICT_SIGNAL implementation (without redundant second code)"""

import os
import subprocess

def run_test(input_text, max_bits, desc):
    """Test compression and decompression"""
    # Write test input
    with open('test_input.txt', 'w') as f:
        f.write(input_text)

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        'test_input.txt', 'test_compressed.lzw',
        '--alphabet', 'ab',
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ {desc}: Compression failed")
        print(result.stderr)
        return False

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        'test_compressed.lzw', 'test_output.txt'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ {desc}: Decompression failed")
        print(result.stderr)
        return False

    # Verify
    with open('test_output.txt', 'r') as f:
        output = f.read()

    if output == input_text:
        print(f"✓ {desc}")
        return True
    else:
        print(f"✗ {desc}: Output mismatch")
        print(f"  Expected: {input_text[:50]}...")
        print(f"  Got: {output[:50]}...")
        return False

def test_all_files():
    """Test all files in TestFiles directory"""
    passed = 0
    failed = 0

    for filename in sorted(os.listdir('TestFiles')):
        filepath = os.path.join('TestFiles', filename)

        # Compress
        result = subprocess.run([
            'python3', 'lzw_lru.py', 'compress',
            filepath, 'test_compressed.lzw',
            '--alphabet', 'extendedascii'
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ {filename}: Compression failed")
            failed += 1
            continue

        # Decompress
        result = subprocess.run([
            'python3', 'lzw_lru.py', 'decompress',
            'test_compressed.lzw', 'test_output.txt'
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ {filename}: Decompression failed")
            failed += 1
            continue

        # Verify
        with open(filepath, 'rb') as f1:
            original = f1.read()
        with open('test_output.txt', 'rb') as f2:
            decoded = f2.read()

        if original == decoded:
            print(f"✓ {filename}")
            passed += 1
        else:
            print(f"✗ {filename}: Mismatch")
            failed += 1

    return passed, failed

if __name__ == '__main__':
    print("Testing optimized EVICT_SIGNAL (without redundant second code)...\n")

    # Test with small dictionaries to force evictions
    run_test('ab' * 10, 3, "ab*10 (max_bits=3)")
    run_test('ab' * 40, 3, "ab*40 (max_bits=3)")
    run_test('ab' * 500, 3, "ab*500 (max_bits=3)")

    # Test with random patterns
    import random
    random.seed(42)
    random_text = ''.join(random.choice('ab') for _ in range(1000))
    run_test(random_text, 3, "Random a/b sequence (1000 chars, max_bits=3)")

    print("\nTesting all files in TestFiles/...")
    passed, failed = test_all_files()
    print(f"\nTestFiles results: {passed} passed, {failed} failed")

    # Cleanup
    for f in ['test_input.txt', 'test_compressed.lzw', 'test_output.txt']:
        if os.path.exists(f):
            os.remove(f)

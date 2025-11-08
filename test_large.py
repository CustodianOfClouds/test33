#!/usr/bin/env python3
"""Test with large inputs and report compression ratios"""

import os
import subprocess
import random

def test_and_report(input_text, description, max_bits=16):
    """Test compression/decompression and report ratios"""
    # Write test input
    with open('test_input.txt', 'w') as f:
        f.write(input_text)

    input_size = os.path.getsize('test_input.txt')

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        'test_input.txt', 'test_compressed.lzw',
        '--alphabet', 'ab',
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ {description}: Compression failed")
        print(result.stderr)
        return False

    compressed_size = os.path.getsize('test_compressed.lzw')

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        'test_compressed.lzw', 'test_output.txt'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ {description}: Decompression failed")
        print(result.stderr)
        return False

    # Verify
    with open('test_output.txt', 'r') as f:
        output = f.read()

    if output != input_text:
        print(f"✗ {description}: Output mismatch")
        print(f"  Input length: {len(input_text)}, Output length: {len(output)}")
        return False

    # Calculate ratio
    ratio = (input_size / compressed_size) if compressed_size > 0 else 0
    percent = (compressed_size / input_size * 100) if input_size > 0 else 0

    print(f"✓ {description}")
    print(f"  Input: {input_size:,} bytes")
    print(f"  Compressed: {compressed_size:,} bytes")
    print(f"  Compression ratio: {ratio:.2f}:1 ({percent:.1f}% of original)")
    print(f"  Space saved: {input_size - compressed_size:,} bytes ({100 - percent:.1f}%)")
    print()

    return True

if __name__ == '__main__':
    print("=" * 70)
    print("LARGE INPUT TESTS WITH COMPRESSION RATIOS")
    print("=" * 70)
    print()

    # Test 1: 10k random A/B
    random.seed(42)
    random_10k = ''.join(random.choice('ab') for _ in range(10000))
    test_and_report(random_10k, "10k random A/B (max_bits=16)")

    # Test 2: AB*5000
    ab_5000 = 'ab' * 5000
    test_and_report(ab_5000, "AB*5000 (max_bits=16)")

    # Test 3: AB*5000 with small dictionary to trigger more evictions
    test_and_report(ab_5000, "AB*5000 (max_bits=3, frequent evictions)", max_bits=3)

    # Test 4: Highly compressible pattern
    pattern = 'aaaaaaaaaa' * 1000  # 10k of just 'a'
    test_and_report(pattern, "10k of 'aaaaaaaaaa' repeated (max_bits=16)")

    # Test 5: Alternating pattern
    alt = 'ab' * 5000
    test_and_report(alt, "Alternating 'ab'*5000 (max_bits=16)")

    # Cleanup
    for f in ['test_input.txt', 'test_compressed.lzw', 'test_output.txt']:
        if os.path.exists(f):
            os.remove(f)

    print("=" * 70)
    print("All tests completed!")
    print("=" * 70)

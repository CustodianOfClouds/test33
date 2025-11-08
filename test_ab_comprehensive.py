#!/usr/bin/env python3
"""Comprehensive test of a/b patterns"""

import subprocess
import random
import os

def test_pattern(pattern, description, max_bits=16):
    """Test a specific pattern"""
    # Write input
    with open('test_input.txt', 'w') as f:
        f.write(pattern)

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

    if output == pattern:
        print(f"✓ {description}")
        return True
    else:
        print(f"✗ {description}: Mismatch")
        print(f"  Input length:  {len(pattern)}")
        print(f"  Output length: {len(output)}")

        # Find first mismatch
        for i in range(min(len(pattern), len(output))):
            if i >= len(output) or i >= len(pattern) or pattern[i] != output[i]:
                print(f"  First mismatch at position {i}:")
                print(f"    Expected: ...{pattern[max(0, i-10):i+20]}...")
                print(f"    Got:      ...{output[max(0, i-10):i+20]}...")
                break
        return False

print("=" * 70)
print("COMPREHENSIVE A/B PATTERN TESTS")
print("=" * 70)
print()

# Test 1: Random 10k
random.seed(42)
random_10k = ''.join(random.choice('ab') for _ in range(10000))
test_pattern(random_10k, "Random 10k a/b (max_bits=16)")

# Test 2: ab*5000 with max_bits=3 (forces frequent evictions)
ab_5000 = 'ab' * 5000
test_pattern(ab_5000, "ab*5000 (max_bits=3)", max_bits=3)

# Test 3: ab*5000 with max_bits=16 (normal)
test_pattern(ab_5000, "ab*5000 (max_bits=16)", max_bits=16)

# Test 4: Random with max_bits=3
random.seed(123)
random_1k = ''.join(random.choice('ab') for _ in range(1000))
test_pattern(random_1k, "Random 1k a/b (max_bits=3)", max_bits=3)

# Test 5: Highly repetitive
pattern = 'a' * 10000
test_pattern(pattern, "10k of 'a' (max_bits=16)")

# Test 6: Alternating with max_bits=3
pattern = 'ab' * 1000
test_pattern(pattern, "ab*1000 (max_bits=3)", max_bits=3)

print()
print("=" * 70)

# Cleanup
for f in ['test_input.txt', 'test_compressed.lzw', 'test_output.txt']:
    if os.path.exists(f):
        os.remove(f)

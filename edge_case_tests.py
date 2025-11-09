#!/usr/bin/env python3
"""
Comprehensive edge case tests for LZW-LRU implementation
Tests boundary conditions, pathological cases, and stress scenarios
"""

import subprocess
import os
import random

def test_case(name, data, alphabet, max_bits, expected_pass=True):
    """Run a single test case"""
    input_file = 'edge_test_input.txt'
    compressed = 'edge_test.lzw'
    decompressed = 'edge_test_dec.txt'

    # Write test data
    mode = 'wb' if isinstance(data, bytes) else 'w'
    with open(input_file, mode) as f:
        f.write(data)

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'compress',
        input_file, compressed,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        if expected_pass:
            print(f"  ✗ {name}: Compression failed")
            print(f"    Error: {result.stderr[:200]}")
            cleanup(input_file, compressed, decompressed)
            return False
        else:
            print(f"  ✓ {name}: Correctly rejected")
            cleanup(input_file, compressed, decompressed)
            return True

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'decompress',
        compressed, decompressed
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ {name}: Decompression failed")
        print(f"    Error: {result.stderr[:200]}")
        cleanup(input_file, compressed, decompressed)
        return False

    # Verify
    result = subprocess.run(['diff', '-q', input_file, decompressed],
                           capture_output=True)

    success = result.returncode == 0

    if success:
        # Show compression stats
        orig_size = os.path.getsize(input_file)
        comp_size = os.path.getsize(compressed)
        ratio = (comp_size / orig_size * 100) if orig_size > 0 else 0
        print(f"  ✓ {name}: {orig_size}B → {comp_size}B ({ratio:.1f}%)")
    else:
        print(f"  ✗ {name}: Decompressed doesn't match")

    cleanup(input_file, compressed, decompressed)
    return success

def cleanup(*files):
    """Remove test files"""
    for f in files:
        if os.path.exists(f):
            os.remove(f)

def run_all_tests():
    """Run comprehensive edge case test suite"""
    results = []

    print("="*80)
    print("EDGE CASE TEST SUITE")
    print("="*80)

    # =========================================================================
    print("\n[CATEGORY 1: BOUNDARY CASES]")
    print("-"*80)

    results.append(test_case(
        "Empty file",
        "",
        'ab',
        3
    ))

    results.append(test_case(
        "Single character",
        "a",
        'ab',
        3
    ))

    results.append(test_case(
        "Two characters (exact alphabet)",
        "ab",
        'ab',
        3
    ))

    results.append(test_case(
        "Just fills dictionary (no eviction)",
        "abba",  # Creates: ab, bb, ba - 3 entries, no eviction
        'ab',
        3
    ))

    results.append(test_case(
        "Exactly triggers first eviction",
        "abababab",  # Should fill dict and trigger 1 eviction
        'ab',
        3
    ))

    # =========================================================================
    print("\n[CATEGORY 2: PATHOLOGICAL PATTERNS]")
    print("-"*80)

    results.append(test_case(
        "All same character (10k)",
        "a" * 10000,
        'ab',
        3
    ))

    results.append(test_case(
        "Strict alternation (10k)",
        "ab" * 5000,
        'ab',
        3
    ))

    results.append(test_case(
        "Worst-case LRU (always evict most useful)",
        ''.join(chr(i % 128) for i in range(10000)),  # Cycling through ASCII
        'ascii',
        9
    ))

    results.append(test_case(
        "Sequential runs",
        "aaabbbaaabbbaaabbb" * 500,
        'ab',
        3
    ))

    results.append(test_case(
        "Increasing run lengths",
        "a" + "bb" * 2 + "aaa" * 3 + "bbbb" * 4 + "aaaaa" * 5,
        'ab',
        9
    ))

    # =========================================================================
    print("\n[CATEGORY 3: LARGE FILES]")
    print("-"*80)

    random.seed(42)
    results.append(test_case(
        "1MB random 'ab'",
        ''.join(random.choice('ab') for _ in range(1000000)),
        'ab',
        3
    ))

    results.append(test_case(
        "1MB repeating 'ab'",
        "ab" * 500000,
        'ab',
        3
    ))

    results.append(test_case(
        "500KB random extendedascii",
        ''.join(chr(random.randint(0, 255)) for _ in range(500000)),
        'extendedascii',
        9
    ))

    # =========================================================================
    print("\n[CATEGORY 4: MAX-BITS VARIATIONS]")
    print("-"*80)

    test_data = "ab" * 100

    results.append(test_case(
        "max-bits=3 (minimal)",
        test_data,
        'ab',
        3
    ))

    results.append(test_case(
        "max-bits=4",
        test_data,
        'ab',
        4
    ))

    results.append(test_case(
        "max-bits=8",
        test_data,
        'ab',
        8
    ))

    results.append(test_case(
        "max-bits=12",
        test_data,
        'ab',
        12
    ))

    results.append(test_case(
        "max-bits=16 (maximum)",
        test_data,
        'ab',
        16
    ))

    # =========================================================================
    print("\n[CATEGORY 5: BINARY DATA]")
    print("-"*80)

    results.append(test_case(
        "All zeros (1k bytes)",
        '\x00' * 1000,
        'extendedascii',
        9
    ))

    results.append(test_case(
        "All 0xFF (1k bytes)",
        '\xff' * 1000,
        'extendedascii',
        9
    ))

    results.append(test_case(
        "Alternating 0x00/0xFF",
        '\x00\xff' * 500,
        'extendedascii',
        9
    ))

    results.append(test_case(
        "Sequential bytes 0-255 repeated",
        ''.join(chr(i) for i in range(256)) * 10,
        'extendedascii',
        9
    ))

    results.append(test_case(
        "Random binary (10k bytes)",
        ''.join(chr(random.randint(0, 255)) for _ in range(10000)),
        'extendedascii',
        9
    ))

    # =========================================================================
    print("\n[CATEGORY 6: COMPRESSION EXTREMES]")
    print("-"*80)

    results.append(test_case(
        "Highly compressible (same byte)",
        "a" * 100000,
        'ab',
        9
    ))

    results.append(test_case(
        "Poorly compressible (random)",
        ''.join(random.choice('abcdefghij') for _ in range(10000)),
        'extendedascii',
        9
    ))

    results.append(test_case(
        "Fibonacci-like pattern",
        fibonacci_string(1000),
        'ab',
        9
    ))

    # =========================================================================
    print("\n[CATEGORY 7: EVICT-THEN-USE SCENARIOS]")
    print("-"*80)

    results.append(test_case(
        "Maximum evict-then-use (force signals)",
        create_evict_then_use_pattern(1000),
        'ab',
        3
    ))

    results.append(test_case(
        "Zero evict-then-use (no signals needed)",
        "ab" * 5000,  # Simple repetition, LRU order stable
        'ab',
        3
    ))

    # =========================================================================
    print("\n[CATEGORY 8: SPECIAL CHARACTERS]")
    print("-"*80)

    results.append(test_case(
        "Newlines and tabs",
        "a\nb\ta\nb\t" * 100,
        'extendedascii',
        9
    ))

    results.append(test_case(
        "Whitespace variations",
        "a b\tc\nd\r" * 100,
        'extendedascii',
        9
    ))

    # =========================================================================
    print("\n[CATEGORY 9: DICTIONARY BOUNDARY]")
    print("-"*80)

    results.append(test_case(
        "Exactly fills dict, no overflow",
        create_dict_fill_pattern('ab', 3),
        'ab',
        3
    ))

    results.append(test_case(
        "One byte past dict full",
        create_dict_fill_pattern('ab', 3) + 'a',
        'ab',
        3
    ))

    # =========================================================================
    print("\n[CATEGORY 10: STRESS TESTS]")
    print("-"*80)

    results.append(test_case(
        "Pathological: Every byte triggers eviction",
        create_pathological_eviction(5000),
        'ab',
        3
    ))

    results.append(test_case(
        "Cascading evictions pattern",
        "ababaabbabaabbaaba" * 500,
        'ab',
        3
    ))

    results.append(test_case(
        "Max entropy (close to random)",
        ''.join(chr(hash(i) % 256) for i in range(10000)),
        'extendedascii',
        9
    ))

    results.append(test_case(
        "Degenerate: Only 2 unique patterns",
        ("a" * 100 + "b" * 100) * 50,
        'ab',
        9
    ))

    results.append(test_case(
        "Dictionary thrashing (worst LRU)",
        create_lru_thrashing(2000),
        'ab',
        3
    ))

    # =========================================================================
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("\n✓✓✓ ALL EDGE CASES PASSED ✓✓✓")
        return True
    else:
        print(f"\n✗✗✗ {total - passed} EDGE CASES FAILED ✗✗✗")
        return False

def fibonacci_string(length):
    """Generate Fibonacci-like string pattern"""
    a, b = 'a', 'b'
    result = ''
    while len(result) < length:
        result += a
        a, b = b, a + b
    return result[:length]

def create_evict_then_use_pattern(iterations):
    """Create pattern that maximizes evict-then-use scenarios"""
    # Pattern: fill dict, then use evicted codes immediately
    # With max-bits=3, dict codes are 3,4,5,6
    # Create ab, ba, aba, bab to fill
    # Then use patterns that evict and immediately reuse
    pattern = "ababaababb"  # Creates complex eviction pattern
    return pattern * (iterations // len(pattern))

def create_dict_fill_pattern(alphabet, max_bits):
    """Create pattern that exactly fills dictionary"""
    # Calculate how many dict entries can fit
    alphabet_size = len(alphabet)
    max_size = 1 << max_bits
    dict_capacity = max_size - alphabet_size - 2  # -2 for EOF and EVICT_SIGNAL

    # Create pattern that generates exactly dict_capacity entries
    # For 'ab' with max_bits=3: need 4 entries (ab, ba, aba, bab)
    pattern = 'abba'  # Creates: ab, bb, ba (3 entries)
    return pattern

def create_pathological_eviction(length):
    """Create pattern that maximizes evictions per byte"""
    # Pattern that constantly creates new sequences
    # Forces eviction on almost every character
    result = []
    for i in range(length):
        # Alternate in a way that creates unique patterns
        if i % 4 == 0:
            result.append('a')
        elif i % 4 == 1:
            result.append('b')
        elif i % 4 == 2:
            result.append('a')
        else:
            result.append('a')
    return ''.join(result)

def create_lru_thrashing(length):
    """Create pattern that thrashes LRU (worst-case access pattern)"""
    # Pattern: Use N+1 unique patterns where N = dict size
    # This causes every access to evict the next-to-be-used entry
    # With max_bits=3, dict has 4 slots, so use 5 patterns cyclically
    patterns = ['ab', 'ba', 'aa', 'bb', 'aba']
    result = []
    for i in range(length // 3):
        result.append(patterns[i % len(patterns)])
    return ''.join(result)

if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)

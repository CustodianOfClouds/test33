#!/usr/bin/env python3
"""
Benchmark comparison: O(L) vs O(1) versions of Optimization 2
Compares compression ratios (should be identical) and time performance
"""

import subprocess
import os
import random
import time

def benchmark_compress(script, input_file, alphabet, max_bits, name):
    """Compress file and return size and time"""
    output_file = f"bench_{name}_{os.path.basename(script)}.lzw"

    start_time = time.time()
    result = subprocess.run([
        'python3', script, 'compress',
        input_file, output_file,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)
    elapsed = time.time() - start_time

    if result.returncode != 0:
        return None, None

    size = os.path.getsize(output_file)
    os.remove(output_file)
    return size, elapsed

def main():
    print("="*90)
    print("BENCHMARK: O(255 × L) LINEAR SEARCH vs O(1) HASHMAP")
    print("="*90)
    print()
    print("Comparing lzw_lru_optimization2_old.py (linear search)")
    print("     vs  lzw_lru_optimization2.py     (HashMap O(1))")
    print()

    # Create test files
    print("Creating test files...")

    # AB repeating
    with open('bench_ab_repeat.txt', 'w') as f:
        f.write('ab' * 250000)

    # AB random
    random.seed(42)
    with open('bench_ab_random.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))

    # Test configurations
    tests = [
        ('bench_ab_repeat.txt', 'ab', 3, 'Repeating ab × 250k'),
        ('bench_ab_random.txt', 'ab', 3, 'Random ab × 500k'),
    ]

    # Add TestFiles if available
    if os.path.exists('TestFiles'):
        # Select a few representative files
        for filename in ['code.txt', 'large.txt', 'bmps.tar', 'all.tar', 'wacky.bmp']:
            filepath = os.path.join('TestFiles', filename)
            if os.path.isfile(filepath):
                tests.append((filepath, 'extendedascii', 9, filename))

    print()
    print("="*90)
    print(f"{'Test':<25} {'Original':>12} {'Old Size':>12} {'New Size':>12} {'Old Time':>10} {'New Time':>10} {'Speedup':>10}")
    print("-"*90)

    total_speedup = 0
    test_count = 0

    for filepath, alphabet, max_bits, name in tests:
        orig_size = os.path.getsize(filepath)

        # Benchmark old version (linear search)
        old_size, old_time = benchmark_compress(
            'lzw_lru_optimization2_old.py', filepath, alphabet, max_bits, name
        )

        # Benchmark new version (HashMap)
        new_size, new_time = benchmark_compress(
            'lzw_lru_optimization2.py', filepath, alphabet, max_bits, name
        )

        if old_size and new_size:
            speedup = old_time / new_time if new_time > 0 else 0
            total_speedup += speedup
            test_count += 1

            # Check if sizes match (they should!)
            size_match = "✓" if old_size == new_size else "✗ MISMATCH"

            display_name = name if len(name) <= 25 else name[:22] + "..."

            print(f"{display_name:<25} {orig_size:>12,} {old_size:>12,} {new_size:>12,} "
                  f"{old_time:>9.2f}s {new_time:>9.2f}s {speedup:>9.2f}x {size_match}")

    # Cleanup
    os.remove('bench_ab_repeat.txt')
    os.remove('bench_ab_random.txt')

    print("="*90)
    print()
    print(f"Average speedup: {total_speedup / test_count:.2f}x")
    print()
    print("OBSERVATIONS:")
    print("  1. Compression sizes should be IDENTICAL (same algorithm)")
    print("  2. O(1) HashMap version should be faster, especially on large files")
    print("  3. Speedup increases with:")
    print("     - More EVICT_SIGNALs (more evictions = more lookups)")
    print("     - Longer string lengths (linear search does O(L) comparisons)")
    print("     - Larger dictionary (max-bits) means fewer early evictions")
    print()
    print("MEMORY TRADEOFF:")
    print("  - Linear search: Minimal overhead (just 255-entry buffer)")
    print("  - HashMap: +4KB overhead (~8.7% of program memory)")
    print("  - Verdict: 4KB is trivial, O(1) guarantee valuable for large files")
    print("="*90)

if __name__ == '__main__':
    main()

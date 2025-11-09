#!/usr/bin/env python3
"""
Time benchmark: O(L) vs O(1) across different max-bits
Shows how speedup varies with dictionary size (max-bits 9, 10, 11, 12)
"""

import subprocess
import os
import random
import time

def benchmark_compress_time(script, input_file, alphabet, max_bits, name):
    """Compress file and return time only"""
    output_file = f"bench_time_{name}_{max_bits}_{os.path.basename(script)}.lzw"

    start_time = time.time()
    result = subprocess.run([
        'python3', script, 'compress',
        input_file, output_file,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)
    elapsed = time.time() - start_time

    if result.returncode != 0:
        return None

    os.remove(output_file)
    return elapsed

def main():
    print("="*100)
    print("TIME BENCHMARK: O(255 × L) LINEAR vs O(1) HASHMAP across MAX-BITS")
    print("="*100)
    print()
    print("Shows how performance difference varies with dictionary size")
    print("Larger dictionary (higher max-bits) = fewer evictions = less benefit from O(1)")
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
        ('bench_ab_repeat.txt', 'ab', 'Repeating ab × 250k'),
        ('bench_ab_random.txt', 'ab', 'Random ab × 500k'),
    ]

    # Add TestFiles
    if os.path.exists('TestFiles'):
        for filename in ['code.txt', 'large.txt', 'bmps.tar', 'all.tar', 'wacky.bmp', 'assig2.doc']:
            filepath = os.path.join('TestFiles', filename)
            if os.path.isfile(filepath):
                tests.append((filepath, 'extendedascii', filename))

    max_bits_values = [9, 10, 11, 12]

    for filepath, alphabet, name in tests:
        orig_size = os.path.getsize(filepath)

        print()
        print("="*100)
        print(f"FILE: {name} ({orig_size:,} bytes)")
        print("="*100)
        print(f"{'Max-Bits':<10} {'O(L) Time':>12} {'O(1) Time':>12} {'Speedup':>10} {'Verdict':>15}")
        print("-"*100)

        for max_bits in max_bits_values:
            # Benchmark O(L) version
            ol_time = benchmark_compress_time(
                'lzw_lru_optimization2_old.py', filepath, alphabet, max_bits, name
            )

            # Benchmark O(1) version
            o1_time = benchmark_compress_time(
                'lzw_lru_optimization2.py', filepath, alphabet, max_bits, name
            )

            if ol_time and o1_time:
                speedup = ol_time / o1_time if o1_time > 0 else 0

                # Determine verdict
                if speedup >= 1.1:
                    verdict = "O(1) faster"
                elif speedup >= 1.02:
                    verdict = "O(1) slightly faster"
                elif speedup >= 0.98:
                    verdict = "Similar"
                else:
                    verdict = "O(L) faster"

                print(f"{max_bits:<10} {ol_time:>11.2f}s {o1_time:>11.2f}s {speedup:>9.2f}x  {verdict:>15}")

    # Cleanup
    os.remove('bench_ab_repeat.txt')
    os.remove('bench_ab_random.txt')

    print()
    print("="*100)
    print("OBSERVATIONS:")
    print("  - Higher max-bits = larger dictionary = fewer evictions")
    print("  - Fewer evictions = fewer EVICT_SIGNALs = less opportunity for O(1) to shine")
    print("  - O(1) speedup should be most visible at low max-bits (many evictions)")
    print("  - At very high max-bits, both converge (minimal evictions)")
    print()
    print("CONCLUSION:")
    print("  O(1) HashMap provides consistent performance regardless of max-bits")
    print("  O(L) linear search gets slower with frequent evictions (low max-bits)")
    print("="*100)

if __name__ == '__main__':
    main()

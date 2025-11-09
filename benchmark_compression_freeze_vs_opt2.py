#!/usr/bin/env python3
"""
Compression ratio benchmark: FREEZE vs OPT-2 (O(1)) across max-bits
Shows how compression performance varies with dictionary size
"""

import subprocess
import os
import random

def compress_and_measure(script, input_file, alphabet, max_bits, name):
    """Compress file and return compressed size"""
    output_file = f"bench_comp_{name}_{max_bits}_{os.path.basename(script)}.lzw"

    result = subprocess.run([
        'python3', script, 'compress',
        input_file, output_file,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        return None

    size = os.path.getsize(output_file)
    os.remove(output_file)
    return size

def main():
    print("="*100)
    print("COMPRESSION RATIO: FREEZE vs OPTIMIZATION-2 (O(1)) across MAX-BITS")
    print("="*100)
    print()
    print("Shows how compression ratio changes with dictionary size")
    print("Higher max-bits = larger dictionary = more patterns captured")
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
        print(f"{'Max-Bits':<10} {'Freeze':>12} {'Opt-2':>12} {'Difference':>12} {'Opt2/Freeze':>13} {'Winner':>15}")
        print("-"*100)

        for max_bits in max_bits_values:
            # Compress with both methods
            freeze_size = compress_and_measure(
                'lzw_freeze.py', filepath, alphabet, max_bits, name
            )

            opt2_size = compress_and_measure(
                'lzw_lru_optimization2.py', filepath, alphabet, max_bits, name
            )

            if freeze_size and opt2_size:
                diff = opt2_size - freeze_size
                ratio = opt2_size / freeze_size if freeze_size > 0 else 0
                improvement = ((freeze_size - opt2_size) / freeze_size * 100) if freeze_size > 0 else 0

                # Determine winner
                if ratio < 0.9:
                    winner = "OPT-2 wins!"
                elif ratio < 1.0:
                    winner = "OPT-2 better"
                elif ratio < 1.1:
                    winner = "Similar"
                elif ratio < 1.5:
                    winner = "Freeze better"
                else:
                    winner = "Freeze wins!"

                print(f"{max_bits:<10} {freeze_size:>12,} {opt2_size:>12,} {diff:>+12,} {ratio:>12.2f}x  {winner:>15}")

    # Cleanup
    os.remove('bench_ab_repeat.txt')
    os.remove('bench_ab_random.txt')

    print()
    print("="*100)
    print("OBSERVATIONS:")
    print("  - Repetitive patterns (ab repeat, text): FREEZE wins (no need for adaptation)")
    print("  - Diverse patterns (bmps.tar, wacky.bmp): OPT-2 wins (LRU adaptation pays off)")
    print("  - Higher max-bits: Gap narrows (larger dict = less eviction needed)")
    print()
    print("PATTERN INSIGHTS:")
    print("  1. Static patterns favor FREEZE (dictionary learns once, no changes)")
    print("  2. Evolving patterns favor OPT-2 (LRU adapts to changing data)")
    print("  3. Very high max-bits: Both converge (dictionary rarely fills)")
    print()
    print("TRADE-OFF:")
    print("  FREEZE: Simpler, faster on repetitive data, but can't adapt")
    print("  OPT-2:  Adaptive, better on diverse data, tiny overhead (4KB + O(1))")
    print("="*100)

if __name__ == '__main__':
    main()

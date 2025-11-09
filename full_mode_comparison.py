#!/usr/bin/env python3
"""
Comprehensive comparison: FREEZE vs OPTIMIZED-1 vs OPTIMIZED-2
Tests with max-bits 9, 10, 11, 12 on AB and ExtendedASCII tests
"""

import subprocess
import os
import random

def compress_and_measure(script, input_file, alphabet, max_bits):
    """Compress file and return compressed size"""
    output_file = f"test_comp_{os.path.basename(script)}_{max_bits}.lzw"

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

def format_comparison(freeze_size, opt1_size, opt2_size):
    """Format comparison showing savings"""
    if not all([freeze_size, opt1_size, opt2_size]):
        return "ERROR", "ERROR"

    # Opt1 vs Freeze
    opt1_vs_freeze = ((freeze_size - opt1_size) / freeze_size * 100) if freeze_size > 0 else 0

    # Opt2 vs Opt1
    opt2_vs_opt1 = ((opt1_size - opt2_size) / opt1_size * 100) if opt1_size > 0 else 0

    # Opt2 vs Freeze (total)
    opt2_vs_freeze = ((freeze_size - opt2_size) / freeze_size * 100) if freeze_size > 0 else 0

    return opt1_vs_freeze, opt2_vs_opt1, opt2_vs_freeze

def main():
    print("="*90)
    print("COMPREHENSIVE MODE COMPARISON: FREEZE vs OPTIMIZED-1 vs OPTIMIZED-2")
    print("="*90)
    print()

    # Create test files
    print("Creating test files...")

    # AB repeating
    with open('test_ab_repeat.txt', 'w') as f:
        f.write('ab' * 250000)

    # AB random
    random.seed(42)
    with open('test_ab_random.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))

    # Test configurations
    ab_tests = [
        ('test_ab_repeat.txt', 'ab', 'Repeating ab × 250k'),
        ('test_ab_random.txt', 'ab', 'Random ab × 500k'),
    ]

    # Extended ASCII tests
    ea_tests = []
    if os.path.exists('TestFiles'):
        for filename in sorted(os.listdir('TestFiles')):
            filepath = os.path.join('TestFiles', filename)
            if os.path.isfile(filepath):
                ea_tests.append((filepath, 'extendedascii', filename))

    max_bits_values = [9, 10, 11, 12]

    # Run tests
    for max_bits in max_bits_values:
        print("\n" + "="*90)
        print(f"MAX-BITS = {max_bits}")
        print("="*90)

        # AB Alphabet tests
        if ab_tests:
            print(f"\n{'='*90}")
            print(f"AB ALPHABET (max-bits={max_bits})")
            print(f"{'='*90}")
            print(f"{'Test':<25} {'Original':>12} {'Freeze':>12} {'Opt-1':>12} {'Opt-2':>12} {'Opt1 vs F':>11} {'Opt2 vs 1':>11} {'Opt2 vs F':>11}")
            print("-"*90)

            for filepath, alphabet, name in ab_tests:
                orig_size = os.path.getsize(filepath)

                freeze_size = compress_and_measure('lzw_freeze.py', filepath, alphabet, max_bits)
                opt1_size = compress_and_measure('lzw_lru_optimized.py', filepath, alphabet, max_bits)
                opt2_size = compress_and_measure('lzw_lru_optimization2.py', filepath, alphabet, max_bits)

                if freeze_size and opt1_size and opt2_size:
                    opt1_vs_freeze, opt2_vs_opt1, opt2_vs_freeze = format_comparison(freeze_size, opt1_size, opt2_size)

                    print(f"{name:<25} {orig_size:>12,} {freeze_size:>12,} {opt1_size:>12,} {opt2_size:>12,} "
                          f"{opt1_vs_freeze:>10.1f}% {opt2_vs_opt1:>10.1f}% {opt2_vs_freeze:>10.1f}%")

        # Extended ASCII tests
        if ea_tests:
            print(f"\n{'='*90}")
            print(f"EXTENDED ASCII (max-bits={max_bits})")
            print(f"{'='*90}")
            print(f"{'Test':<25} {'Original':>12} {'Freeze':>12} {'Opt-1':>12} {'Opt-2':>12} {'Opt1 vs F':>11} {'Opt2 vs 1':>11} {'Opt2 vs F':>11}")
            print("-"*90)

            for filepath, alphabet, name in ea_tests:
                orig_size = os.path.getsize(filepath)

                freeze_size = compress_and_measure('lzw_freeze.py', filepath, alphabet, max_bits)
                opt1_size = compress_and_measure('lzw_lru_optimized.py', filepath, alphabet, max_bits)
                opt2_size = compress_and_measure('lzw_lru_optimization2.py', filepath, alphabet, max_bits)

                if freeze_size and opt1_size and opt2_size:
                    opt1_vs_freeze, opt2_vs_opt1, opt2_vs_freeze = format_comparison(freeze_size, opt1_size, opt2_size)

                    # Truncate name if too long
                    display_name = name if len(name) <= 25 else name[:22] + "..."

                    print(f"{display_name:<25} {orig_size:>12,} {freeze_size:>12,} {opt1_size:>12,} {opt2_size:>12,} "
                          f"{opt1_vs_freeze:>10.1f}% {opt2_vs_opt1:>10.1f}% {opt2_vs_freeze:>10.1f}%")

    # Cleanup
    os.remove('test_ab_repeat.txt')
    os.remove('test_ab_random.txt')

    print("\n" + "="*90)
    print("LEGEND:")
    print("  Opt1 vs F:  % savings of Optimized-1 compared to Freeze")
    print("  Opt2 vs 1:  % savings of Optimized-2 compared to Optimized-1")
    print("  Opt2 vs F:  % total savings of Optimized-2 compared to Freeze")
    print("="*90)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Compare compression ratios: lzw_lru_optimized.py vs lzw_lru_optimization2.py
"""

import subprocess
import os
import random

def compress_and_get_size(script, input_file, alphabet, max_bits):
    """Compress and return compressed size"""
    output_file = f"test_compare_{os.path.basename(script)}.lzw"

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
    print("="*80)
    print("OPTIMIZATION COMPARISON: Output History vs Full Entry")
    print("="*80)
    print()

    tests = []

    # Create test files
    print("[1] Creating repeating 'ab' × 250k...")
    with open('test_repeat_ab.txt', 'w') as f:
        f.write('ab' * 250000)
    tests.append(('test_repeat_ab.txt', 'ab', 3, "Repeating 'ab' × 250k"))

    print("[2] Creating random 'ab' × 500k...")
    random.seed(42)
    with open('test_random_ab.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))
    tests.append(('test_random_ab.txt', 'ab', 3, "Random 'ab' × 500k"))

    # Add TestFiles
    test_files = [
        ('TestFiles/code.txt', 'extendedascii', 9, 'code.txt'),
        ('TestFiles/large.txt', 'extendedascii', 9, 'large.txt'),
        ('TestFiles/texts.tar', 'extendedascii', 9, 'texts.tar'),
        ('TestFiles/all.tar', 'extendedascii', 9, 'all.tar'),
    ]

    for filepath, alphabet, max_bits, name in test_files:
        if os.path.exists(filepath):
            tests.append((filepath, alphabet, max_bits, name))

    print()
    print("-"*80)
    print(f"{'Test':<25} {'Original':>12} {'Optimized':>12} {'Savings':>10}")
    print("-"*80)

    total_original = 0
    total_optimized = 0

    for filepath, alphabet, max_bits, name in tests:
        orig_size = compress_and_get_size('lzw_lru_optimized.py', filepath, alphabet, max_bits)
        opt_size = compress_and_get_size('lzw_lru_optimization2.py', filepath, alphabet, max_bits)

        if orig_size and opt_size:
            savings = (orig_size - opt_size) / orig_size * 100
            total_original += orig_size
            total_optimized += opt_size

            print(f"{name:<25} {orig_size:>12,} {opt_size:>12,} {savings:>9.1f}%")

    print("-"*80)
    overall_savings = (total_original - total_optimized) / total_original * 100
    print(f"{'TOTAL':<25} {total_original:>12,} {total_optimized:>12,} {overall_savings:>9.1f}%")
    print("="*80)
    print()
    print(f"Optimization 2 reduces compressed size by {overall_savings:.1f}% on average!")
    print()

    # Cleanup
    os.remove('test_repeat_ab.txt')
    os.remove('test_random_ab.txt')

if __name__ == '__main__':
    main()

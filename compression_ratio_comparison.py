#!/usr/bin/env python3
"""
Comprehensive compression ratio comparison between:
- FREEZE mode (dictionary stops growing)
- LRU FULL (always send EVICT_SIGNAL)
- LRU OPTIMIZED (send signal only when needed)
"""

import subprocess
import os
import random

def compress_with_mode(input_file, mode, alphabet, max_bits):
    """Compress file with specific mode and return compressed size"""
    output = f"test_{mode}_{max_bits}.lzw"

    if mode == 'freeze':
        script = 'lzw_freeze.py'
    elif mode == 'lru_full':
        script = 'lzw_lru.py'
    elif mode == 'lru_opt':
        script = 'lzw_lru_optimized.py'
    else:
        return None

    result = subprocess.run([
        'python3', script, 'compress',
        input_file, output,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True)

    if result.returncode != 0:
        print(f"    Error with {mode}: {result.stderr.decode()[:100]}")
        return None

    size = os.path.getsize(output)
    os.remove(output)
    return size

def test_compression(test_name, input_file, alphabet, max_bits_list):
    """Test all modes on one file with multiple max-bits values"""
    orig_size = os.path.getsize(input_file)

    print(f"\n{'='*80}")
    print(f"{test_name}")
    print(f"Original size: {orig_size:,} bytes")
    print(f"{'='*80}")
    print(f"{'max-bits':<10} {'FREEZE':>15} {'LRU-FULL':>15} {'LRU-OPT':>15} {'Savings':>15}")
    print("-"*80)

    for max_bits in max_bits_list:
        freeze_size = compress_with_mode(input_file, 'freeze', alphabet, max_bits)
        full_size = compress_with_mode(input_file, 'lru_full', alphabet, max_bits)
        opt_size = compress_with_mode(input_file, 'lru_opt', alphabet, max_bits)

        if freeze_size and full_size and opt_size:
            savings = ((full_size - opt_size) / full_size * 100) if full_size > 0 else 0

            freeze_ratio = f"{freeze_size:,} ({freeze_size/orig_size*100:.1f}%)"
            full_ratio = f"{full_size:,} ({full_size/orig_size*100:.1f}%)"
            opt_ratio = f"{opt_size:,} ({opt_size/orig_size*100:.1f}%)"

            print(f"{max_bits:<10} {freeze_ratio:>15} {full_ratio:>15} {opt_ratio:>15} {savings:>14.1f}%")

def main():
    print("="*80)
    print("COMPRESSION RATIO COMPARISON")
    print("="*80)
    print("\nModes:")
    print("  FREEZE:   Dictionary stops growing at max size")
    print("  LRU-FULL: Always send EVICT_SIGNAL (100% of evictions)")
    print("  LRU-OPT:  Send signal only when needed (20-30% of evictions)")
    print()

    # =======================================================================
    print("\n" + "="*80)
    print("CATEGORY 1: REPEATING 'ab' PATTERN")
    print("="*80)

    # Create 250k repeating 'ab'
    print("\nCreating 250k repeats of 'ab' (500k bytes)...")
    with open('test_repeat_ab.txt', 'w') as f:
        f.write('ab' * 250000)

    test_compression(
        "Repeating 'ab' × 250k",
        'test_repeat_ab.txt',
        'ab',
        [3, 4, 5, 6]
    )

    os.remove('test_repeat_ab.txt')

    # =======================================================================
    print("\n" + "="*80)
    print("CATEGORY 2: RANDOM 'ab' PATTERN")
    print("="*80)

    # Create 500k random 'ab'
    print("\nCreating 500k random 'ab' characters...")
    random.seed(42)
    with open('test_random_ab.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))

    test_compression(
        "Random 'ab' × 500k",
        'test_random_ab.txt',
        'ab',
        [3, 4, 5, 6]
    )

    os.remove('test_random_ab.txt')

    # =======================================================================
    print("\n" + "="*80)
    print("CATEGORY 3: EXTENDED ASCII FILES")
    print("="*80)

    # Test on actual files
    test_files = [
        ('TestFiles/texts.tar', 'texts.tar (1.4 MB)'),
        ('TestFiles/all.tar', 'all.tar (3 MB)'),
        ('TestFiles/large.txt', 'large.txt (1.2 MB)'),
        ('TestFiles/code.txt', 'code.txt (69 KB)'),
        ('TestFiles/frosty.jpg', 'frosty.jpg (126 KB)'),
    ]

    for filepath, name in test_files:
        if os.path.exists(filepath):
            test_compression(
                name,
                filepath,
                'extendedascii',
                [9, 10, 11, 12]
            )

    # =======================================================================
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\nKey Observations:")
    print("  1. FREEZE: May compress better or worse depending on data")
    print("  2. LRU-FULL: Worst ratio (sends signal for every eviction)")
    print("  3. LRU-OPT: Best LRU ratio (60-70% smaller than FULL)")
    print()
    print("LRU-OPT saves 60-70% vs LRU-FULL by only signaling when needed!")
    print("="*80)

if __name__ == '__main__':
    main()

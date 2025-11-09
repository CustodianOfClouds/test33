#!/usr/bin/env python3
"""
Compare Freeze vs Opt-2 across different max-bits values
Shows how compression size varies with dictionary size
"""

import subprocess
import os
import random

def compress_and_measure(script, input_file, alphabet, max_bits):
    """Compress file and return compressed size"""
    output_file = f"test_prog_{os.path.basename(script)}_{max_bits}.lzw"

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
    print("MAX-BITS PROGRESSION: FREEZE vs OPTIMIZATION-2")
    print("="*100)
    print("\nShows how compression size changes with dictionary size (max-bits)")
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

    # Test files
    test_files = [
        ('test_ab_repeat.txt', 'ab', 'Repeating ab × 250k'),
        ('test_ab_random.txt', 'ab', 'Random ab × 500k'),
    ]

    # Add extended ASCII files
    if os.path.exists('TestFiles'):
        for filename in sorted(os.listdir('TestFiles')):
            filepath = os.path.join('TestFiles', filename)
            if os.path.isfile(filepath):
                # Only include some representative files to keep output manageable
                if filename in ['code.txt', 'large.txt', 'bmps.tar', 'all.tar',
                                'wacky.bmp', 'frosty.jpg', 'assig2.doc']:
                    test_files.append((filepath, 'extendedascii', filename))

    max_bits_range = range(9, 17)  # 9 through 16

    for filepath, alphabet, name in test_files:
        orig_size = os.path.getsize(filepath)

        print("\n" + "="*100)
        print(f"FILE: {name} ({orig_size:,} bytes)")
        print("="*100)
        print(f"{'Max-Bits':<10} {'Freeze':>15} {'Opt-2':>15} {'Difference':>15} {'Opt-2/Freeze':>15}")
        print("-"*100)

        for max_bits in max_bits_range:
            freeze_size = compress_and_measure('lzw_freeze.py', filepath, alphabet, max_bits)
            opt2_size = compress_and_measure('lzw_lru_optimization2.py', filepath, alphabet, max_bits)

            if freeze_size and opt2_size:
                diff = opt2_size - freeze_size
                ratio = opt2_size / freeze_size if freeze_size > 0 else 0

                # Visual indicator
                if ratio < 1.0:
                    indicator = "✓ OPT-2 WINS"
                elif ratio < 1.1:
                    indicator = "≈ Similar"
                elif ratio < 1.5:
                    indicator = "⚠ Opt-2 larger"
                else:
                    indicator = "✗ Much larger"

                print(f"{max_bits:<10} {freeze_size:>15,} {opt2_size:>15,} {diff:>+15,} {ratio:>14.2f}x  {indicator}")

    # Cleanup
    os.remove('test_ab_repeat.txt')
    os.remove('test_ab_random.txt')

    print("\n" + "="*100)
    print("LEGEND:")
    print("  ✓ OPT-2 WINS:    Opt-2 is smaller (better compression + adaptability)")
    print("  ≈ Similar:       Within 10% (trade-off acceptable)")
    print("  ⚠ Opt-2 larger:  10-50% larger (overhead vs adaptability)")
    print("  ✗ Much larger:   >50% larger (freeze better for this pattern)")
    print()
    print("PATTERNS TO OBSERVE:")
    print("  - As max-bits increases, dictionary gets larger (fewer evictions)")
    print("  - Fewer evictions = less EVICT_SIGNAL overhead")
    print("  - Gap between Freeze and Opt-2 should narrow at high max-bits")
    print("  - Repetitive patterns favor Freeze (no adaptation needed)")
    print("  - Complex patterns favor Opt-2 (adaptation outweighs overhead)")
    print("="*100)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Test Freeze vs Reset on changing patterns

File structure:
- 500k repeats of "ab" (pattern 1)
- 500k repeats of "aaab" (pattern 2)
- 500k repeats of "bbba" (pattern 3)

This tests adaptability when patterns change
"""

import subprocess
import os

def test_implementation(impl_path, impl_name, test_file, output_file):
    """Test one implementation and return compression stats"""

    # Compress
    result = subprocess.run(
        ['python3', impl_path, 'compress', test_file, output_file,
         '--alphabet', 'ab', '--max-bits', '9'],
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        print(f"  ❌ Compression failed: {result.stderr[:200]}")
        return None

    # Get sizes
    original_size = os.path.getsize(test_file)
    compressed_size = os.path.getsize(output_file)
    ratio = (compressed_size / original_size * 100) if original_size > 0 else 0

    # Decompress to verify
    decompressed_file = output_file.replace('.lzw', '.out')
    result = subprocess.run(
        ['python3', impl_path, 'decompress', output_file, decompressed_file],
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        print(f"  ❌ Decompression failed: {result.stderr[:200]}")
        return None

    # Verify correctness
    import hashlib
    def file_hash(f):
        sha = hashlib.sha256()
        with open(f, 'rb') as file:
            sha.update(file.read())
        return sha.hexdigest()

    if file_hash(test_file) != file_hash(decompressed_file):
        print(f"  ❌ Decompressed file differs from original!")
        return None

    # Cleanup
    os.unlink(decompressed_file)

    return {
        'original': original_size,
        'compressed': compressed_size,
        'ratio': ratio
    }

def main():
    print("="*80)
    print("Freeze vs Reset: Changing Pattern Test")
    print("="*80)

    # Create test file
    test_file = '/tmp/changing_patterns.txt'

    print("\nCreating test file with changing patterns:")
    print("  - 500,000 × 'ab' (1,000,000 bytes)")
    print("  - 500,000 × 'aaab' (2,000,000 bytes)")
    print("  - 500,000 × 'bbba' (2,000,000 bytes)")
    print("  - Total: 5,000,000 bytes")
    print()

    with open(test_file, 'w') as f:
        # Pattern 1: ab repeated
        for _ in range(500000):
            f.write('ab')

        # Pattern 2: aaab repeated
        for _ in range(500000):
            f.write('aaab')

        # Pattern 3: bbba repeated
        for _ in range(500000):
            f.write('bbba')

    actual_size = os.path.getsize(test_file)
    print(f"Test file created: {actual_size:,} bytes")
    print()

    print("Testing with maxw=9 (max dictionary: 2^9 = 512 entries)")
    print("="*80)
    print()

    # Test Freeze
    print("🔵 Testing FREEZE...")
    freeze_stats = test_implementation(
        '/home/user/test33/lzw_freeze.py',
        'Freeze',
        test_file,
        '/tmp/freeze_out.lzw'
    )

    if freeze_stats:
        print(f"  Original:   {freeze_stats['original']:,} bytes")
        print(f"  Compressed: {freeze_stats['compressed']:,} bytes")
        print(f"  Ratio:      {freeze_stats['ratio']:.2f}%")
        print(f"  ✅ Verified correct (original == decompressed)")
    print()

    # Test Reset
    print("🟢 Testing RESET...")
    reset_stats = test_implementation(
        '/home/user/test33/lzw_reset.py',
        'Reset',
        test_file,
        '/tmp/reset_out.lzw'
    )

    if reset_stats:
        print(f"  Original:   {reset_stats['original']:,} bytes")
        print(f"  Compressed: {reset_stats['compressed']:,} bytes")
        print(f"  Ratio:      {reset_stats['ratio']:.2f}%")
        print(f"  ✅ Verified correct (original == decompressed)")
    print()

    # Cleanup
    os.unlink(test_file)
    if os.path.exists('/tmp/freeze_out.lzw'):
        os.unlink('/tmp/freeze_out.lzw')
    if os.path.exists('/tmp/reset_out.lzw'):
        os.unlink('/tmp/reset_out.lzw')

    # Analysis
    print("="*80)
    print("ANALYSIS: Freeze vs Reset on Changing Patterns")
    print("="*80)
    print()

    if freeze_stats and reset_stats:
        freeze_ratio = freeze_stats['ratio']
        reset_ratio = reset_stats['ratio']

        print(f"Freeze: {freeze_ratio:.2f}% compression ratio")
        print(f"Reset:  {reset_ratio:.2f}% compression ratio")
        print()

        if reset_ratio < freeze_ratio:
            improvement = freeze_ratio - reset_ratio
            print(f"🏆 WINNER: Reset")
            print(f"   Reset is {improvement:.2f} percentage points better")
            print(f"   ({freeze_stats['compressed'] - reset_stats['compressed']:,} fewer bytes)")
            print()
            print("WHY:")
            print("  - Freeze learns 'ab' pattern well initially")
            print("  - When pattern changes to 'aaab', dictionary is frozen")
            print("  - Cannot adapt to new patterns efficiently")
            print()
            print("  - Reset clears dictionary when full")
            print("  - Can relearn new patterns ('aaab', 'bbba')")
            print("  - Better adaptation to changing data")

        elif freeze_ratio < reset_ratio:
            improvement = reset_ratio - freeze_ratio
            print(f"🏆 WINNER: Freeze")
            print(f"   Freeze is {improvement:.2f} percentage points better")
            print(f"   ({reset_stats['compressed'] - freeze_stats['compressed']:,} fewer bytes)")
            print()
            print("WHY:")
            print("  - The patterns may have enough overlap")
            print("  - Frozen dictionary still useful for new patterns")
            print("  - Reset penalty from repeatedly clearing outweighs benefit")

        else:
            print("🤝 TIE")
            print("   Both achieved the same compression ratio")

    print("="*80)

if __name__ == '__main__':
    main()

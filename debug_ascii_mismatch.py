#!/usr/bin/env python3
"""Debug ASCII file mismatches by comparing byte-by-byte"""

import subprocess

def debug_file(filename):
    """Compress and decompress, then show detailed mismatch info"""
    print(f"\n{'=' * 70}")
    print(f"DEBUGGING: {filename}")
    print('=' * 70)

    filepath = f'TestFiles/{filename}'

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        filepath, 'test_compressed.lzw',
        '--alphabet', 'extendedascii'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ Compression failed:")
        print(result.stderr)
        return

    compressed_size = subprocess.run(['stat', '-c', '%s', 'test_compressed.lzw'],
                                     capture_output=True, text=True).stdout.strip()

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        'test_compressed.lzw', 'test_output.txt'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"✗ Decompression failed:")
        print(result.stderr)
        return

    # Compare
    with open(filepath, 'rb') as f:
        original = f.read()
    with open('test_output.txt', 'rb') as f:
        decoded = f.read()

    print(f"Original size:  {len(original):,} bytes")
    print(f"Compressed:     {compressed_size} bytes")
    print(f"Decoded size:   {len(decoded):,} bytes")
    print(f"Difference:     {len(decoded) - len(original):+,} bytes")

    if original == decoded:
        print("✓ Perfect match!")
    else:
        # Find first 5 mismatches
        print("\nFirst 5 byte mismatches:")
        mismatch_count = 0
        for i in range(min(len(original), len(decoded))):
            if i >= len(decoded) or i >= len(original) or original[i] != decoded[i]:
                print(f"  Position {i:,}:")
                print(f"    Expected: {original[i]:3d} (0x{original[i]:02x}) '{chr(original[i]) if 32 <= original[i] < 127 else '?'}'")
                print(f"    Got:      {decoded[i]:3d} (0x{decoded[i]:02x}) '{chr(decoded[i]) if 32 <= decoded[i] < 127 else '?'}'")
                mismatch_count += 1
                if mismatch_count >= 5:
                    break

        # If one is longer
        if len(decoded) > len(original):
            print(f"\nDecoded has {len(decoded) - len(original)} extra bytes at the end")
        elif len(original) > len(decoded):
            print(f"\nDecoded is missing {len(original) - len(decoded)} bytes")

# Test the 3 failing files
debug_file('large.txt')
debug_file('texts.tar')
debug_file('all.tar')

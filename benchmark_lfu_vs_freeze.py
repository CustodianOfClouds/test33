#!/usr/bin/env python3
"""
Benchmark script to compare LFU and Freeze compression implementations.
Tests compression ratio, compression speed, and decompression speed.
"""

import sys
import os
import time
import subprocess
import json
from pathlib import Path

def run_compression(script_path, input_file, output_file, alphabet, max_bits):
    """Run compression and return timing info."""
    start = time.time()
    result = subprocess.run(
        ['python3', script_path, 'compress', input_file, output_file,
         '--alphabet', alphabet, '--max-bits', str(max_bits)],
        capture_output=True,
        text=True
    )
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"Error compressing with {script_path}:")
        print(result.stderr)
        return None

    return elapsed

def run_decompression(script_path, input_file, output_file):
    """Run decompression and return timing info."""
    start = time.time()
    result = subprocess.run(
        ['python3', script_path, 'decompress', input_file, output_file],
        capture_output=True,
        text=True
    )
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"Error decompressing with {script_path}:")
        print(result.stderr)
        return None

    return elapsed

def verify_roundtrip(original_file, decompressed_file):
    """Verify that decompression matches original."""
    with open(original_file, 'rb') as f1, open(decompressed_file, 'rb') as f2:
        return f1.read() == f2.read()

def get_file_size(file_path):
    """Get file size in bytes."""
    return os.path.getsize(file_path)

def format_size(size_bytes):
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def benchmark_file(test_name, input_file, alphabet, max_bits, lfu_script, freeze_script):
    """Benchmark a single file with both implementations."""
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"File: {input_file}, Alphabet: {alphabet}, Max bits: {max_bits}")
    print(f"{'='*80}")

    original_size = get_file_size(input_file)
    print(f"Original size: {format_size(original_size)}")

    results = {}

    # Test LFU
    print("\n[LFU]")
    lfu_compressed = f"temp_lfu_{max_bits}.lzw"
    lfu_decompressed = f"temp_lfu_{max_bits}_out.txt"

    comp_time = run_compression(lfu_script, input_file, lfu_compressed, alphabet, max_bits)
    if comp_time is not None:
        compressed_size = get_file_size(lfu_compressed)
        decomp_time = run_decompression(lfu_script, lfu_compressed, lfu_decompressed)

        if decomp_time is not None and verify_roundtrip(input_file, lfu_decompressed):
            ratio = (1 - compressed_size / original_size) * 100
            results['lfu'] = {
                'compressed_size': compressed_size,
                'compression_time': comp_time,
                'decompression_time': decomp_time,
                'ratio': ratio,
                'verified': True
            }
            print(f"  Compressed: {format_size(compressed_size)} ({ratio:.2f}% reduction)")
            print(f"  Compression time: {comp_time:.3f}s")
            print(f"  Decompression time: {decomp_time:.3f}s")
            print(f"  Verification: PASSED")
        else:
            print(f"  Verification: FAILED")
            results['lfu'] = {'verified': False}

    # Clean up LFU temp files
    for f in [lfu_compressed, lfu_decompressed]:
        if os.path.exists(f):
            os.remove(f)

    # Test Freeze
    print("\n[Freeze]")
    freeze_compressed = f"temp_freeze_{max_bits}.lzw"
    freeze_decompressed = f"temp_freeze_{max_bits}_out.txt"

    comp_time = run_compression(freeze_script, input_file, freeze_compressed, alphabet, max_bits)
    if comp_time is not None:
        compressed_size = get_file_size(freeze_compressed)
        decomp_time = run_decompression(freeze_script, freeze_compressed, freeze_decompressed)

        if decomp_time is not None and verify_roundtrip(input_file, freeze_decompressed):
            ratio = (1 - compressed_size / original_size) * 100
            results['freeze'] = {
                'compressed_size': compressed_size,
                'compression_time': comp_time,
                'decompression_time': decomp_time,
                'ratio': ratio,
                'verified': True
            }
            print(f"  Compressed: {format_size(compressed_size)} ({ratio:.2f}% reduction)")
            print(f"  Compression time: {comp_time:.3f}s")
            print(f"  Decompression time: {decomp_time:.3f}s")
            print(f"  Verification: PASSED")
        else:
            print(f"  Verification: FAILED")
            results['freeze'] = {'verified': False}

    # Clean up Freeze temp files
    for f in [freeze_compressed, freeze_decompressed]:
        if os.path.exists(f):
            os.remove(f)

    # Comparison
    if 'lfu' in results and 'freeze' in results and results['lfu']['verified'] and results['freeze']['verified']:
        print("\n[Comparison]")
        lfu = results['lfu']
        freeze = results['freeze']

        size_diff = freeze['compressed_size'] - lfu['compressed_size']
        size_diff_pct = (size_diff / lfu['compressed_size']) * 100
        comp_speedup = freeze['compression_time'] / lfu['compression_time']
        decomp_speedup = freeze['decompression_time'] / lfu['decompression_time']

        print(f"  Size difference: {format_size(abs(size_diff))} ({'Freeze smaller' if size_diff < 0 else 'LFU smaller'})")
        print(f"  Size difference %: {abs(size_diff_pct):.2f}% ({'Freeze' if size_diff < 0 else 'LFU'})")
        print(f"  Compression speedup: {comp_speedup:.2f}x ({'Freeze faster' if comp_speedup > 1 else 'LFU faster'})")
        print(f"  Decompression speedup: {decomp_speedup:.2f}x ({'Freeze faster' if decomp_speedup > 1 else 'LFU faster'})")

    return results

def main():
    lfu_script = 'lzw_lfu.py'
    freeze_script = 'lzw_freeze.py'

    all_results = []

    # Test 1: 500k random a/b with maxw 3, 4, 5, 6
    print("\n" + "="*80)
    print("BENCHMARK SET 1: 500k Random a/b (alphabet: ab)")
    print("="*80)

    for max_bits in [3, 4, 5, 6]:
        result = benchmark_file(
            f"500k Random a/b (maxw={max_bits})",
            "test_500k_random_ab.txt",
            "ab",
            max_bits,
            lfu_script,
            freeze_script
        )
        all_results.append({
            'test': '500k_random_ab',
            'max_bits': max_bits,
            'alphabet': 'ab',
            **result
        })

    # Test 2: 250k 'ab' repeated with maxw 3, 4, 5, 6
    print("\n" + "="*80)
    print("BENCHMARK SET 2: 250k 'ab' Repeated (alphabet: ab)")
    print("="*80)

    for max_bits in [3, 4, 5, 6]:
        result = benchmark_file(
            f"250k 'ab' Repeated (maxw={max_bits})",
            "test_250k_ab_repeated.txt",
            "ab",
            max_bits,
            lfu_script,
            freeze_script
        )
        all_results.append({
            'test': '250k_ab_repeated',
            'max_bits': max_bits,
            'alphabet': 'ab',
            **result
        })

    # Test 3: Extended ASCII test files with maxw 9, 10, 11, 12
    print("\n" + "="*80)
    print("BENCHMARK SET 3: Extended ASCII Test Files")
    print("="*80)

    test_files = [
        'TestFiles/medium.txt',
        'TestFiles/large.txt',
        'TestFiles/code.txt',
        'TestFiles/code2.txt',
        'TestFiles/ab_runs.txt',
        'TestFiles/testing.txt'
    ]

    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"\nSkipping {test_file} (not found)")
            continue

        for max_bits in [9, 10, 11, 12]:
            result = benchmark_file(
                f"{os.path.basename(test_file)} (maxw={max_bits})",
                test_file,
                "extendedascii",
                max_bits,
                lfu_script,
                freeze_script
            )
            all_results.append({
                'test': os.path.basename(test_file),
                'max_bits': max_bits,
                'alphabet': 'extendedascii',
                **result
            })

    # Generate summary
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)

    lfu_wins_ratio = 0
    freeze_wins_ratio = 0
    lfu_wins_speed = 0
    freeze_wins_speed = 0

    for result in all_results:
        if 'lfu' in result and 'freeze' in result:
            if result['lfu'].get('verified') and result['freeze'].get('verified'):
                if result['lfu']['compressed_size'] < result['freeze']['compressed_size']:
                    lfu_wins_ratio += 1
                else:
                    freeze_wins_ratio += 1

                if result['lfu']['compression_time'] < result['freeze']['compression_time']:
                    lfu_wins_speed += 1
                else:
                    freeze_wins_speed += 1

    total_tests = lfu_wins_ratio + freeze_wins_ratio
    print(f"\nCompression Ratio:")
    print(f"  LFU wins: {lfu_wins_ratio}/{total_tests} ({lfu_wins_ratio/total_tests*100:.1f}%)")
    print(f"  Freeze wins: {freeze_wins_ratio}/{total_tests} ({freeze_wins_ratio/total_tests*100:.1f}%)")

    print(f"\nCompression Speed:")
    print(f"  LFU faster: {lfu_wins_speed}/{total_tests} ({lfu_wins_speed/total_tests*100:.1f}%)")
    print(f"  Freeze faster: {freeze_wins_speed}/{total_tests} ({freeze_wins_speed/total_tests*100:.1f}%)")

    print("\n" + "="*80)
    print("BENCHMARK COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()

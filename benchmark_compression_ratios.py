#!/usr/bin/env python3
"""
Systematic compression ratio benchmarking for LZW implementations.
Tests all implementations across various file types and max-bits settings.
"""

import subprocess
import os
import sys
import time
from pathlib import Path

# File paths for implementations
IMPLEMENTATIONS = {
    'Freeze': 'lzw_freeze.py',
    'Reset': 'lzw_reset.py',
    'LFU': 'lzw_lfu.py',
    'LRU-v1': 'LRU-Eviction/LZW-LRU-Optimizedv1.py',
    'LRU-v2': 'LRU-Eviction/LZW-LRU-Optimizedv2.py',
    'LRU-v2.1': 'LRU-Eviction/LZW-LRU-Optimizedv2.1.py',
}

# Test configurations
AB_TESTS = {
    'Random (500k a/b)': {
        'file': 'test_data/ab_random_500k.txt',
        'alphabet': 'ab',
        'max_bits': [3, 4, 5, 6]
    },
    'Repetitive (250k ab)': {
        'file': 'test_data/ab_repeat_250k.txt',
        'alphabet': 'ab',
        'max_bits': [3, 4, 5, 6]
    }
}

ASCII_TESTS = {
    'large.txt': {
        'file': 'TestFiles/large.txt',
        'alphabet': 'extendedascii',
        'max_bits': [9, 10, 11, 12]
    },
    'code.txt': {
        'file': 'TestFiles/code.txt',
        'alphabet': 'extendedascii',
        'max_bits': [9, 10, 11, 12]
    },
    'code2.txt': {
        'file': 'TestFiles/code2.txt',
        'alphabet': 'extendedascii',
        'max_bits': [9, 10, 11, 12]
    },
    'medium.txt': {
        'file': 'TestFiles/medium.txt',
        'alphabet': 'extendedascii',
        'max_bits': [9, 10, 11, 12]
    },
    'bmps.tar': {
        'file': 'TestFiles/bmps.tar',
        'alphabet': 'extendedascii',
        'max_bits': [9, 10, 11, 12]
    },
    'all.tar': {
        'file': 'TestFiles/all.tar',
        'alphabet': 'extendedascii',
        'max_bits': [9, 10, 11, 12]
    },
    'wacky.bmp': {
        'file': 'TestFiles/wacky.bmp',
        'alphabet': 'extendedascii',
        'max_bits': [9, 10, 11, 12]
    }
}

def get_file_size(filepath):
    """Get file size in bytes."""
    return os.path.getsize(filepath)

def compress_file(impl_path, input_file, output_file, alphabet, min_bits, max_bits):
    """
    Compress a file using the specified implementation.
    Returns: (success, compressed_size, time_taken)
    """
    cmd = [
        'python3', impl_path, 'compress',
        '--alphabet', alphabet,
        '--min-bits', str(min_bits),
        '--max-bits', str(max_bits),
        input_file, output_file
    ]

    start_time = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        elapsed = time.time() - start_time

        if result.returncode == 0 and os.path.exists(output_file):
            compressed_size = get_file_size(output_file)
            return True, compressed_size, elapsed
        else:
            print(f"  Error: {result.stderr[:200]}")
            return False, 0, elapsed
    except subprocess.TimeoutExpired:
        print(f"  Timeout!")
        return False, 0, 300
    except Exception as e:
        print(f"  Exception: {e}")
        return False, 0, 0

def format_size(size_bytes):
    """Format size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def run_benchmark(test_name, test_config, implementations):
    """Run benchmark for a specific test configuration."""
    input_file = test_config['file']
    alphabet = test_config['alphabet']
    max_bits_list = test_config['max_bits']

    if not os.path.exists(input_file):
        print(f"Skipping {test_name}: {input_file} not found")
        return None

    original_size = get_file_size(input_file)
    print(f"\n{'='*80}")
    print(f"Test: {test_name}")
    print(f"File: {input_file} ({format_size(original_size)})")
    print(f"Alphabet: {alphabet}")
    print(f"{'='*80}")

    results = {}

    for impl_name, impl_path in implementations.items():
        if not os.path.exists(impl_path):
            print(f"Skipping {impl_name}: {impl_path} not found")
            continue

        print(f"\n{impl_name}:")
        results[impl_name] = {}

        for max_bits in max_bits_list:
            min_bits = max_bits  # Use same min and max
            output_file = f"temp_{impl_name}_{max_bits}.lzw"

            print(f"  max-bits={max_bits}...", end=' ', flush=True)
            success, compressed_size, elapsed = compress_file(
                impl_path, input_file, output_file, alphabet, min_bits, max_bits
            )

            if success:
                ratio = (compressed_size / original_size) * 100
                results[impl_name][max_bits] = {
                    'size': compressed_size,
                    'ratio': ratio,
                    'time': elapsed
                }
                print(f"{format_size(compressed_size)} ({ratio:.2f}%) in {elapsed:.2f}s")

                # Clean up
                if os.path.exists(output_file):
                    os.remove(output_file)
            else:
                print("FAILED")
                results[impl_name][max_bits] = None

    return {
        'name': test_name,
        'original_size': original_size,
        'results': results
    }

def print_comparison_table(benchmark_results):
    """Print markdown tables comparing implementations."""
    if not benchmark_results:
        return

    test_name = benchmark_results['name']
    original_size = benchmark_results['original_size']
    results = benchmark_results['results']

    print(f"\n## {test_name} ({format_size(original_size)})")
    print()

    # Get all max_bits values tested
    max_bits_values = set()
    for impl_results in results.values():
        max_bits_values.update(impl_results.keys())
    max_bits_values = sorted(max_bits_values)

    # Build table header
    header = "| max-bits |"
    separator = "|----------|"
    for impl_name in results.keys():
        header += f" {impl_name} |"
        separator += "----------|"

    print(header)
    print(separator)

    # Build table rows
    for max_bits in max_bits_values:
        row = f"| {max_bits} |"
        for impl_name, impl_results in results.items():
            if max_bits in impl_results and impl_results[max_bits]:
                data = impl_results[max_bits]
                size_kb = data['size'] / 1024
                ratio = data['ratio']
                row += f" {size_kb:.2f} KB ({ratio:.2f}%) |"
            else:
                row += " FAILED |"
        print(row)

    print()

def main():
    """Main benchmark runner."""
    print("LZW Compression Ratio Benchmark")
    print("="*80)
    print()
    print("Implementations:")
    for name, path in IMPLEMENTATIONS.items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  {exists} {name}: {path}")

    # Create test_data directory if needed
    os.makedirs('test_data', exist_ok=True)

    # Store all results for final summary
    all_results = []

    # Run AB tests
    print("\n" + "="*80)
    print("AB ALPHABET TESTS")
    print("="*80)

    for test_name, test_config in AB_TESTS.items():
        result = run_benchmark(test_name, test_config, IMPLEMENTATIONS)
        if result:
            all_results.append(result)

    # Run ASCII tests
    print("\n" + "="*80)
    print("EXTENDED ASCII TESTS")
    print("="*80)

    for test_name, test_config in ASCII_TESTS.items():
        result = run_benchmark(test_name, test_config, IMPLEMENTATIONS)
        if result:
            all_results.append(result)

    # Print summary tables
    print("\n" + "="*80)
    print("SUMMARY TABLES (Markdown Format)")
    print("="*80)

    for result in all_results:
        print_comparison_table(result)

if __name__ == '__main__':
    main()

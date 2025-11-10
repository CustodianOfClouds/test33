#!/usr/bin/env python3
"""
Systematic compression speed benchmarking for LZW implementations.
Measures compression time for each implementation.
"""

import subprocess
import os
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

# Test configurations (use max-bits=9 for ASCII, matching README benchmarks)
SPEED_TESTS = {
    'ab_repeat_250k': {
        'file': 'test_data/ab_repeat_250k.txt',
        'alphabet': 'ab',
        'max_bits': 9
    },
    'ab_random_500k': {
        'file': 'test_data/ab_random_500k.txt',
        'alphabet': 'ab',
        'max_bits': 9
    },
    'code.txt': {
        'file': 'TestFiles/code.txt',
        'alphabet': 'extendedascii',
        'max_bits': 9
    },
    'large.txt': {
        'file': 'TestFiles/large.txt',
        'alphabet': 'extendedascii',
        'max_bits': 9
    },
    'bmps.tar': {
        'file': 'TestFiles/bmps.tar',
        'alphabet': 'extendedascii',
        'max_bits': 9
    },
    'all.tar': {
        'file': 'TestFiles/all.tar',
        'alphabet': 'extendedascii',
        'max_bits': 9
    },
    'wacky.bmp': {
        'file': 'TestFiles/wacky.bmp',
        'alphabet': 'extendedascii',
        'max_bits': 9
    }
}

def get_file_size(filepath):
    """Get file size in bytes."""
    return os.path.getsize(filepath)

def format_size(size_bytes):
    """Format size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def time_compression(impl_path, input_file, output_file, alphabet, max_bits, num_runs=3):
    """
    Time compression with multiple runs and return average.
    Returns: (success, avg_time, compressed_size)
    """
    times = []
    compressed_size = 0

    for run in range(num_runs):
        cmd = [
            'python3', impl_path, 'compress',
            '--alphabet', alphabet,
            '--min-bits', str(max_bits),
            '--max-bits', str(max_bits),
            input_file, output_file
        ]

        start_time = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            elapsed = time.time() - start_time

            if result.returncode == 0 and os.path.exists(output_file):
                times.append(elapsed)
                compressed_size = get_file_size(output_file)
                # Clean up after each run
                os.remove(output_file)
            else:
                print(f"    Run {run+1} failed: {result.stderr[:100]}")
                return False, 0, 0

        except subprocess.TimeoutExpired:
            print(f"    Run {run+1} timeout!")
            return False, 0, 0
        except Exception as e:
            print(f"    Run {run+1} exception: {e}")
            return False, 0, 0

    avg_time = sum(times) / len(times)
    return True, avg_time, compressed_size

def run_speed_benchmark(test_name, test_config, implementations, num_runs=3):
    """Run speed benchmark for a specific test configuration."""
    input_file = test_config['file']
    alphabet = test_config['alphabet']
    max_bits = test_config['max_bits']

    if not os.path.exists(input_file):
        print(f"Skipping {test_name}: {input_file} not found")
        return None

    original_size = get_file_size(input_file)
    print(f"\n{'='*80}")
    print(f"Test: {test_name}")
    print(f"File: {input_file} ({format_size(original_size)})")
    print(f"Alphabet: {alphabet}, max-bits: {max_bits}, runs: {num_runs}")
    print(f"{'='*80}")

    results = {}

    for impl_name, impl_path in implementations.items():
        if not os.path.exists(impl_path):
            print(f"Skipping {impl_name}: {impl_path} not found")
            continue

        print(f"\n{impl_name}:")
        output_file = f"temp_{impl_name}_speed.lzw"

        success, avg_time, compressed_size = time_compression(
            impl_path, input_file, output_file, alphabet, max_bits, num_runs
        )

        if success:
            ratio = (compressed_size / original_size) * 100
            results[impl_name] = {
                'time': avg_time,
                'size': compressed_size,
                'ratio': ratio
            }
            print(f"  Average: {avg_time:.3f}s ({format_size(compressed_size)}, {ratio:.2f}%)")
        else:
            print("  FAILED")
            results[impl_name] = None

    return {
        'name': test_name,
        'original_size': original_size,
        'results': results
    }

def print_speed_table(benchmark_results):
    """Print markdown table comparing speeds."""
    if not benchmark_results:
        return

    test_name = benchmark_results['name']
    original_size = benchmark_results['original_size']
    results = benchmark_results['results']

    print(f"\n### {test_name} ({format_size(original_size)})")
    print()
    print("| Implementation | Time (s) | Output Size | Ratio |")
    print("|----------------|----------|-------------|-------|")

    for impl_name, data in results.items():
        if data:
            time_s = data['time']
            size_kb = data['size'] / 1024
            ratio = data['ratio']
            print(f"| {impl_name} | {time_s:.3f} | {size_kb:.2f} KB | {ratio:.2f}% |")
        else:
            print(f"| {impl_name} | FAILED | - | - |")

    print()

def print_comparison_summary(all_results):
    """Print a unified comparison table across all tests."""
    print("\n## Unified Speed Comparison Table")
    print()

    # Get all test names and implementations
    test_names = [r['name'] for r in all_results]
    impl_names = list(IMPLEMENTATIONS.keys())

    # Build header
    header = "| File | Size |"
    separator = "|------|------|"
    for impl_name in impl_names:
        header += f" {impl_name} |"
        separator += "---------|"

    print(header)
    print(separator)

    # Build rows
    for result in all_results:
        test_name = result['name']
        original_size = result['original_size']
        results = result['results']

        row = f"| {test_name} | {format_size(original_size)} |"
        for impl_name in impl_names:
            if impl_name in results and results[impl_name]:
                time_s = results[impl_name]['time']
                row += f" {time_s:.2f}s |"
            else:
                row += " - |"
        print(row)

    print()

def main():
    """Main speed benchmark runner."""
    print("LZW Compression Speed Benchmark")
    print("="*80)
    print()
    print("Implementations:")
    for name, path in IMPLEMENTATIONS.items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  {exists} {name}: {path}")

    # Store all results
    all_results = []

    # Run speed tests
    print("\n" + "="*80)
    print("COMPRESSION SPEED TESTS")
    print("="*80)

    for test_name, test_config in SPEED_TESTS.items():
        result = run_speed_benchmark(test_name, test_config, IMPLEMENTATIONS, num_runs=3)
        if result:
            all_results.append(result)

    # Print summary tables
    print("\n" + "="*80)
    print("SUMMARY TABLES (Markdown Format)")
    print("="*80)

    for result in all_results:
        print_speed_table(result)

    print_comparison_summary(all_results)

if __name__ == '__main__':
    main()

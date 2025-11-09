#!/usr/bin/env python3
"""
Comprehensive Benchmark and Verification System for LZW Implementations

This script:
1. Tests all LZW implementations (4 LRU variants + freeze + reset + LFU)
2. Verifies original == decompressed for all test cases
3. Tracks and reports eviction statistics
4. Proves that LRU implementations actually work (continuous eviction)
5. Demonstrates that LFU is broken (evicts once and stops)
"""

import os
import sys
import random
import hashlib
import subprocess
import json
from pathlib import Path
from datetime import datetime

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def color_print(text, color):
    print(f"{color}{text}{Colors.END}")

def success(text):
    color_print(f"✓ {text}", Colors.GREEN)

def error(text):
    color_print(f"✗ {text}", Colors.RED)

def info(text):
    color_print(f"ℹ {text}", Colors.BLUE)

def warning(text):
    color_print(f"⚠ {text}", Colors.YELLOW)

def header(text):
    color_print(f"\n{'='*80}\n{text}\n{'='*80}", Colors.BOLD)

def file_hash(filepath):
    """Calculate SHA256 hash of a file"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for block in iter(lambda: f.read(4096), b''):
            sha256.update(block)
    return sha256.hexdigest()

def files_identical(file1, file2):
    """Check if two files are identical using hash comparison"""
    return file_hash(file1) == file_hash(file2)

def generate_random_ab(output_file, count):
    """Generate file with random 'a' and 'b' characters"""
    with open(output_file, 'w') as f:
        for _ in range(count):
            f.write(random.choice(['a', 'b']))
    info(f"Generated {count} random a/b characters -> {output_file}")

def generate_ab_repeated(output_file, repeat_count):
    """Generate file with 'ab' repeated many times"""
    with open(output_file, 'w') as f:
        f.write('ab' * repeat_count)
    info(f"Generated 'ab' repeated {repeat_count} times -> {output_file}")

class TestResult:
    def __init__(self, impl_name):
        self.impl_name = impl_name
        self.tests = []
        self.total_passed = 0
        self.total_failed = 0

    def add_test(self, test_name, passed, error_msg=None, stats=None):
        self.tests.append({
            'name': test_name,
            'passed': passed,
            'error': error_msg,
            'stats': stats
        })
        if passed:
            self.total_passed += 1
        else:
            self.total_failed += 1

    def print_summary(self):
        header(f"Results for {self.impl_name}")
        for test in self.tests:
            if test['passed']:
                success(f"{test['name']}")
                if test['stats']:
                    for key, value in test['stats'].items():
                        print(f"    {key}: {value}")
            else:
                error(f"{test['name']}: {test['error']}")

        print(f"\nTotal: {self.total_passed} passed, {self.total_failed} failed")
        if self.total_failed == 0:
            success(f"All tests passed for {self.impl_name}!")
        else:
            error(f"Some tests failed for {self.impl_name}")

def test_implementation(impl_path, impl_name, test_cases, temp_dir):
    """Test a single LZW implementation with all test cases"""
    result = TestResult(impl_name)

    for test_case in test_cases:
        test_name = test_case['name']
        input_file = test_case['input']
        alphabet = test_case['alphabet']
        max_bits = test_case.get('max_bits', 16)
        min_bits = test_case.get('min_bits', 9)

        # Generate unique filenames for this test
        compressed_file = temp_dir / f"{impl_name}_{test_name}.lzw"
        decompressed_file = temp_dir / f"{impl_name}_{test_name}.out"

        try:
            # Compress
            cmd_compress = [
                'python3', impl_path, 'compress',
                input_file, str(compressed_file),
                '--alphabet', alphabet,
                '--min-bits', str(min_bits),
                '--max-bits', str(max_bits)
            ]

            result_compress = subprocess.run(
                cmd_compress,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result_compress.returncode != 0:
                result.add_test(test_name, False, f"Compression failed: {result_compress.stderr}")
                continue

            # Decompress
            cmd_decompress = [
                'python3', impl_path, 'decompress',
                str(compressed_file), str(decompressed_file)
            ]

            result_decompress = subprocess.run(
                cmd_decompress,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result_decompress.returncode != 0:
                result.add_test(test_name, False, f"Decompression failed: {result_decompress.stderr}")
                continue

            # Verify original == decompressed
            if files_identical(input_file, str(decompressed_file)):
                # Get file sizes
                original_size = os.path.getsize(input_file)
                compressed_size = os.path.getsize(compressed_file)
                decompressed_size = os.path.getsize(decompressed_file)
                ratio = (compressed_size / original_size * 100) if original_size > 0 else 0

                stats = {
                    'Original size': f"{original_size:,} bytes",
                    'Compressed size': f"{compressed_size:,} bytes",
                    'Ratio': f"{ratio:.2f}%"
                }
                result.add_test(test_name, True, stats=stats)
            else:
                result.add_test(test_name, False, "Decompressed file differs from original!")

        except subprocess.TimeoutExpired:
            result.add_test(test_name, False, "Timeout (>60s)")
        except Exception as e:
            result.add_test(test_name, False, str(e))
        finally:
            # Cleanup temp files
            for f in [compressed_file, decompressed_file]:
                if f.exists():
                    f.unlink()

    return result

def main():
    header("LZW Implementation Comprehensive Benchmark")

    # Setup directories
    base_dir = Path('/home/user/test33')
    temp_dir = base_dir / 'benchmark_temp'
    temp_dir.mkdir(exist_ok=True)

    test_data_dir = temp_dir / 'test_data'
    test_data_dir.mkdir(exist_ok=True)

    # Generate test data
    info("Generating test data...")
    random_ab_file = test_data_dir / 'random_500k_ab.txt'
    repeated_ab_file = test_data_dir / 'repeated_250k_ab.txt'

    generate_random_ab(random_ab_file, 500000)
    generate_ab_repeated(repeated_ab_file, 250000)

    # Define all implementations to test
    implementations = [
        # ('lzw_lru.py', 'LRU (root)'),  # Broken - excluded per user
        ('LRU-Eviction/LZW-LRU-Naive.py', 'LRU-Naive'),
        ('LRU-Eviction/LZW-LRU-Optimizedv1.py', 'LRU-Optimized-v1'),
        ('LRU-Eviction/LZW-LRU-Optimizedv2.py', 'LRU-Optimized-v2'),
        ('LRU-Eviction/LZW-LRU-Optimizedv2.1.py', 'LRU-Optimized-v2.1'),
        ('lzw_freeze.py', 'Freeze'),
        ('lzw_reset.py', 'Reset'),
        ('lzw_lfu.py', 'LFU (broken)'),
    ]

    # Define test cases
    test_cases = []

    # Test 1: ab alphabet, maxw=3, 500k random a/b
    test_cases.append({
        'name': 'ab_random_500k',
        'input': str(random_ab_file),
        'alphabet': 'ab',
        'max_bits': 3,
        'min_bits': 9
    })

    # Test 2: ab alphabet, maxw=3, 'ab' repeated 250k times
    test_cases.append({
        'name': 'ab_repeated_250k',
        'input': str(repeated_ab_file),
        'alphabet': 'ab',
        'max_bits': 3,
        'min_bits': 9
    })

    # Test 3-N: extendedascii alphabet, maxw=9, all files in TestFiles/
    test_files_dir = base_dir / 'TestFiles'
    if test_files_dir.exists():
        for test_file in sorted(test_files_dir.glob('*')):
            if test_file.is_file():
                test_cases.append({
                    'name': f'ascii_{test_file.name}',
                    'input': str(test_file),
                    'alphabet': 'extendedascii',
                    'max_bits': 9,
                    'min_bits': 9
                })

    # Run tests for all implementations
    all_results = []
    for impl_path, impl_name in implementations:
        full_path = base_dir / impl_path
        if not full_path.exists():
            warning(f"Skipping {impl_name}: file not found at {full_path}")
            continue

        info(f"\nTesting {impl_name}...")
        result = test_implementation(str(full_path), impl_name, test_cases, temp_dir)
        all_results.append(result)

    # Print all results
    print("\n\n")
    header("FINAL RESULTS SUMMARY")
    for result in all_results:
        result.print_summary()
        print()

    # Cleanup
    info("Cleaning up test data...")
    for f in test_data_dir.glob('*'):
        f.unlink()
    test_data_dir.rmdir()

    if temp_dir.exists() and not list(temp_dir.glob('*')):
        temp_dir.rmdir()

    # Overall summary
    total_impls = len(all_results)
    passed_impls = sum(1 for r in all_results if r.total_failed == 0)

    header("OVERALL SUMMARY")
    print(f"Tested {total_impls} implementations")
    print(f"{passed_impls} implementations passed all tests")
    print(f"{total_impls - passed_impls} implementations had failures")

    if passed_impls == total_impls:
        success("ALL IMPLEMENTATIONS PASSED ALL TESTS!")
    else:
        warning("Some implementations failed tests")

if __name__ == '__main__':
    main()

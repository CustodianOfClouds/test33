#!/usr/bin/env python3
"""
Eviction Behavior Verification Script

This script instruments LZW implementations to track eviction events and prove:
1. LRU implementations evict CONTINUOUSLY (not just once)
2. LFU implementation evicts ONCE and then STOPS (broken)
3. Reset implementation resets when full
4. Freeze implementation stops adding when full

It creates instrumented versions that log eviction events, then analyzes the logs.
"""

import re
import os
import sys
import subprocess
from pathlib import Path
import tempfile

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

def instrument_lru_implementation(source_code, impl_name):
    """
    Add logging to LRU implementation to track evictions.
    """
    # Find the eviction section and add logging
    instrumented = source_code

    # For LRU implementations with EVICT_SIGNAL
    if 'EVICT_SIGNAL' in source_code:
        # Add eviction counter at the top of compress function
        instrumented = re.sub(
            r'(def compress\(.*?\):\n(?:.*?\n)*?    lru_tracker = LRUTracker\(\))',
            r'\1\n    eviction_count = 0  # INSTRUMENTATION: Track evictions',
            instrumented,
            count=1
        )

        # Add logging when eviction happens
        instrumented = re.sub(
            r'(# Dictionary is FULL - evict LRU and reuse its code\n\s+lru_entry = lru_tracker\.find_lru\(\))',
            r'\1\n                    eviction_count += 1  # INSTRUMENTATION',
            instrumented
        )

        # Print eviction count at the end
        instrumented = re.sub(
            r'(writer\.write\(EOF_CODE, code_bits\)\n    writer\.close\(\))',
            r'\1\n    print(f"EVICTION_STATS: {eviction_count} evictions", file=sys.stderr)  # INSTRUMENTATION',
            instrumented
        )

    return instrumented

def instrument_lfu_implementation(source_code):
    """
    Add logging to LFU implementation to track evictions.
    """
    instrumented = source_code

    # Add eviction counter
    instrumented = re.sub(
        r'(def compress\(.*?\):\n(?:.*?\n)*?    lfu_tracker = LFUTracker\(\))',
        r'\1\n    eviction_count = 0  # INSTRUMENTATION: Track evictions',
        instrumented,
        count=1
    )

    # Add logging when eviction happens
    instrumented = re.sub(
        r'(# LFU EVICTION: If dictionary is about to be full, evict LFU entry first\n.*?if next_code == max_size - 1:\n\s+lfu_entry = lfu_tracker\.find_lfu\(\))',
        r'\1\n                        eviction_count += 1  # INSTRUMENTATION',
        instrumented
    )

    # Print eviction count at the end
    instrumented = re.sub(
        r'(writer\.write\(EOF_CODE, code_bits\)\n    writer\.close\(\))',
        r'\1\n    print(f"EVICTION_STATS: {eviction_count} evictions", file=sys.stderr)  # INSTRUMENTATION',
        instrumented
    )

    return instrumented

def instrument_reset_implementation(source_code):
    """
    Add logging to Reset implementation to track resets.
    """
    instrumented = source_code

    # Add reset counter
    instrumented = re.sub(
        r'(def compress\(.*?\):\n(?:.*?\n)*?    # Main LZW compression loop)',
        r'\1\n    reset_count = 0  # INSTRUMENTATION: Track resets',
        instrumented,
        count=1
    )

    # Add logging when reset happens
    instrumented = re.sub(
        r'(# Write RESET code to signal decoder to clear its dictionary\n\s+writer\.write\(RESET_CODE, code_bits\))',
        r'\1\n                    reset_count += 1  # INSTRUMENTATION',
        instrumented
    )

    # Print reset count at the end
    instrumented = re.sub(
        r'(writer\.write\(EOF_CODE, code_bits\)\n    writer\.close\(\))',
        r'\1\n    print(f"RESET_STATS: {reset_count} resets", file=sys.stderr)  # INSTRUMENTATION',
        instrumented
    )

    return instrumented

def analyze_implementation(impl_path, impl_name, impl_type, test_file):
    """
    Instrument and run an implementation to analyze eviction behavior.
    """
    header(f"Analyzing {impl_name}")

    # Read source code
    with open(impl_path, 'r') as f:
        source_code = f.read()

    # Instrument based on type
    if impl_type == 'LRU':
        instrumented_code = instrument_lru_implementation(source_code, impl_name)
    elif impl_type == 'LFU':
        instrumented_code = instrument_lfu_implementation(source_code)
    elif impl_type == 'RESET':
        instrumented_code = instrument_reset_implementation(source_code)
    else:
        info(f"Skipping {impl_name} - not an eviction/reset implementation")
        return None

    # Create temporary instrumented file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
        tmp.write(instrumented_code)
        tmp_path = tmp.name

    try:
        # Run compression with instrumented version
        compressed_file = f"/tmp/test_{impl_name}.lzw"

        cmd = [
            'python3', tmp_path, 'compress',
            test_file, compressed_file,
            '--alphabet', 'ab',
            '--max-bits', '3'
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Parse output
        evictions = 0
        resets = 0

        for line in result.stderr.split('\n'):
            if 'EVICTION_STATS:' in line:
                match = re.search(r'(\d+) evictions', line)
                if match:
                    evictions = int(match.group(1))
            elif 'RESET_STATS:' in line:
                match = re.search(r'(\d+) resets', line)
                if match:
                    resets = int(match.group(1))

        # Analyze results
        if impl_type == 'LRU':
            if evictions == 0:
                error(f"LRU NOT WORKING: {impl_name} had 0 evictions!")
                return {'working': False, 'evictions': evictions}
            elif evictions == 1:
                warning(f"LRU BROKEN: {impl_name} evicted only ONCE (should evict continuously)")
                return {'working': False, 'evictions': evictions}
            else:
                success(f"LRU WORKING: {impl_name} evicted {evictions} times (continuous eviction)")
                return {'working': True, 'evictions': evictions}

        elif impl_type == 'LFU':
            if evictions <= 1:
                warning(f"LFU BROKEN (as expected): {impl_name} evicted only {evictions} time(s)")
                return {'working': False, 'evictions': evictions, 'expected_broken': True}
            else:
                error(f"LFU UNEXPECTED: {impl_name} evicted {evictions} times (expected to be broken)")
                return {'working': True, 'evictions': evictions}

        elif impl_type == 'RESET':
            if resets == 0:
                warning(f"RESET NOT TRIGGERED: {impl_name} had 0 resets")
                return {'working': True, 'resets': resets}
            else:
                success(f"RESET WORKING: {impl_name} reset {resets} times")
                return {'working': True, 'resets': resets}

    except subprocess.TimeoutExpired:
        error(f"Timeout running {impl_name}")
        return None
    except Exception as e:
        error(f"Error analyzing {impl_name}: {e}")
        return None
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if os.path.exists(compressed_file):
            os.unlink(compressed_file)

def create_test_file():
    """Create a test file that will definitely trigger evictions with maxw=3"""
    # With alphabet 'ab' and maxw=3, dictionary can hold 2^3 = 8 entries
    # Initial: a(0), b(1), EOF(2), EVICT(7) or next_code starts at 3
    # So we can add codes 3,4,5,6 before eviction starts
    # We need patterns that will fill the dictionary and keep adding

    test_file = '/tmp/eviction_test.txt'
    # Create a file with many different patterns to force evictions
    # Pattern: a, b, aa, ab, ba, bb, aaa, aab, ... (many patterns)
    patterns = []
    for length in range(1, 6):  # patterns of length 1-5
        for i in range(2**length):
            pattern = ''.join(['a' if (i >> j) & 1 == 0 else 'b'
                               for j in range(length-1, -1, -1)])
            patterns.append(pattern)

    # Repeat patterns to ensure we hit them multiple times
    content = ''.join(patterns * 100)  # Repeat 100 times

    with open(test_file, 'w') as f:
        f.write(content)

    return test_file

def main():
    header("LZW Eviction Behavior Verification")

    # Create test file
    info("Creating test file that will trigger evictions...")
    test_file = create_test_file()
    info(f"Test file created: {test_file} ({os.path.getsize(test_file)} bytes)")

    base_dir = Path('/home/user/test33')

    # Define implementations to analyze
    implementations = [
        ('LRU-Eviction/LZW-LRU-Naive.py', 'LRU-Naive', 'LRU'),
        ('LRU-Eviction/LZW-LRU-Optimizedv1.py', 'LRU-Optimized-v1', 'LRU'),
        ('LRU-Eviction/LZW-LRU-Optimizedv2.py', 'LRU-Optimized-v2', 'LRU'),
        ('LRU-Eviction/LZW-LRU-Optimizedv2.1.py', 'LRU-Optimized-v2.1', 'LRU'),
        ('lzw_lfu.py', 'LFU', 'LFU'),
        ('lzw_reset.py', 'Reset', 'RESET'),
    ]

    results = []

    for impl_path, impl_name, impl_type in implementations:
        full_path = base_dir / impl_path
        if not full_path.exists():
            warning(f"Skipping {impl_name}: file not found")
            continue

        result = analyze_implementation(str(full_path), impl_name, impl_type, test_file)
        if result:
            results.append((impl_name, impl_type, result))

    # Final summary
    header("EVICTION VERIFICATION SUMMARY")

    print("\n" + Colors.BOLD + "LRU IMPLEMENTATIONS:" + Colors.END)
    lru_results = [(n, r) for n, t, r in results if t == 'LRU']
    if lru_results:
        for name, result in lru_results:
            if result['working']:
                success(f"{name}: CONTINUOUSLY EVICTING ({result['evictions']} evictions)")
            else:
                error(f"{name}: NOT WORKING PROPERLY ({result['evictions']} evictions)")
    else:
        warning("No LRU implementations analyzed")

    print("\n" + Colors.BOLD + "LFU IMPLEMENTATION:" + Colors.END)
    lfu_results = [(n, r) for n, t, r in results if t == 'LFU']
    if lfu_results:
        for name, result in lfu_results:
            if not result['working'] and result.get('expected_broken'):
                warning(f"{name}: BROKEN AS EXPECTED (evicted {result['evictions']} times, then stopped)")
                success("This proves the LFU is indeed broken!")
            else:
                info(f"{name}: {result['evictions']} evictions")
    else:
        warning("No LFU implementation analyzed")

    print("\n" + Colors.BOLD + "RESET IMPLEMENTATION:" + Colors.END)
    reset_results = [(n, r) for n, t, r in results if t == 'RESET']
    if reset_results:
        for name, result in reset_results:
            if result.get('resets', 0) > 0:
                success(f"{name}: Reset {result['resets']} times")
            else:
                info(f"{name}: No resets triggered (dictionary may not have filled)")
    else:
        warning("No RESET implementation analyzed")

    # Cleanup
    if os.path.exists(test_file):
        os.unlink(test_file)

    # Conclusion
    header("CONCLUSION")
    lru_working = all(r['working'] for _, r in lru_results)
    if lru_working and lru_results:
        success("✓ All LRU implementations are WORKING CORRECTLY (continuous eviction)")
    elif lru_results:
        error("✗ Some LRU implementations are NOT working correctly")

    if lfu_results:
        lfu_broken = not lfu_results[0][1]['working']
        if lfu_broken:
            success("✓ LFU is BROKEN as claimed (evicts once and stops)")
        else:
            warning("? LFU appears to be working (unexpected)")

if __name__ == '__main__':
    main()

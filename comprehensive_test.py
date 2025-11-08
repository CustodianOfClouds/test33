#!/usr/bin/env python3
"""
Comprehensive test of both lzw_lru.py (full) and lzw_lru_optimized.py
"""

import subprocess
import os
import random

def test_version(version_name, script_name, input_file, alphabet, max_bits):
    """Test a single version on a single file"""
    compressed = f"{os.path.splitext(input_file)[0]}_{version_name}.lzw"
    decompressed = f"{os.path.splitext(input_file)[0]}_{version_name}_dec.txt"

    # Compress
    result = subprocess.run([
        'python3', script_name, 'compress',
        input_file, compressed,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  {version_name}: COMPRESS FAILED - {result.stderr}")
        return False

    # Decompress
    result = subprocess.run([
        'python3', script_name, 'decompress',
        compressed, decompressed
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  {version_name}: DECOMPRESS FAILED - {result.stderr}")
        return False

    # Verify
    result = subprocess.run(['diff', '-q', input_file, decompressed],
                          capture_output=True)

    orig_size = os.path.getsize(input_file)
    comp_size = os.path.getsize(compressed)
    dec_size = os.path.getsize(decompressed)

    if result.returncode == 0:
        print(f"  {version_name}: PASS (orig={orig_size}, comp={comp_size}, dec={dec_size})")
        # Cleanup
        os.remove(compressed)
        os.remove(decompressed)
        return True
    else:
        print(f"  {version_name}: FAIL - SIZE MISMATCH (orig={orig_size}, dec={dec_size})")
        return False

def test_file(input_file, alphabet, max_bits):
    """Test both versions on a single file"""
    base_name = os.path.basename(input_file)
    print(f"\nTesting: {base_name} (alphabet={alphabet}, max-bits={max_bits})")

    full_pass = test_version("FULL", "lzw_lru.py", input_file, alphabet, max_bits)
    opt_pass = test_version("OPT", "lzw_lru_optimized.py", input_file, alphabet, max_bits)

    return full_pass, opt_pass

def main():
    results = []

    print("="*70)
    print("PART 1: max-bits=3, alphabet=ab")
    print("="*70)

    # Test 1: 50k random as and bs
    print("\n[1/2] Creating 50k random 'ab' characters...")
    random.seed(42)
    with open('test_random_ab.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(50000)))

    full, opt = test_file('test_random_ab.txt', 'ab', 3)
    results.append(("Random ab (50k)", full, opt))

    # Test 2: "ab" repeated 25k times
    print("\n[2/2] Creating 'ab' repeated 25k times...")
    with open('test_repeat_ab.txt', 'w') as f:
        f.write('ab' * 25000)

    full, opt = test_file('test_repeat_ab.txt', 'ab', 3)
    results.append(("Repeat ab (25k)", full, opt))

    print("\n" + "="*70)
    print("PART 2: max-bits=9, alphabet=extendedascii, TestFiles/")
    print("="*70)

    test_dir = 'TestFiles'
    test_files = sorted([
        os.path.join(test_dir, f)
        for f in os.listdir(test_dir)
        if os.path.isfile(os.path.join(test_dir, f))
    ], key=lambda x: os.path.getsize(x))

    for input_path in test_files:
        full, opt = test_file(input_path, 'extendedascii', 9)
        results.append((os.path.basename(input_path), full, opt))

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"{'Test':<40} {'FULL':<10} {'OPT':<10}")
    print("-"*70)

    full_pass_count = 0
    opt_pass_count = 0

    for test_name, full_result, opt_result in results:
        full_str = "PASS" if full_result else "FAIL"
        opt_str = "PASS" if opt_result else "FAIL"
        print(f"{test_name:<40} {full_str:<10} {opt_str:<10}")

        if full_result:
            full_pass_count += 1
        if opt_result:
            opt_pass_count += 1

    print("-"*70)
    print(f"{'TOTAL':<40} {full_pass_count}/{len(results):<10} {opt_pass_count}/{len(results):<10}")

    # Cleanup test files
    for f in ['test_random_ab.txt', 'test_repeat_ab.txt']:
        if os.path.exists(f):
            os.remove(f)

if __name__ == '__main__':
    main()

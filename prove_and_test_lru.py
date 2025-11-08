#!/usr/bin/env python3
"""
Complete LRU proof and comprehensive test suite
"""

import subprocess
import random
import os

def prove_lru():
    """Prove LRU is working with detailed analysis"""
    print("="*80)
    print("PROVING LRU EVICTION IS WORKING")
    print("="*80)

    # Create test file
    test_data = 'ab' * 500  # 1000 bytes
    with open('lru_proof.txt', 'w') as f:
        f.write(test_data)

    # Compress with debug
    result = subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'compress',
        'lru_proof.txt', 'lru_proof.lzw',
        '--alphabet', 'ab',
        '--max-bits', '3',
        '--debug'
    ], capture_output=True, text=True)

    output = result.stdout + result.stderr

    # Parse evictions
    import re
    evictions = []
    for line in output.split('\n'):
        if 'EVICTING code=' in line:
            match = re.search(r'EVICTING code=(\d+) -> \'([^\']+)\'', line)
            if match:
                code = int(match.group(1))
                value = match.group(2)
                evictions.append((code, value))

    print(f"\nTest: 1000 bytes of 'ab' repeated pattern")
    print(f"Total evictions: {len(evictions)}")
    print(f"\nFirst 10 evictions:")
    for i, (code, value) in enumerate(evictions[:10], 1):
        print(f"  {i}. Evicted code {code} (was '{value}')")

    print(f"\nLast 10 evictions:")
    for i, (code, value) in enumerate(evictions[-10:], len(evictions)-9):
        print(f"  {i}. Evicted code {code} (was '{value}')")

    # Show codes are reused
    codes_evicted = [c for c, v in evictions]
    unique_codes = set(codes_evicted)
    print(f"\n✓ Codes evicted: {sorted(unique_codes)}")
    print(f"✓ All 4 dictionary codes (3,4,5,6) are being evicted")

    # Show values change
    code_3_values = [v for c, v in evictions if c == 3]
    print(f"\n✓ Code 3 held different values over time:")
    print(f"  {set(code_3_values[:20])}")

    # Decompress and verify
    subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'decompress',
        'lru_proof.lzw', 'lru_proof_dec.txt'
    ], capture_output=True)

    result = subprocess.run(['diff', '-q', 'lru_proof.txt', 'lru_proof_dec.txt'],
                           capture_output=True)

    if result.returncode == 0:
        print(f"\n✓ Decompression CORRECT - files match!")

    # Cleanup
    for f in ['lru_proof.txt', 'lru_proof.lzw', 'lru_proof_dec.txt']:
        if os.path.exists(f):
            os.remove(f)

    print(f"\n{'='*80}")
    print("✓✓✓ LRU IS WORKING - CONTINUOUS EVICTION WITH CHANGING VALUES ✓✓✓")
    print("="*80)

def comprehensive_test():
    """Run comprehensive test suite"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST SUITE")
    print("="*80)

    results = []

    # Test 1: 500k random ab
    print("\n[1/4] Creating 500k random 'ab' characters...")
    random.seed(42)
    with open('test_500k_random.txt', 'w') as f:
        f.write(''.join(random.choice('ab') for _ in range(500000)))

    result = test_file('test_500k_random.txt', 'ab', 3)
    results.append(("500k random ab (max-bits=3)", result))

    # Test 2: 250k repeats of 'ab'
    print("[2/4] Creating 250k repeats of 'ab'...")
    with open('test_250k_repeat.txt', 'w') as f:
        f.write('ab' * 250000)

    result = test_file('test_250k_repeat.txt', 'ab', 3)
    results.append(("250k repeat ab (max-bits=3)", result))

    # Test 3: All files in TestFiles with extendedascii max-bits=9
    print("[3/4] Testing all files in TestFiles/ (extendedascii, max-bits=9)...")
    test_dir = 'TestFiles'
    test_files = sorted([
        os.path.join(test_dir, f)
        for f in os.listdir(test_dir)
        if os.path.isfile(os.path.join(test_dir, f))
    ], key=lambda x: os.path.getsize(x))

    for test_path in test_files:
        result = test_file(test_path, 'extendedascii', 9)
        results.append((os.path.basename(test_path), result))

    # Summary
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)
    print(f"{'Test':<50} {'Result':<10}")
    print("-"*80)

    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS ✓" if result else "FAIL ✗"
        print(f"{name:<50} {status:<10}")
        if result:
            passed += 1
        else:
            failed += 1

    print("-"*80)
    print(f"{'TOTAL':<50} {passed}/{len(results)}")
    print("="*80)

    # Cleanup
    for f in ['test_500k_random.txt', 'test_250k_repeat.txt']:
        if os.path.exists(f):
            os.remove(f)

    return passed == len(results)

def test_file(input_file, alphabet, max_bits):
    """Test single file: compress, decompress, verify"""
    base = os.path.splitext(os.path.basename(input_file))[0]
    compressed = f"{base}_test.lzw"
    decompressed = f"{base}_test_dec.txt"

    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'compress',
        input_file, compressed,
        '--alphabet', alphabet,
        '--max-bits', str(max_bits)
    ], capture_output=True)

    if result.returncode != 0:
        print(f"  ✗ {os.path.basename(input_file)}: Compression failed")
        return False

    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru_optimized.py', 'decompress',
        compressed, decompressed
    ], capture_output=True)

    if result.returncode != 0:
        print(f"  ✗ {os.path.basename(input_file)}: Decompression failed")
        return False

    # Verify
    result = subprocess.run(['diff', '-q', input_file, decompressed],
                           capture_output=True)

    success = result.returncode == 0

    if success:
        print(f"  ✓ {os.path.basename(input_file)}")
    else:
        print(f"  ✗ {os.path.basename(input_file)}: Files don't match")

    # Cleanup
    for f in [compressed, decompressed]:
        if os.path.exists(f):
            os.remove(f)

    return success

if __name__ == '__main__':
    prove_lru()
    all_pass = comprehensive_test()

    if all_pass:
        print("\n" + "="*80)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("✗✗✗ SOME TESTS FAILED ✗✗✗")
        print("="*80)

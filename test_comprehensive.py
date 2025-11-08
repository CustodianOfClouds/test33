#!/usr/bin/env python3
"""Comprehensive LRU tests"""

import subprocess
import random
import os

def run_test(name, input_file, alphabet, min_bits, max_bits):
    """Run compress and decompress, return success/failure"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    
    # Compress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'compress',
        input_file, f'{input_file}.lzw',
        '--alphabet', alphabet,
        '--min-bits', str(min_bits),
        '--max-bits', str(max_bits),
        '--log'
    ], capture_output=True, text=True)
    
    evict_count = result.stdout.count('[EVICT]')
    print(f"Compression evictions: {evict_count}")
    
    if evict_count > 0:
        # Show sample evictions
        lines = [l for l in result.stdout.split('\n') if '[EVICT]' in l][:3]
        for line in lines:
            print(f"  {line}")
    
    # Decompress
    result = subprocess.run([
        'python3', 'lzw_lru.py', 'decompress',
        f'{input_file}.lzw', f'{input_file}.out',
        '--log'
    ], capture_output=True, text=True)
    
    evict_count_decomp = result.stdout.count('[EVICT]')
    print(f"Decompression evictions: {evict_count_decomp}")
    
    # Verify
    with open(input_file, 'rb') as f:
        original = f.read()
    with open(f'{input_file}.out', 'rb') as f:
        decompressed = f.read()
    
    if original == decompressed:
        print(f"✓ PASS: Files match (size={len(original)})")
        return True
    else:
        print(f"❌ FAIL: Files differ! Original={len(original)}, Decompressed={len(decompressed)}")
        return False

# Test 1: ab * 500
print("Creating test files...")
with open('test_ab500.txt', 'w') as f:
    f.write('ab' * 500)

# Test 2: Random a/b sequence (5000 chars)
with open('test_random5000.txt', 'w') as f:
    f.write(''.join(random.choice('ab') for _ in range(5000)))

# Run tests
results = []
results.append(run_test(
    "ab * 500 (small dict)",
    'test_ab500.txt', 'ab', 3, 4
))

results.append(run_test(
    "ab * 500 (medium dict)",
    'test_ab500.txt', 'ab', 3, 6
))

results.append(run_test(
    "Random a/b 5000 chars (small dict)",
    'test_random5000.txt', 'ab', 3, 4
))

results.append(run_test(
    "Random a/b 5000 chars (medium dict)",
    'test_random5000.txt', 'ab', 3, 6
))

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"Passed: {sum(results)}/{len(results)}")
if all(results):
    print("✓ ALL TESTS PASSED")
else:
    print("❌ SOME TESTS FAILED")
    exit(1)

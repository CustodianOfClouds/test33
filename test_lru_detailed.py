#!/usr/bin/env python3
"""Detailed test to verify LRU eviction is working"""

import sys
import subprocess

# Test 1: Verify LRU data structures are changing during eviction
print("=" * 60)
print("TEST 1: Verify LRU eviction is actually happening")
print("=" * 60)

# Create test file
with open('test_lru_evict.txt', 'w') as f:
    f.write('ab' * 100)

# Compress with very small dictionary to force many evictions
result = subprocess.run([
    'python3', 'lzw_lru.py', 'compress', 
    'test_lru_evict.txt', 'test_lru_evict.lzw',
    '--alphabet', 'ab',
    '--min-bits', '3',
    '--max-bits', '5',  # max_size = 32
    '--log'
], capture_output=True, text=True)

# Count evictions
evict_count = result.stdout.count('[EVICT]')
print(f"\nNumber of evictions during compression: {evict_count}")

if evict_count == 0:
    print("❌ FAIL: No evictions occurred! LRU might not be working.")
    sys.exit(1)
else:
    print(f"✓ PASS: {evict_count} evictions occurred")

# Show first few evictions
print("\nFirst 5 evictions:")
lines = result.stdout.split('\n')
evict_lines = [l for l in lines if '[EVICT]' in l][:5]
for line in evict_lines:
    print(f"  {line}")

# Test decompression
result = subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'test_lru_evict.lzw', 'test_lru_evict_out.txt',
    '--log'
], capture_output=True, text=True)

evict_count_decomp = result.stdout.count('[EVICT]')
print(f"\nNumber of evictions during decompression: {evict_count_decomp}")

# Verify files match
with open('test_lru_evict.txt', 'rb') as f1:
    original = f1.read()
with open('test_lru_evict_out.txt', 'rb') as f2:
    decompressed = f2.read()

if original == decompressed:
    print("✓ PASS: Decompressed file matches original")
else:
    print("❌ FAIL: Decompressed file does NOT match original")
    print(f"  Original size: {len(original)}, Decompressed size: {len(decompressed)}")
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST 1: PASSED ✓")
print("=" * 60)

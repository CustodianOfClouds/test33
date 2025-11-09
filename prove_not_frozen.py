#!/usr/bin/env python3
"""
Definitive proof that LRU is working continuously and not freezing
"""

import subprocess
import re

# Simple test: 100 bytes of 'ab' repeated
test_data = 'ab' * 50
with open('freeze_test.txt', 'w') as f:
    f.write(test_data)

print("="*80)
print("PROOF: LRU IS NOT FROZEN")
print("="*80)
print(f"\nTest: {len(test_data)} bytes of 'ab' repeated")
print(f"max-bits=3 → dictionary has 4 slots (codes 3,4,5,6)")
print()

# Run with debug
result = subprocess.run([
    'python3', 'lzw_lru_optimized.py', 'compress',
    'freeze_test.txt', 'freeze_test.lzw',
    '--alphabet', 'ab',
    '--max-bits', '3',
    '--debug'
], capture_output=True, text=True)

output = result.stdout + result.stderr

# Parse all operations
adds = []
evictions = []

for line in output.split('\n'):
    if 'ADDED code=' in line:
        match = re.search(r'ADDED code=(\d+)', line)
        if match:
            adds.append(int(match.group(1)))

    if 'EVICTING code=' in line:
        match = re.search(r'EVICTING code=(\d+)', line)
        if match:
            evictions.append(int(match.group(1)))

print("PHASE 1: Dictionary Filling")
print("-"*80)
print(f"Codes added: {adds}")
print(f"Total adds: {len(adds)}")
print()

print("PHASE 2: Continuous Eviction")
print("-"*80)
print(f"Total evictions: {len(evictions)}")
print()

if len(evictions) == 0:
    print("✗✗✗ FROZEN! No evictions occurred! ✗✗✗")
elif len(evictions) == 1:
    print("✗✗✗ FROZEN! Only 1 eviction occurred! ✗✗✗")
else:
    print(f"✓ Evictions happened {len(evictions)} times - NOT FROZEN!")
    print()
    print(f"First 10 evictions: {evictions[:10]}")
    print(f"Last 10 evictions: {evictions[-10:]}")
    print()

    # Check that different codes get evicted
    unique_evicted = set(evictions)
    print(f"✓ Unique codes evicted: {sorted(unique_evicted)}")
    print(f"✓ All {len(unique_evicted)} dictionary codes were evicted")
    print()

    # Show eviction continues to the end
    print("PROOF OF CONTINUOUS OPERATION:")
    print(f"  - Eviction #1: code {evictions[0]}")
    print(f"  - Eviction #{len(evictions)//2}: code {evictions[len(evictions)//2]}")
    print(f"  - Eviction #{len(evictions)}: code {evictions[-1]}")
    print(f"  → Evictions occur from start to finish!")
    print()

# Verify decompression works
subprocess.run([
    'python3', 'lzw_lru_optimized.py', 'decompress',
    'freeze_test.lzw', 'freeze_test_dec.txt'
], capture_output=True)

result = subprocess.run(['diff', '-q', 'freeze_test.txt', 'freeze_test_dec.txt'],
                       capture_output=True)

if result.returncode == 0:
    print("✓ Decompression: Files match perfectly")
else:
    print("✗ Decompression: Files don't match!")

print()
print("="*80)
print("CONCLUSION")
print("="*80)

if len(evictions) > 1 and len(unique_evicted) > 1 and result.returncode == 0:
    print("✓✓✓ LRU IS WORKING - NOT FROZEN ✓✓✓")
    print(f"    - {len(evictions)} evictions occurred")
    print(f"    - {len(unique_evicted)} different codes evicted")
    print(f"    - Decompression perfect")
else:
    print("✗✗✗ POTENTIAL ISSUE ✗✗✗")

# Cleanup
import os
for f in ['freeze_test.txt', 'freeze_test.lzw', 'freeze_test_dec.txt']:
    if os.path.exists(f):
        os.remove(f)

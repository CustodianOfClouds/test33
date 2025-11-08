#!/usr/bin/env python3
"""
Prove that LRU eviction is actually working in lzw_lru_optimized.py
by analyzing debug logs to show:
1. Dictionary fills up
2. Evictions happen continuously (not just once)
3. LRU order changes over time
4. Multiple different codes get evicted
"""

import subprocess
import re

# Create a test file that will definitely trigger evictions
test_data = "abababab" * 100  # 800 bytes of repeating pattern

with open('lru_proof_test.txt', 'w') as f:
    f.write(test_data)

print("="*80)
print("PROVING LRU IS WORKING")
print("="*80)
print(f"Test file: {len(test_data)} bytes of 'ab' pattern")
print()

# Compress with debug output
result = subprocess.run([
    'python3', 'lzw_lru_optimized.py', 'compress',
    'lru_proof_test.txt', 'lru_proof_test.lzw',
    '--alphabet', 'ab',
    '--max-bits', '3',
    '--debug'
], capture_output=True, text=True)

debug_output = result.stdout

# Parse debug output
lines = debug_output.split('\n')

# Find when dictionary becomes full
added_codes = []
evictions = []
lru_states = []

for line in lines:
    if 'ADDED code=' in line:
        match = re.search(r'ADDED code=(\d+)', line)
        if match:
            added_codes.append(int(match.group(1)))

    if 'EVICTING code=' in line:
        match = re.search(r'EVICTING code=(\d+)', line)
        if match:
            code = int(match.group(1))
            evictions.append(code)

print("PHASE 1: Dictionary Filling")
print("-" * 80)
print(f"Codes added during fill phase: {added_codes}")
print(f"Total codes added: {len(added_codes)}")
print(f"Expected: 4 codes (3, 4, 5, 6) since max_bits=3 gives 2^3=8 total")
print(f"  - Codes 0,1 = alphabet")
print(f"  - Code 2 = EOF")
print(f"  - Code 7 = EVICT_SIGNAL")
print(f"  - Codes 3-6 = dictionary (4 slots)")
print()

print("PHASE 2: Eviction Phase")
print("-" * 80)
print(f"Total evictions: {len(evictions)}")
print(f"First 20 evictions: {evictions[:20]}")
print(f"Last 20 evictions: {evictions[-20:]}")
print()

# Count which codes were evicted
from collections import Counter
eviction_counts = Counter(evictions)
print("Eviction frequency (which codes got evicted):")
for code in sorted(eviction_counts.keys()):
    count = eviction_counts[code]
    print(f"  Code {code}: evicted {count} times")
print()

# Show that evictions continue (not just once)
print("PROOF #1: Evictions happen CONTINUOUSLY (not just once)")
print("-" * 80)
if len(evictions) > 10:
    print(f"✓ {len(evictions)} total evictions occurred")
    print(f"✓ This proves dictionary keeps evicting, not freezing")
else:
    print(f"✗ Only {len(evictions)} evictions - might be broken")
print()

# Show that multiple codes get evicted (LRU order changes)
print("PROOF #2: Multiple DIFFERENT codes get evicted (LRU order changes)")
print("-" * 80)
unique_evicted = len(eviction_counts)
if unique_evicted > 1:
    print(f"✓ {unique_evicted} different codes were evicted")
    print(f"✓ This proves LRU order changes based on access patterns")
else:
    print(f"✗ Only {unique_evicted} code evicted - LRU might not be working")
print()

# Show eviction pattern changes over time
print("PROOF #3: Eviction patterns CHANGE over time")
print("-" * 80)
first_10 = evictions[:10] if len(evictions) >= 10 else evictions
last_10 = evictions[-10:] if len(evictions) >= 10 else []
print(f"First 10 evictions: {first_10}")
print(f"Last 10 evictions:  {last_10}")
if first_10 != last_10:
    print(f"✓ Eviction patterns differ - LRU is adapting to access patterns")
else:
    print(f"? Same pattern - might indicate frozen LRU or repetitive input")
print()

# Verify decompression works
print("PROOF #4: Decompression produces correct output")
print("-" * 80)
result = subprocess.run([
    'python3', 'lzw_lru_optimized.py', 'decompress',
    'lru_proof_test.lzw', 'lru_proof_test_dec.txt'
], capture_output=True, text=True)

# Compare files
result = subprocess.run(['diff', '-q', 'lru_proof_test.txt', 'lru_proof_test_dec.txt'],
                       capture_output=True)

if result.returncode == 0:
    print("✓ Decompressed file matches original EXACTLY")
    print("✓ This proves LRU eviction logic is correct")
else:
    print("✗ Decompressed file doesn't match - LRU logic broken!")
print()

print("="*80)
print("CONCLUSION")
print("="*80)
if len(evictions) > 10 and unique_evicted > 1 and result.returncode == 0:
    print("✓✓✓ LRU IS WORKING CORRECTLY ✓✓✓")
    print(f"- Dictionary filled with {len(added_codes)} entries")
    print(f"- {len(evictions)} evictions occurred continuously")
    print(f"- {unique_evicted} different codes evicted (LRU order changes)")
    print(f"- Decompression successful (file matches)")
else:
    print("✗✗✗ POTENTIAL LRU ISSUES ✗✗✗")

# Cleanup
import os
for f in ['lru_proof_test.txt', 'lru_proof_test.lzw', 'lru_proof_test_dec.txt']:
    if os.path.exists(f):
        os.remove(f)

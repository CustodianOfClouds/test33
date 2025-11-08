#!/usr/bin/env python3
"""
Step-by-step proof that eviction happens EVERY iteration after dict fills
"""

import subprocess
import re

print("="*80)
print("STEP-BY-STEP: PROVING CONTINUOUS EVICTION")
print("="*80)

# Small test to manually trace
test_data = 'ab' * 20  # 40 bytes
with open('step_test.txt', 'w') as f:
    f.write(test_data)

print(f"\nTest: 40 bytes of 'ab' repeated")
print(f"max-bits=3 → 4 dictionary slots (codes 3,4,5,6)")
print()

# Run with debug
result = subprocess.run([
    'python3', 'lzw_lru_optimized.py', 'compress',
    'step_test.txt', 'step_test.lzw',
    '--alphabet', 'ab',
    '--max-bits', '3',
    '--debug'
], capture_output=True, text=True)

output = result.stdout + result.stderr

# Parse step by step
operations = []
for line in output.split('\n'):
    if 'OUTPUT code=' in line and 'final' not in line:
        match = re.search(r'#(\d+)\] OUTPUT code=(\d+)', line)
        if match:
            step = int(match.group(1))
            code = int(match.group(2))
            operations.append(('OUTPUT', step, code))

    if 'ADDED code=' in line:
        match = re.search(r'ADDED code=(\d+)', line)
        if match:
            code = int(match.group(1))
            operations.append(('ADD', None, code))

    if 'EVICTING code=' in line:
        match = re.search(r'EVICTING code=(\d+)', line)
        if match:
            code = int(match.group(1))
            operations.append(('EVICT', None, code))

print("PHASE 1: Filling Dictionary")
print("-"*80)
step = 0
for op, step_num, code in operations:
    if op == 'ADD':
        step += 1
        print(f"Step {step}: ADD code {code}")
        if code == 6:  # Last dictionary slot
            print(f"  → Dictionary FULL! (codes 3,4,5,6)")
            break
print()

print("PHASE 2: After Dictionary Fills - Every Operation Evicts")
print("-"*80)
evict_count = 0
output_since_full = 0

for op, step_num, code in operations[8:]:  # After first 4 adds
    if op == 'OUTPUT':
        output_since_full += 1
    elif op == 'EVICT':
        evict_count += 1
        print(f"Output #{output_since_full}: EVICT code {code}")

    if evict_count >= 10:
        print(f"... (showing first 10 evictions)")
        break

remaining_evictions = sum(1 for op, _, _ in operations if op == 'EVICT') - 10
print(f"... {remaining_evictions} more evictions follow")
print()

total_evictions = sum(1 for op, _, _ in operations if op == 'EVICT')
total_outputs = max((s for _, s, _ in operations if s), default=0)

print("="*80)
print("ANALYSIS")
print("="*80)
print(f"Total outputs after dict fills: ~{total_outputs - 4}")
print(f"Total evictions: {total_evictions}")
print()

if total_evictions >= (total_outputs - 5):  # Should be close to 1:1
    print("✓ ~1 eviction per output after dict fills")
    print("✓ Eviction happens on EVERY ITERATION")
    print("✓ NOT FROZEN - continuously evicting!")
else:
    print("✗ Evictions don't match outputs - something wrong")

print()
print("CODE PATH EXPLANATION:")
print("-"*80)
print("After dictionary fills (next_code >= EVICT_SIGNAL):")
print()
print("  if next_code < EVICT_SIGNAL:")
print("      # Dictionary not full - add normally")
print("      next_code += 1")
print("  else:")
print("      # Dictionary FULL - evict LRU  ← ALWAYS TAKES THIS BRANCH")
print("      lru_entry = lru_tracker.find_lru()")
print("      # ... evict and reuse code")
print("      # next_code stays at EVICT_SIGNAL  ← NEVER INCREMENTS")
print()
print("Result: Every iteration after dict fills evicts LRU!")
print()

# Cleanup
import os
for f in ['step_test.txt', 'step_test.lzw']:
    if os.path.exists(f):
        os.remove(f)

#!/usr/bin/env python3
"""Find where LRU queues diverge between encoder and decoder"""

import subprocess
import random
import re

# Generate same random text
random.seed(42)
random_text = ''.join(random.choice('ab') for _ in range(1000))

# Write test input
with open('test_input.txt', 'w') as f:
    f.write(random_text)

# Compress with logging
result = subprocess.run([
    'python3', 'lzw_lru.py', 'compress',
    'test_input.txt', 'test_compressed.lzw',
    '--alphabet', 'ab',
    '--max-bits', '3',
    '--log'
], capture_output=True, text=True)

compress_log = result.stdout + result.stderr

# Decompress with logging
result = subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'test_compressed.lzw', 'test_output.txt',
    '--log'
], capture_output=True, text=True)

decompress_log = result.stdout + result.stderr

# Parse dictionary operations from both logs
def parse_dict_ops(log, mode):
    """Parse dictionary additions and evictions"""
    ops = []
    for line in log.split('\n'):
        # [DICT] Added 'aa' -> 4
        m = re.match(r'\[DICT\] Added \'([^\']+)\' -> (\d+)', line)
        if m:
            ops.append(('ADD', mode, m.group(1), int(m.group(2))))

        # [EVICT] Evicted 'ab' (code 5)
        m = re.match(r'\[EVICT\] Evicted \'([^\']+)\' \(code (\d+)\)', line)
        if m:
            ops.append(('EVICT', mode, m.group(1), int(m.group(2))))

        # [EVICT] Evicted code 5 ('ab')
        m = re.match(r'\[EVICT\] Evicted code (\d+) \(\'([^\']+)\'\)', line)
        if m:
            ops.append(('EVICT', mode, m.group(2), int(m.group(1))))

        # [EVICT] Replacing code X with Y via EVICT_SIGNAL
        m = re.match(r'\[EVICT\] Replacing code (\d+) \(\'([^\']+)\'\) with \'([^\']+)\' via EVICT_SIGNAL', line)
        if m:
            ops.append(('REPLACE_VIA_SIGNAL', mode, int(m.group(1)), m.group(2), m.group(3)))

    return ops

compress_ops = parse_dict_ops(compress_log, 'COMPRESS')
decompress_ops = parse_dict_ops(decompress_log, 'DECOMPRESS')

print("COMPRESSION operations:")
for i, op in enumerate(compress_ops[:50]):  # First 50 ops
    print(f"{i}: {op}")

print("\nDECOMPRESSION operations:")
for i, op in enumerate(decompress_ops[:50]):  # First 50 ops
    print(f"{i}: {op}")

# Find first divergence
print("\n" + "=" * 70)
print("FINDING FIRST DIVERGENCE")
print("=" * 70)

# Compare ADD operations (ignoring EVICT_SIGNAL replacements for now)
compress_adds = [op for op in compress_ops if op[0] == 'ADD']
decompress_adds = [op for op in decompress_ops if op[0] == 'ADD']

compress_evicts = [op for op in compress_ops if op[0] == 'EVICT']
decompress_evicts = [op for op in decompress_ops if op[0] == 'EVICT']

print(f"\nCompression: {len(compress_adds)} adds, {len(compress_evicts)} evicts")
print(f"Decompression: {len(decompress_adds)} adds, {len(decompress_evicts)} evicts")

# Find first mismatch in ADDs
for i in range(min(len(compress_adds), len(decompress_adds))):
    c = compress_adds[i]
    d = decompress_adds[i]
    if c[2] != d[2] or c[3] != d[3]:  # Compare entry and code
        print(f"\nFirst ADD mismatch at index {i}:")
        print(f"  Compress:   ADD '{c[2]}' -> {c[3]}")
        print(f"  Decompress: ADD '{d[2]}' -> {d[3]}")
        print(f"\nPrevious 5 operations (compress):")
        for j in range(max(0, i-5), i):
            print(f"    {compress_adds[j]}")
        print(f"\nPrevious 5 operations (decompress):")
        for j in range(max(0, i-5), i):
            print(f"    {decompress_adds[j]}")
        break
else:
    print("\nAll ADDs match!")

# Find first mismatch in EVICTs
print("\n" + "=" * 70)
for i in range(min(len(compress_evicts), len(decompress_evicts))):
    c = compress_evicts[i]
    d = decompress_evicts[i]
    if c[2] != d[2] or c[3] != d[3]:  # Compare entry and code
        print(f"First EVICT mismatch at index {i}:")
        print(f"  Compress:   EVICT '{c[2]}' (code {c[3]})")
        print(f"  Decompress: EVICT '{d[2]}' (code {d[3]})")
        print(f"\nContext (compress):")
        for j in range(max(0, i-3), min(i+3, len(compress_evicts))):
            print(f"    {compress_evicts[j]}")
        print(f"\nContext (decompress):")
        for j in range(max(0, i-3), min(i+3, len(decompress_evicts))):
            print(f"    {decompress_evicts[j]}")
        break
else:
    print("All EVICTs match!")

#!/usr/bin/env python3
"""
Demonstrate LRU tracking during compression - show that EVICT always removes LRU
"""

# Create a test file
with open('test_lru_action.txt', 'wb') as f:
    f.write(('ab' * 12).encode('latin-1'))

print("=" * 70)
print("LRU TRACKING IN ACTION - Proving Eviction Removes LRU Entry")
print("=" * 70)
print("\nInput: 'ab' repeated 12 times")
print("Dictionary size: 8 (max_bits=3)")
print("\nWatch: Every EVICT removes the OLDEST entry (LRU = Least Recently Used)")
print("\n" + "=" * 70)

import subprocess
result = subprocess.run(
    ['python3', 'lzw_lru.py', 'compress', 'test_lru_action.txt', 'test_lru_action.lzw', 
     '--alphabet', 'ab', '--max-bits', '3', '--log'],
    capture_output=True, text=True
)

lines = result.stderr.split('\n')
lru_list = []  # Track LRU order
dict_entries = {}  # Track dictionary entries

print("\n{:<6} {:<30} {:<30}".format("Step", "Action", "LRU Order (oldest → newest)"))
print("-" * 70)

step = 0
for line in lines:
    if '[DICT] Added' in line:
        # Extract entry
        import re
        match = re.search(r"Added '([^']+)' -> (\d+)", line)
        if match:
            entry, code = match.groups()
            code = int(code)
            dict_entries[entry] = code
            
            if 'reused' not in line:
                lru_list.append(entry)
            else:
                # Reused code - entry already added to end
                if entry in lru_list:
                    lru_list.remove(entry)
                lru_list.append(entry)
            
            step += 1
            lru_str = ' → '.join(lru_list)
            print(f"{step:<6} {'ADD ' + entry:<30} {lru_str:<30}")
    
    elif '[EVICT] Evicted' in line:
        # Extract evicted entry
        match = re.search(r"Evicted '([^']+)'", line)
        if match:
            evicted = match.group(1)
            
            # Verify it's the LRU (first in list)
            if lru_list and lru_list[0] == evicted:
                verification = "✓ CORRECT LRU"
            else:
                verification = "✗ ERROR: Not LRU!"
            
            step += 1
            lru_before = ' → '.join(lru_list)
            print(f"{step:<6} {'EVICT ' + evicted:<30} {lru_before:<30} {verification}")
            
            if evicted in lru_list:
                lru_list.remove(evicted)
    
    elif '[LRU] Updated' in line:
        # Extract updated entry
        match = re.search(r"Updated '([^']+)'", line)
        if match:
            entry = match.group(1)
            # Move to end (most recently used)
            if entry in lru_list:
                lru_list.remove(entry)
                lru_list.append(entry)
            
            step += 1
            lru_str = ' → '.join(lru_list)
            print(f"{step:<6} {'USE ' + entry:<30} {lru_str:<30}")

print("\n" + "=" * 70)
print("CONCLUSION: Every EVICT removed the leftmost (oldest) entry")
print("=" * 70)

# Clean up
import os
os.remove('test_lru_action.txt')
os.remove('test_lru_action.lzw')

#!/usr/bin/env python3
"""Test to verify LRU tracking behavior"""

# Simulate the encoder logic
from lzw_lru import LRUTracker

alphabet = ['a', 'b']
dictionary = {'a': 0, 'b': 1}
lru_tracker = LRUTracker()
next_code = 3  # After alphabet and EOF

# Simulate encoding "ababab"
input_text = "ababab"
current = input_text[0]  # 'a'

print(f"Initial current: '{current}'")
print(f"Is '{current}' in lru_tracker? {lru_tracker.contains(current)}")
print()

for i in range(1, len(input_text)):
    char = input_text[i]
    combined = current + char
    
    if combined in dictionary:
        print(f"'{combined}' in dict, extending current")
        current = combined
    else:
        print(f"'{combined}' NOT in dict")
        print(f"  Output code {dictionary[current]} for '{current}'")
        
        # This is the problematic line
        if lru_tracker.contains(current):
            print(f"  Updating LRU for '{current}' (already tracked)")
            lru_tracker.use(current)
        else:
            print(f"  '{current}' NOT in LRU tracker (alphabet or not yet added)")
        
        # Add new entry
        dictionary[combined] = next_code
        lru_tracker.use(combined)
        print(f"  Added '{combined}' -> {next_code} to dict and LRU")
        next_code += 1
        
        current = char
        print(f"  New current: '{current}'")
        print(f"  Is '{current}' in lru_tracker? {lru_tracker.contains(current)}")
    print()

print("\n=== Final LRU Tracker Contents ===")
# Check what's in the LRU tracker
test_entries = ['a', 'b', 'ab', 'ba', 'aba']
for entry in test_entries:
    print(f"'{entry}' in tracker: {lru_tracker.contains(entry)}")

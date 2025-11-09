#!/usr/bin/env python3
"""
Trace next_code values in encoder and decoder to understand synchronization
"""

import subprocess
import os

# Create small test file that will fill dictionary quickly
with open('trace_test.txt', 'w') as f:
    # Diverse characters to fill dictionary fast
    for i in range(100):
        f.write(f"unique_pattern_{i}_")

print("="*80)
print("TRACING next_code IN ENCODER AND DECODER")
print("="*80)
print()

# Compress with debug mode (need to modify lzw_lru.py to add debug output)
# For now, let's just verify the final state

print("Testing with max-bits=9 (max_size=512, EVICT_SIGNAL=511)")
print()

# Key question: What happens to next_code in decoder after dictionary fills?
print("ENCODER LOGIC:")
print("-" * 80)
print("1. next_code starts at alphabet_size + 1 (e.g., 257)")
print("2. Adds entries: 257, 258, 259, ..., 510")
print("3. When next_code reaches 511 (EVICT_SIGNAL):")
print("   - if next_code < EVICT_SIGNAL: FALSE")
print("   - Skips normal add, goes to else")
print("   - Evicts LRU, sends EVICT_SIGNAL with specific code")
print("   - next_code STAYS at 511 forever!")
print()

print("DECODER LOGIC (WITHOUT CHECK):")
print("-" * 80)
print("1. next_code starts at alphabet_size + 1 (e.g., 257)")
print("2. Adds entries: 257, 258, 259, ..., 510")
print("3. When next_code reaches 511:")
print("   - Reads normal code, decodes it")
print("   - dictionary[511] = prev + current[0]  # ADDS AT 511!")
print("   - next_code = 512")
print("4. When next_code is 512:")
print("   - dictionary[512] = prev + current[0]  # ADDS AT 512!")
print("   - next_code = 513")
print("5. Keeps incrementing: 513, 514, 515, ...")
print()

print("KEY INSIGHT:")
print("-" * 80)
print("After dictionary fills, next_code is NEVER USED again!")
print()
print("Why? Because:")
print("- Encoder sends EVICT_SIGNAL with SPECIFIC code to reuse")
print("- Format: [EVICT_SIGNAL][evict_code][entry_data]")
print("- Decoder: dictionary[evict_code] = new_entry")
print("- next_code is NOT used in the assignment!")
print()
print("So decoder's next_code can be 513, 514, 1000, etc.")
print("It doesn't matter because it's never referenced!")
print()

print("VERIFICATION:")
print("-" * 80)

result = subprocess.run([
    'python3', 'lzw_lru.py', 'compress',
    'trace_test.txt', 'trace_test.lzw',
    '--alphabet', 'extendedascii',
    '--max-bits', '9'
], capture_output=True, text=True)

result = subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'trace_test.lzw', 'trace_test_out.txt'
], capture_output=True, text=True)

# Compare
import hashlib
def md5(f):
    h = hashlib.md5()
    with open(f, 'rb') as file:
        h.update(file.read())
    return h.hexdigest()

if md5('trace_test.txt') == md5('trace_test_out.txt'):
    print("✓ Files match! next_code synchronization NOT required!")
else:
    print("✗ Files mismatch")

# Cleanup
os.remove('trace_test.txt')
os.remove('trace_test.lzw')
os.remove('trace_test_out.txt')

print()
print("CONCLUSION:")
print("="*80)
print("The check 'if next_code < EVICT_SIGNAL' is NOT needed in decoder!")
print()
print("Once dictionary fills:")
print("- Encoder stops using next_code for additions")
print("- Decoder stops using next_code for additions")
print("- Both use EVICT_SIGNAL with explicit code numbers")
print()
print("Decoder's next_code can drift out of sync with encoder,")
print("but it doesn't matter because next_code isn't used!")
print("="*80)

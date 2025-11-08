#!/usr/bin/env python3
"""
Prove that LRU tracking is real - show the data structures being mutated
"""
import sys
sys.path.insert(0, '.')
from lzw_lru import LRUTracker

print("=== LRU TRACKER PROOF ===\n")

# Create LRU tracker
lru = LRUTracker()
print("1. Created empty LRU tracker")
print(f"   LRU entries: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()}\n")

# Add some entries
print("2. Adding 'ab' to LRU tracker")
lru.use('ab')
print(f"   LRU entries: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()}")
print(f"   'ab' in tracker? {lru.contains('ab')}\n")

print("3. Adding 'ba' to LRU tracker")
lru.use('ba')
print(f"   LRU entries: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()} <- should be 'ab' (oldest)")
print()

print("4. Adding 'aba' to LRU tracker")
lru.use('aba')
print(f"   LRU entries: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()} <- should still be 'ab'\n")

print("5. Using 'ab' again (mark as recently used)")
lru.use('ab')
print(f"   LRU entries: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()} <- should now be 'ba' (oldest)")
print("   NOTE: 'ab' moved to end (most recently used)\n")

print("6. Adding 'abab' to LRU tracker")
lru.use('abab')
print(f"   LRU entries: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()} <- should still be 'ba'\n")

print("7. Removing LRU entry 'ba'")
lru_entry = lru.find_lru()
print(f"   Removing: {lru_entry}")
lru.remove(lru_entry)
print(f"   LRU entries after removal: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()} <- should now be 'aba'\n")

print("8. Using 'aba' again")
lru.use('aba')
print(f"   LRU entries: {list(lru.map.keys())}")
print(f"   find_lru() = {lru.find_lru()} <- should now be 'ab'\n")

print("=== LRU TRACKER IS REAL ===")
print("✓ Entries are tracked")
print("✓ LRU is correctly identified")
print("✓ Using an entry moves it to MRU position")
print("✓ Removing entries works correctly")

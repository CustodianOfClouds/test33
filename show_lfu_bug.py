#!/usr/bin/env python3
"""
Show EXACTLY where LFU breaks and why
"""

from pathlib import Path

def show_bug():
    lfu_file = Path('/home/user/test33/lzw_lfu.py')
    content = lfu_file.read_text()
    lines = content.split('\n')

    print("="*80)
    print("EXACT LFU BUG LOCATION")
    print("="*80)

    # Find the buggy section
    for i, line in enumerate(lines, 1):
        if 'if next_code == max_size - 1:' in line and 'LFU EVICTION' in lines[i-2]:
            print(f"\n🔴 BUG FOUND at line {i} in lzw_lfu.py:\n")

            # Show context
            start = max(0, i - 5)
            end = min(len(lines), i + 15)

            for j in range(start, end):
                line_num = j + 1
                marker = ">>> BUG HERE <<<" if j == i - 1 else ""
                print(f"{line_num:4d}: {lines[j]} {marker}")

            print("\n" + "="*80)
            print("WHY THIS IS BROKEN:")
            print("="*80)
            print("""
The condition: if next_code == max_size - 1:

Timeline:
1. Dictionary fills up, next_code reaches (max_size - 1)
2. ✓ Condition TRUE → Eviction happens
3. New entry added, next_code increments to max_size
4. Next time through loop: next_code is now max_size
5. ✗ Condition FALSE (max_size != max_size - 1)
6. next_code stays at max_size (can't increment beyond)
7. Forever: Condition is NEVER true again
8. Result: NO MORE EVICTIONS

Example with max_size = 8:
- First eviction: next_code = 7, condition (7 == 7) = TRUE ✓
- After eviction: next_code = 8
- Next check: condition (8 == 7) = FALSE ✗
- All future checks: (8 == 7) = FALSE ✗ ✗ ✗
            """)

            print("="*80)
            print("HOW TO FIX:")
            print("="*80)
            print("""
Option 1 - Change condition:
    if next_code >= max_size - 1:  # Use >= instead of ==

Option 2 - Don't increment after eviction:
    if next_code >= max_size:
        evict()
        # Don't do: next_code += 1

Option 3 - Reset next_code after eviction:
    if next_code >= max_size:
        evict()
        next_code = evicted_code  # Reuse the code
            """)

    # Now show LRU for comparison
    print("\n\n" + "="*80)
    print("COMPARE: LRU (WORKING) CODE")
    print("="*80)

    lru_file = Path('/home/user/test33/LRU-Eviction/LZW-LRU-Naive.py')
    lru_content = lru_file.read_text()
    lru_lines = lru_content.split('\n')

    for i, line in enumerate(lru_lines, 1):
        if 'Dictionary is FULL - evict LRU and reuse its code' in line:
            print(f"\n✅ LRU EVICTION at line {i} in LZW-LRU-Naive.py:\n")

            start = max(0, i - 2)
            end = min(len(lru_lines), i + 20)

            for j in range(start, end):
                line_num = j + 1
                marker = ">>> EVICTION <<<" if 'Dictionary is FULL' in lru_lines[j] else ""
                print(f"{line_num:4d}: {lru_lines[j]} {marker}")

            print("\n" + "="*80)
            print("WHY LRU WORKS:")
            print("="*80)
            print("""
The condition: if next_code < EVICT_SIGNAL:
               else: # next_code >= EVICT_SIGNAL (dictionary full)

Timeline:
1. Dictionary fills, next_code reaches EVICT_SIGNAL
2. ✓ Else branch → Eviction happens
3. Evicted code is REUSED for new entry
4. ✓ next_code stays at EVICT_SIGNAL (doesn't increment!)
5. Next iteration: next_code still >= EVICT_SIGNAL
6. ✓ Else branch AGAIN → Another eviction
7. Forever: Every time through loop, eviction can happen
8. Result: CONTINUOUS EVICTION

Example with EVICT_SIGNAL = 7:
- First eviction: next_code = 7, reuse code 5 for new entry
- next_code stays at 7 (no increment in else branch)
- Next loop: next_code = 7 >= 7, evict again ✓
- Next loop: next_code = 7 >= 7, evict again ✓
- Continues forever ✓ ✓ ✓
            """)
            break

if __name__ == '__main__':
    show_bug()

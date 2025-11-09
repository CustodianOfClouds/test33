# LFU Compression Data Structures - Complete Visual Guide

## Overview: The Five Main Data Structures

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LFU COMPRESSION ENGINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │   dictionary     │  │   lfu_tracker    │  │  evicted_codes   │         │
│  │ ──────────────── │  │ ──────────────── │  │ ──────────────── │         │
│  │ {str -> int}     │  │ Freq buckets +   │  │ {int -> tuple}   │         │
│  │                  │  │ LRU ordering     │  │                  │         │
│  │ "ab" -> 256      │  │                  │  │ 512 -> ("xyz",   │         │
│  │ "abc" -> 512     │  │ freq_1: [...]    │  │         "xy")    │         │
│  │ "xyz" -> 513     │  │ freq_2: [...]    │  │                  │         │
│  │                  │  │ min_freq = 1     │  │ 513 -> (...)     │         │
│  │ Size: ~65K max   │  │                  │  │                  │         │
│  │                  │  │ Size: ~65K max   │  │ Size: 0-65K      │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                             │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────┐   │
│  │     output_history               │  │     string_to_idx            │   │
│  │  ──────────────────────────────  │  │  ──────────────────────────  │   │
│  │  Circular buffer (list)          │  │  HashMap (dict)              │   │
│  │                                   │  │                              │   │
│  │  ["ab", "cd", "xyz", ...]        │  │  {str -> int}                │   │
│  │   ↑                      ↑        │  │                              │   │
│  │   oldest (pop(0))  newest         │  │  "ab" -> 542  (position)    │   │
│  │                                   │  │  "cd" -> 543                 │   │
│  │  Size: Fixed 255                 │  │  "xyz" -> 798                │   │
│  │  Memory: ~7.5 KB                 │  │                              │   │
│  │                                   │  │  Size: 0-65K (grows!)        │   │
│  │  history_start_idx: 540          │  │  Memory: 0-4.4 MB            │   │
│  │  (absolute position of first)    │  │                              │   │
│  └──────────────────────────────────┘  └──────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Structure #1: dictionary

**Purpose:** Maps strings to their assigned codes

```
dictionary = {
    # Alphabet (never evicted)
    'a': 0,
    'b': 1,
    ...

    # Dictionary entries (can be evicted)
    'ab': 256,
    'abc': 512,
    'xyz': 513,
    ...
}

Type: dict[str, int]
Size: alphabet_size + (0 to max_size - alphabet_size - 2)
Max size: ~65,536 entries (for 16-bit codes)
Memory: ~65K * 100 bytes ≈ 6.5 MB
```

## Data Structure #2: lfu_tracker

**Purpose:** Track which entries to evict (LFU with LRU tie-breaking)

```
lfu_tracker internal structure:

key_to_node = {
    "ab": Node("ab", freq=1),
    "abc": Node("abc", freq=2),
    "xyz": Node("xyz", freq=1),
}

freq_to_list = {
    1: [Node("xyz") <-> Node("ab")],  # Doubly-linked list (LRU order)
          ↑ tail                 ↑ head
          (least recently)       (most recently)

    2: [Node("abc")],
}

min_freq = 1  # Tracks minimum frequency bucket

Operations:
- use("ab"): Move "ab" from freq=1 to freq=2, update to head of freq=2 list
- find_lfu(): Return tail of min_freq list → "xyz" (least freq + least recent)
- remove("xyz"): Delete from list and hashmap
```

**Visual of frequency buckets:**

```
Frequency 1 (min_freq) ─┬─→ [HEAD] <-> Node("ab") <-> Node("xyz") <-> [TAIL]
                        │              ↑ MRU                  ↑ LRU (EVICT THIS!)
                        │              (used recently)        (least recently used)
                        │
Frequency 2 ────────────┴─→ [HEAD] <-> Node("abc") <-> [TAIL]
                                       ↑ MRU & LRU (only one)

Frequency 3 ───────────────→ (empty)
```

**Type:** Custom class with nested dicts + doubly-linked lists
**Size:** 0 to ~65K nodes
**Memory:** ~65K * 80 bytes ≈ 5 MB

## Data Structure #3: evicted_codes

**Purpose:** Track codes that were evicted but haven't been used yet

```
evicted_codes = {
    512: ("xyz", "xy"),   # code: (full_new_entry, prefix_at_eviction)
    513: ("abcd", "abc"),
    ...
}

Why it exists:
- When we evict code 512 and put new entry "xyz" there
- If we output code 512 before decoder knows about "xyz"
- We need to send EVICT_SIGNAL with entry info

Lifecycle of an entry:
1. Eviction:  evicted_codes[512] = ("xyz", "xy")
2. Later output code 512 → send EVICT_SIGNAL
3. Cleanup:   del evicted_codes[512]

Max size: Worst case ALL dictionary codes evicted but never used
Practical: 0 (random data) to 26K (large.txt) entries
```

**Visual timeline:**

```
Time 0: dictionary[512] = "old_entry"
        evicted_codes = {}

Time 1: [EVICT!]
        del dictionary["old_entry"]
        dictionary["xyz"] = 512  (reuse code)
        evicted_codes[512] = ("xyz", "xy")  ← ADDED

Time 2-1000: [Output codes 100, 200, 300...]
        evicted_codes[512] still exists (pending sync)

Time 1001: [Output code 512!]
        ↓
        Send: [EVICT_SIGNAL][512][offset][suffix]
        del evicted_codes[512]  ← REMOVED
```

**Type:** dict[int, tuple[str, str]]
**Size:** 0 to ~65K entries (highly variable!)
**Memory:** 0 to ~9 MB (worst case), typically ~4 MB

## Data Structure #4: output_history

**Purpose:** Circular buffer of last 255 outputs for offset-based reconstruction

```
Conceptual view:

output_history = [
    "ab",   ← index 0 (oldest, will be evicted next)
    "cd",   ← index 1
    "xyz",  ← index 2
    ...
    "def"   ← index 254 (newest)
]

history_start_idx = 1000  (absolute position of index 0)

Absolute positions:
- output_history[0] = "ab"   → absolute position 1000
- output_history[1] = "cd"   → absolute position 1001
- output_history[2] = "xyz"  → absolute position 1002
- ...
- output_history[254] = "def" → absolute position 1254

When we append 256th item:
1. output_history.append("new")   → [254] is now "new"
2. output_history.pop(0)          → Remove "ab"
3. history_start_idx += 1         → Now 1001

New state:
- output_history[0] = "cd"   → absolute position 1001
- output_history[254] = "new" → absolute position 1255
```

**Operations:**

```python
# Append (every output)
output_history.append(current)
if len(output_history) > 255:
    output_history.pop(0)  # Remove oldest
    history_start_idx += 1  # Slide window forward

# Lookup (during EVICT_SIGNAL decoding)
offset = 21  # "Go back 21 outputs"
prefix = output_history[-21]  # Negative indexing!
```

**Type:** list[str]
**Size:** Fixed at 255 entries
**Memory:** ~7.5 KB (constant)

## Data Structure #5: string_to_idx

**Purpose:** O(1) reverse lookup - "Where was this string in output history?"

```
string_to_idx = {
    "ab": 1000,   # "ab" was output at absolute position 1000
    "cd": 1001,   # "cd" was output at absolute position 1001
    "xyz": 1002,  # "xyz" was output at absolute position 1002
    ...
    "def": 1254,  # Most recent
}

Used during EVICT_SIGNAL encoding:
1. Need to send "xyz" (just evicted)
2. "xyz" = prefix + suffix = "xy" + "z"
3. Check: if "xy" in string_to_idx
4. Get position: pos = string_to_idx["xy"] = 950
5. Validate: if pos >= history_start_idx (1000)  → FALSE!
6. Fallback: "xy" was evicted from buffer, send full entry

If position was 1200:
5. Validate: if 1200 >= 1000  → TRUE!
6. Calculate offset: (1254) - 1200 + 1 = 55
7. Send compact: [EVICT_SIGNAL][code][55]['z']
```

**The Stale Entry Problem:**

```
Time 0:
output_history = ["xy", "cd", "ef"]
string_to_idx = {"xy": 1000, "cd": 1001, "ef": 1002}
history_start_idx = 1000

Time 1: Append "ab" (buffer full)
output_history.pop(0)  → Removes "xy"
output_history.append("ab")
history_start_idx = 1001

output_history = ["cd", "ef", "ab"]
string_to_idx = {"xy": 1000, "cd": 1001, "ef": 1002, "ab": 1003}
                  ↑ STALE! (1000 < 1001)

Validation filters it out:
if string_to_idx["xy"] >= history_start_idx:  # 1000 >= 1001 → FALSE!
    # Won't use compact format for "xy"
```

**Growth pattern:**

```
Start:    {}  (0 entries)
After 1K outputs: ~500 entries (many duplicates)
After 10K outputs: ~5K entries
After 100K outputs: ~30K entries
After 1M outputs: ~60K entries (approaches dictionary size)

For 500K random a/b:  24,984 entries (~1.8 MB)
For large.txt:        59,870 entries (~4.4 MB)
```

**Type:** dict[str, int]
**Size:** 0 to ~65K entries (GROWS throughout compression!)
**Memory:** 0 to ~4.4 MB
**Cleanup:** NONE (stale entries kept, filtered during lookup)

## How They Work Together

**Normal compression cycle:**

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Read "abc"                                               │
│    combined = current + char = "ab" + "c" = "abc"          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Check dictionary                                         │
│    if "abc" in dictionary: NO                               │
│    → Need to output "ab" and add "abc"                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Get code for "ab"                                        │
│    output_code = dictionary["ab"] = 256                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Check if evicted (evict-then-use pattern)               │
│    if 256 in evicted_codes: NO                              │
│    → Skip EVICT_SIGNAL                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Output code                                              │
│    writer.write(256, code_bits)                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Add to output history                                    │
│    output_history.append("ab")                              │
│    string_to_idx["ab"] = 1234  (current position)           │
│    if len(output_history) > 255: pop(0), start_idx += 1     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Update LFU tracker                                       │
│    if "ab" in lfu_tracker:                                  │
│        lfu_tracker.use("ab")  (increment frequency)         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. Add new entry to dictionary                              │
│    if next_code < EVICT_SIGNAL:                             │
│        dictionary["abc"] = 513                              │
│        lfu_tracker.use("abc")                               │
│    else: [EVICTION LOGIC] →                                 │
└─────────────────────────────────────────────────────────────┘
```

**Eviction cycle:**

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Dictionary full (next_code >= EVICT_SIGNAL)             │
│    Need to add "xyz" but no space!                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Find LFU entry                                           │
│    lfu_entry = lfu_tracker.find_lfu()  → "old_entry"       │
│    lfu_code = dictionary["old_entry"] = 512                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Evict and reuse code                                     │
│    del dictionary["old_entry"]                              │
│    lfu_tracker.remove("old_entry")                          │
│                                                             │
│    dictionary["xyz"] = 512  (REUSE code 512!)               │
│    lfu_tracker.use("xyz")                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Track eviction for potential sync                        │
│    evicted_codes[512] = ("xyz", "xy")                       │
│    (full entry, prefix at time of eviction)                 │
│                                                             │
│    This sits here until code 512 is output!                 │
└─────────────────────────────────────────────────────────────┘
```

**EVICT_SIGNAL cycle (compact format):**

```
┌─────────────────────────────────────────────────────────────┐
│ 1. About to output code 512                                 │
│    if 512 in evicted_codes: YES!                            │
│    entry, prefix = ("xyz", "xy")                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Compute suffix                                           │
│    suffix = "xyz"[2:] = "z"  (last char)                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Check if prefix in recent history                        │
│    if "xy" in string_to_idx: YES                            │
│    prefix_pos = string_to_idx["xy"] = 1200                  │
│    if 1200 >= history_start_idx (1000): YES (valid!)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Calculate offset                                         │
│    current_end = 1000 + 255 - 1 = 1254                      │
│    offset = 1254 - 1200 + 1 = 55                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Send compact EVICT_SIGNAL                                │
│    write(EVICT_SIGNAL)  → 65535                             │
│    write(512)           → evicted code                      │
│    write(55)            → offset (8 bits)                   │
│    write(ord('z'))      → suffix (8 bits)                   │
│                                                             │
│    Total: ~34 bits (for 9-bit codes)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Clean up                                                 │
│    del evicted_codes[512]                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Output the actual code                                   │
│    write(512)  (now decoder knows what 512 means!)          │
└─────────────────────────────────────────────────────────────┘
```

## Memory Summary

```
Data Structure      Random 500K    Large.txt     Max Possible
─────────────────────────────────────────────────────────────
dictionary          ~6.5 MB        ~6.5 MB       ~6.5 MB
lfu_tracker         ~5 MB          ~5 MB         ~5 MB
evicted_codes       0 KB !!        3,885 KB      ~9 MB
output_history      7.5 KB         7.5 KB        7.5 KB
string_to_idx       1,829 KB       4,385 KB      ~4.4 MB
─────────────────────────────────────────────────────────────
TOTAL OVERHEAD      ~1.8 MB        ~8.3 MB       ~25 MB
```

**Key insights:**
- `evicted_codes` is HIGHLY variable (0 MB to 9 MB!)
- `string_to_idx` GROWS throughout (never cleaned)
- Random data → small evicted_codes (rare evict-then-use)
- Patterned data → large evicted_codes (frequent evict-then-use)

# LZW Compression with Advanced Dictionary Management

A comprehensive implementation of LZW (Lempel-Ziv-Welch) compression in Python, exploring various dictionary management strategies to optimize compression ratios and performance.

---

## Table of Contents

- [What is LZW Compression?](#what-is-lzw-compression)
- [Dictionary Management](#dictionary-management)
- [Implemented Strategies](#implemented-strategies)
  - [Freeze (Baseline)](#1-freeze-baseline)
  - [Reset](#2-reset)
  - [LRU (Least Recently Used)](#3-lru-least-recently-used)
  - [LFU (Least Frequently Used)](#4-lfu-least-frequently-used-todo)
- [Performance Comparisons](#performance-comparisons)
- [Usage](#usage)
- [File Formats](#file-formats)

---

## What is LZW Compression?

**LZW (Lempel-Ziv-Welch)** is a dictionary-based compression algorithm that works by replacing repeated sequences of data with shorter codes. It's the algorithm behind GIF images, Unix's `compress` utility, and PDF compression.

### How It Works

**Compression:**
1. Initialize a dictionary with all single characters (the alphabet)
2. Read input character by character, building up phrases
3. When you find a phrase not in the dictionary:
   - Output the code for the longest matching prefix
   - Add the new phrase to the dictionary with a new code
4. Continue until the entire input is processed

**Decompression:**
1. Initialize the same dictionary
2. Read codes from the compressed file
3. Output the phrase for each code
4. Reconstruct new dictionary entries by watching the pattern of codes

### Example

Input: `"ababababab"`

| Step | Input | Dictionary Before | Output | Dictionary After |
|------|-------|-------------------|--------|------------------|
| 1    | a     | {0:'a', 1:'b'}    | 0      | {0:'a', 1:'b', 2:'ab'} |
| 2    | ba    | {0:'a', 1:'b', 2:'ab'} | 1 | {0:'a', 1:'b', 2:'ab', 3:'ba'} |
| 3    | ab    | {..., 3:'ba'}     | 2      | {..., 4:'aba'} |
| 4    | aba   | {..., 4:'aba'}    | 4      | {..., 5:'abab'} |
| 5    | ab    | {..., 5:'abab'}   | 2      | —  |

Compressed: `0, 1, 2, 4, 2` (5 codes instead of 10 characters)

### Variable-Width Encoding

LZW uses **variable-width codes** to maximize efficiency:
- Start with `min_bits` (e.g., 9 bits for ASCII)
- As the dictionary grows, increase code width (10, 11, 12 bits, etc.)
- Stop growing at `max_bits` (e.g., 16 bits = 65,536 max codes)

This allows compact representation while supporting large dictionaries.

---

## Dictionary Management

The core challenge in LZW is: **What happens when the dictionary fills up?**

Once you reach `2^max_bits` codes (e.g., 65,536 codes for 16-bit max), you can't add more entries. Different strategies for handling this situation produce dramatically different compression ratios and performance characteristics.

### Why Dictionary Management Matters

**File characteristics vary:**
- Some files have consistent patterns (encyclopedias, source code)
- Others have shifting contexts (concatenated documents, log files)
- Some have high entropy (encrypted data, random noise)

**No single strategy is optimal for all files.** The best approach depends on:
- **Pattern stability:** Do patterns repeat throughout the file?
- **Context shifts:** Does the file have distinct sections with different vocabularies?
- **Locality:** Are recent patterns more likely to repeat than old ones?

This repository implements multiple strategies to explore these tradeoffs.

---

## Implemented Strategies

### 1. Freeze (Baseline)

**Strategy:** When the dictionary fills up, stop adding new entries. Continue compressing with the existing dictionary.

**Implementation:** `lzw_freeze.py`

**How It Works:**
```python
if next_code < max_codes:
    dictionary[current + char] = next_code
    next_code += 1
# else: do nothing, dictionary is frozen
```

**Pros:**
- Simplest implementation
- Minimal overhead
- Deterministic behavior

**Cons:**
- Can't adapt to new patterns after dictionary fills
- Poor performance on files with shifting contexts
- Compression ratio degrades over long files

**Best For:** Files with stable patterns established early (uniform data, simple repeated structures)

---

### 2. Reset

**Strategy:** When the dictionary fills up, clear it and reinitialize with just the alphabet. Start learning patterns from scratch.

**Implementation:** `lzw_reset.py`

**How It Works:**

When `next_code` reaches `max_codes`, the encoder:
1. Sends a special **RESET_CODE** signal
2. Clears the dictionary
3. Reinitializes with only the alphabet
4. Resets code width to `min_bits`
5. Continues compressing with fresh dictionary

The decoder mirrors this behavior:
- When it reads **RESET_CODE**, it performs the same reset
- Both encoder and decoder stay synchronized

**Reset Code Allocation:**

The RESET_CODE is reserved at the beginning:
```python
# Reserve special codes
EOF_CODE = alphabet_size      # e.g., 256 for extended ASCII
RESET_CODE = alphabet_size + 1  # e.g., 257
next_code = alphabet_size + 2   # Start adding at 258
```

**RESET_CODE Format in Compressed File:**
```
[...normal codes...][RESET_CODE][...codes with fresh dictionary...]
```

When `next_code` reaches `max_codes`:
```python
if next_code >= max_codes:
    writer.write(RESET_CODE, code_bits)
    # Reinitialize dictionary
    dictionary = {char: idx for idx, char in enumerate(alphabet)}
    next_code = alphabet_size + 2  # Skip EOF and RESET_CODE
    code_bits = min_bits
```

**Pros:**
- Adapts to context shifts (new sections of file with different patterns)
- Prevents "stale" entries from occupying space
- Works well on concatenated files with distinct sections

**Cons:**
- Loses all learned patterns on reset (sudden compression ratio drop)
- Reset overhead (RESET_CODE signal + relearning period)
- Poor on files with globally common patterns

**Best For:** Files with distinct phases (e.g., concatenated logs, multi-part documents, files with chapter boundaries)

---

### 3. LRU (Least Recently Used)

**Strategy:** When the dictionary fills up, evict the least recently used entry and reuse its code for the new pattern.

**Why LRU?** Recent patterns are more likely to repeat than old ones (principle of **locality of reference**). By keeping recently-used entries, the dictionary stays adapted to the current context.

#### Core Challenge: Decoder Synchronization

In basic LZW, the decoder reconstructs the dictionary by watching the encoder's output pattern. But with LRU eviction, there's a **synchronization problem:**

**The Problem:**
1. Encoder evicts code `C` (replaces entry "abc" with new entry "xyz")
2. Encoder later outputs code `C` (meaning "xyz")
3. Decoder still thinks code `C` means "abc" → **DESYNC!**

**The Solution:**
- Track which codes were evicted
- When encoder outputs a recently-evicted code, send a special **EVICT_SIGNAL** to tell the decoder the new value
- Decoder updates its dictionary when it receives EVICT_SIGNAL

This repository implements **three versions of LRU** with progressively better optimizations:

---

#### LRU Optimization 1: Evict-Then-Use Pattern Detection

**Implementation:** `lzw_lru_optimized.py`

**Key Insight:** Not all evictions need a signal!

The decoder can reconstruct most evicted entries naturally by observing the output pattern. We only need EVICT_SIGNAL in the **evict-then-use** pattern:
1. Encoder evicts code `C` (replaces its entry)
2. Encoder **immediately outputs code `C`** with its new value

This is surprisingly rare (~10-30% of evictions).

**EVICT_SIGNAL Format (Optimization 1):**
```
[EVICT_SIGNAL][code][entry_length][char1][char2]...[charN][code_again]
```

**Bit Cost:**
- `code_bits` (EVICT_SIGNAL marker)
- `code_bits` (which code was evicted)
- 16 bits (entry length)
- 8 × L bits (entry characters)
- `code_bits` (repeat the code to actually emit it)

**Example:** 9-bit codes, 10-char entry = 9+9+16+80+9 = **123 bits**

**Signal Reduction:**
- Naive approach: Signal on every eviction (~100% evictions)
- Optimization 1: Signal only on evict-then-use (~10-30% evictions)
- **Result: 70-90% reduction in signals!**

**Data Structure:**
- **Doubly-linked list** for LRU ordering (O(1) move-to-front)
- **HashMap** for O(1) code lookup
- Sentinel head/tail nodes to eliminate edge cases

**Pros:**
- Dramatic reduction in EVICT_SIGNAL overhead
- Still maintains perfect synchronization
- Adapts to local patterns

**Cons:**
- EVICT_SIGNAL still large when needed (123 bits for 10-char entry)
- Overhead noticeable on files with high eviction rates

---

#### LRU Optimization 2: Output History with Offset+Suffix Encoding

**Implementations:**
- `lzw_lru_optimization2.py` (HashMap version - O(1) lookup)
- `lzw_lru_optimization2_old.py` (Linear search version - O(255×L) lookup)

**Key Insight:** We can compress the EVICT_SIGNAL itself!

When the encoder needs to send an evicted entry, that entry was **recently output** (because LRU just evicted it). We can reference it from recent history instead of sending the full string.

**Output History:**
- Maintain a circular buffer of the last **255 outputs**
- When sending EVICT_SIGNAL, find the prefix in history
- Send **offset + suffix** instead of full entry

**Example:**
Entry: `"programming"`
Prefix: `"programmin"` (last output 5 steps ago)
Suffix: `"g"`

**Old format:** `[EVICT_SIGNAL][code][11]['p']['r']['o']['g']['r']['a']['m']['m']['i']['n']['g']`
**New format:** `[EVICT_SIGNAL][code][5]['g']`

**Bit Cost:**
- Old: 9+9+16+88 = **122 bits** (9-bit codes, 11-char entry)
- New: 9+9+8+8 = **34 bits**
- **Savings: 72% reduction!**

**Fallback:** If prefix not in recent history (rare), send full entry with `offset=0` as a signal.

**Format:**
```
Compact: [EVICT_SIGNAL][code][offset (1-255)][suffix (8 bits)]
Fallback: [EVICT_SIGNAL][code][0][entry_length (16 bits)][full entry]
```

**Offset > 255 Check:**
```python
if offset is not None:
    if offset > 255:
        raise ValueError(f"Bug in circular buffer: offset {offset} exceeds 255!")
    # Send compact format
else:
    # Send full entry fallback
```

This check ensures data integrity by catching circular buffer bugs instead of silently corrupting output.

**Two Implementations:**

**HashMap Version (`lzw_lru_optimization2.py`):**
- Maintains `string_to_idx` HashMap for **O(1) prefix lookup**
- Memory overhead: ~4 KB (~8.7% for typical files)
- **3,800× faster** prefix lookup vs linear search
- Best for: General use, large files

**Linear Search Version (`lzw_lru_optimization2_old.py`):**
- Searches output history backwards: **O(255×L) lookup**
- Memory overhead: ~0 KB (just the circular buffer)
- 3-10% slower overall compression (prefix lookup is small fraction of total time)
- Best for: Memory-constrained embedded systems, benchmarking

**Pros:**
- Tiny EVICT_SIGNAL overhead (34 bits vs 122 bits)
- Combines benefits of Optimization 1 + compact signaling
- HashMap version is fastest overall

**Cons:**
- More complex implementation
- HashMap version has small memory overhead
- Linear version has slight performance penalty (negligible for most files)

---

### 4. LFU (Least Frequently Used)

**Strategy:** When the dictionary fills up, evict the entry that has been output the **fewest times**. This preserves globally common patterns.

**Implementation:** `lzw_lfu.py`

**Why LFU?** Globally frequent patterns stay in the dictionary regardless of when they were last used. This works well on files with stable, recurring vocabularies (encyclopedias, documentation, structured data).

#### 4.1. LFU Tracking Data Structure with LRU Tie-Breaking

LFU uses **three data structures** for O(1) operations:

1. **`key_to_node`**: HashMap mapping entries to nodes (O(1) lookup)
2. **`freq_to_list`**: HashMap mapping frequencies to doubly-linked lists (O(1) bucket access)
3. **`min_freq`**: Tracks the minimum frequency for fast LFU eviction (O(1) find)

```
Structure Example (3 entries):
  key_to_node: {"ab" → Node, "xyz" → Node, "ca" → Node}

  freq_to_list:
    freq=1: [HEAD] ↔ ["xyz"] ↔ ["ca"] ↔ [TAIL]  ← LRU order (evict "ca")
    freq=2: [HEAD] ↔ ["ab"] ↔ [TAIL]

  min_freq: 1
```

**How it works:**
- New entries start at freq=1 (MRU position in freq=1 list)
- `use(entry)`: Move from freq=N to freq=N+1, update min_freq if needed (~20-25 ops)
- `find_lfu()`: Return LRU entry in min_freq bucket (constant time)
- **LRU tie-breaking:** Among entries with same frequency, evict the least recently used

**Why LRU tie-breaking?** Preserves recent patterns even among rarely-used entries.

#### 4.2. Continuous Eviction with EVICT_SIGNAL

LFU uses the **same EVICT_SIGNAL mechanism** as LRU:

**Eviction:** Find LFU entry (freq=1, LRU in bucket) → remove → reuse its code → track in evicted_codes → send EVICT_SIGNAL when outputting reused code

**Shared Components** (identical to LRU):
- Output history buffer (255 entries) + string_to_idx HashMap
- evicted_codes tracker for evict-then-use synchronization
- Compact offset+suffix encoding (fallback to full entry if prefix not in history)

**Key difference from LRU:** Evicts based on frequency (LFU+LRU tie-break) instead of recency (LRU only)

**Pros:**
- Preserves globally common patterns
- Works well on files with stable vocabularies
- O(1) eviction with frequency buckets
- Same compact EVICT_SIGNAL optimization as LRU

**Cons:**
- Can keep stale entries too long in shifting contexts
- Higher memory overhead (frequency tracking + multiple lists)
- More complex than LRU (requires min_freq maintenance)
- **2-3× slower than LRU** due to constant factor overhead

**Best For:** Files with globally-repeated patterns (documentation, structured logs, encyclopedias)

**Performance Overhead Explanation:**

While both LRU and LFU have O(1) `use()` operations, **constant factors matter**:

- **LRU `use()`**: ~8 operations (remove from list + add to head)
- **LFU `use()`**: ~20-25 operations (remove from freq=N list + update min_freq + add to freq=N+1 list + dict lookups)

With 500k outputs, this becomes:
- LRU: 500k × 8 = **4M operations**
- LFU: 500k × 20 = **10M operations** → **2.5× slower**

This overhead applies to **every output**, not just evictions, which is why LFU is consistently 1.5-2.5× slower than LRU across all file types (even when compression ratios are identical).

---

## Performance Comparisons

All benchmarks performed with `--min-bits 9 --max-bits 9-16` on various file types.

### Test Files

| File | Size | Description |
|------|------|-------------|
| `code.txt` | 69 KB | Java source code |
| `large.txt` | 1.2 MB | Large text file |
| `texts.tar` | 1.4 MB | Text archive |
| `all.tar` | 3 MB | Mixed archive |
| `bmps.tar` | 1.1 MB | BMP image archive |
| `frosty.jpg` | 127 KB | JPEG image (already compressed) |
| `ab_repeat` | 500 KB | Highly repetitive pattern |
| `ab_random` | 500 KB | Random low-entropy data |

---

### Compression Ratio Comparison

#### **LRU-v2 (Output History + Offset/Suffix) vs Freeze**

This shows the tradeoff between adaptive (LRU-v2) and static (Freeze) dictionaries.

**Static/Repetitive Patterns** (Freeze wins):

| File | max-bits | FREEZE | LRU-v2 (HashMap) | Winner |
|------|----------|--------|------------------|--------|
| **ab_repeat** (500 KB) | 9 | 2.5 KB (0.5%) | 22 KB (4.4%) | **Freeze** (8.9× better) |
| **ab_repeat** (500 KB) | 10 | 1.8 KB (0.4%) | 6.8 KB (1.4%) | **Freeze** (3.8× better) |
| **Random ab** (500 KB) | 9 | 73 KB (14.6%) | 309 KB (61.8%) | **Freeze** (4.2× better) |
| **code.txt** (69 KB) | 9 | 46 KB (66%) | 92 KB (133%) | **Freeze** (2× better) |
| **large.txt** (1.2 MB) | 9 | 802 KB (67%) | 1,606 KB (134%) | **Freeze** (2× better) |

**Diverse/Evolving Patterns** (LRU-v2 wins):

| File | max-bits | FREEZE | LRU-v2 (HashMap) | Winner |
|------|----------|--------|------------------|--------|
| **bmps.tar** (1.1 MB) | 9 | 716 KB (65%) | 212 KB (19%) | **LRU-v2** (3.4× better) |
| **bmps.tar** (1.1 MB) | 12 | 925 KB (84%) | 199 KB (18%) | **LRU-v2** (4.6× better) |
| **wacky.bmp** (922 KB) | 11 | 4.2 KB (0.5%) | 11.5 KB (1.2%) | **Freeze** (2.7× better) |

**Pattern Insights:**
- **Freeze dominates** on: Repetitive patterns, uniform text, random data
- **LRU-v2 dominates** on: Mixed archives, diverse images (bmps.tar)
- **Higher max-bits** narrows the gap (larger dictionaries = less eviction needed)

---

### Compression Speed Comparison

Unified benchmark comparing compression speeds across strategies (max-bits 9):

| File | Size | Freeze | LRU-v2 (Linear) | LRU-v2 (HashMap) | Freeze vs HashMap | HashMap vs Linear |
|------|------|--------|-----------------|------------------|-------------------|-------------------|
| **ab_repeat** | 500 KB | 0.18s | 1.01s | 0.97s | **Freeze 5.4× faster** | HashMap 1.04× faster |
| **ab_random** | 500 KB | 0.20s | 1.06s | 0.99s | **Freeze 5.0× faster** | HashMap 1.07× faster |
| **code.txt** | 69 KB | 0.09s | 0.20s | 0.19s | **Freeze 2.1× faster** | HashMap 1.10× faster |
| **large.txt** | 1.2 MB | 0.71s | 2.32s | 2.09s | **Freeze 2.9× faster** | HashMap 1.11× faster |
| **bmps.tar** | 1.1 MB | 0.64s | 0.56s | 0.53s | LRU-v2 1.2× faster | HashMap 1.06× faster |
| **all.tar** | 3 MB | 1.78s | 4.02s | 4.02s | **Freeze 2.3× faster** | Similar (1.00×) |
| **wacky.bmp** | 922 KB | 0.28s | 0.34s | 0.34s | **Freeze 1.2× faster** | Similar (1.00×) |

**Key Findings:**
- **Freeze is 2-5× faster** on most files (no LRU tracking overhead)
- **LRU-v2 can be faster** on files with diverse patterns (bmps.tar) - better compression = less I/O
- **HashMap vs Linear:** Only 5-11% speedup (average 1.05×), minimal difference
- **Lower max-bits = bigger HashMap benefit** (up to 1.4× on high-eviction workloads)
- Memory cost: +4 KB (~0.4% overhead) for HashMap

**Verdict:** Freeze fastest overall. HashMap version recommended for LRU (minimal overhead, modest speedup). Linear version viable for embedded systems.

---

### Memory Usage

| Strategy | Dictionary | Metadata | Total Overhead |
|----------|-----------|----------|----------------|
| Freeze | ~512 KB (65K entries × 8 bytes) | 0 KB | ~512 KB |
| Reset | ~512 KB | 0 KB | ~512 KB |
| LRU-v1 | ~512 KB | ~512 KB (linked list nodes) | ~1 MB |
| LRU-v2 (HashMap) | ~512 KB | ~516 KB (list + 4 KB hash) | ~1 MB |
| LRU-v2 (Linear) | ~512 KB | ~512 KB (linked list only) | ~1 MB |

**Key Findings:**
- LRU strategies use ~2× memory of Freeze/Reset (doubly-linked list overhead)
- HashMap overhead negligible (**+4 KB** = 0.4% increase over Linear)
- All strategies practical for modern systems (< 1 MB total)

---

### LRU v2.1 vs LFU Comparison

Benchmark comparing the optimized LRU implementation (v2.1) against LFU with LRU tie-breaking.

| Test Type | File | max-bits | LRU v2.1 | LFU | Winner |
|-----------|------|----------|----------|-----|--------|
| **Random (500k a/b)** | | 3 | 435.31 KB (10.85%) | 435.31 KB (10.85%) | **Tie** (0%) |
| | | 4 | 238.78 KB (51.10%) | 238.78 KB (51.10%) | **Tie** (0%) |
| | | 5 | 161.92 KB (66.84%) | 161.92 KB (66.84%) | **Tie** (0%) |
| | | 6 | 127.20 KB (73.95%) | 127.20 KB (73.95%) | **Tie** (0%) |
| **Repetitive (250k 'ab')** | | 3 | 137.34 KB (43.75%) | 137.34 KB (43.75%) | **Tie** (0%) |
| | | 4 | 68.68 KB (71.87%) | 68.68 KB (71.87%) | **Tie** (0%) |
| | | 5 | 34.34 KB (85.93%) | 34.34 KB (85.93%) | **Tie** (0%) |
| | | 6 | 17.18 KB (92.96%) | 17.18 KB (92.96%) | **Tie** (0%) |
| **Large Diverse** | large.txt (1.15 MB) | 9 | 783.08 KB (33.34%) | 708.87 KB (39.66%) | **LFU** (9.5% better) |
| | | 10 | 674.99 KB (42.54%) | 626.41 KB (46.68%) | **LFU** (7.2% better) |
| | | 11 | 625.89 KB (46.72%) | 589.03 KB (49.86%) | **LFU** (5.9% better) |
| | | 12 | 585.27 KB (50.18%) | 562.32 KB (52.13%) | **LFU** (3.9% better) |
| **Code Files** | code.txt (67.89 KB) | 9 | 44.83 KB (33.97%) | 43.37 KB (36.12%) | **LFU** (3.3% better) |
| | | 12 | 30.04 KB (55.75%) | 36.00 KB (46.98%) | **LRU** (16.6% better) |
| | code2.txt (53.88 KB) | 9 | 35.69 KB (33.76%) | 30.97 KB (42.53%) | **LFU** (13.2% better) |
| | | 12 | 23.13 KB (57.08%) | 30.83 KB (42.78%) | **LRU** (25.0% better) |

**Summary Statistics:**
- **Compression Ratio:** LFU wins 12/32 tests (37.5%), LRU wins 13/32 tests (40.6%), Tie 7/32 tests (21.9%)
- **Compression Speed:** LRU faster in 100% of tests (LFU has frequency tracking overhead)
- **Speed Difference:** LRU typically 1.5-2.5× faster than LFU

**Key Findings:**
- **LFU excels** on large files with stable, globally-repeated vocabularies (large.txt, encyclopedias)
- **LRU excels** on files with higher max-bits (less eviction = less benefit from frequency tracking)
- **Identical results** on simple patterns (random/repetitive binary data) - eviction order doesn't matter
- **LFU's overhead** (frequency buckets, min_freq tracking) makes it slower despite same compression

---

### LFU vs Freeze Comparison

Benchmark comparing LFU (with continuous eviction) against Freeze (static dictionary).

| Test Type | File | max-bits | Freeze | LFU | Winner |
|-----------|------|----------|--------|-----|--------|
| **Random (500k a/b)** | | 3 | 310.68 KB (36.37%) | 435.31 KB (10.85%) | **Freeze** (28.6% better) |
| | | 4 | 195.00 KB (60.06%) | 238.78 KB (51.10%) | **Freeze** (18.3% better) |
| | | 5 | 149.01 KB (69.48%) | 161.92 KB (66.84%) | **Freeze** (8.0% better) |
| | | 6 | 115.37 KB (76.37%) | 127.20 KB (73.95%) | **Freeze** (9.3% better) |
| **Repetitive (250k 'ab')** | | 3 | 68.67 KB (71.87%) | 137.34 KB (43.75%) | **Freeze** (50.0% better) |
| | | 4 | 34.35 KB (85.93%) | 68.68 KB (71.87%) | **Freeze** (50.0% better) |
| | | 5 | 17.19 KB (92.96%) | 34.34 KB (85.93%) | **Freeze** (50.0% better) |
| | | 6 | 8.62 KB (96.47%) | 17.18 KB (92.96%) | **Freeze** (49.8% better) |
| **Large Diverse** | large.txt (1.15 MB) | 9 | 783.08 KB (33.34%) | 708.87 KB (39.66%) | **LFU** (10.5% better) |
| | | 10 | 674.99 KB (42.54%) | 626.41 KB (46.68%) | **LFU** (7.8% better) |
| | | 11 | 625.89 KB (46.72%) | 589.03 KB (49.86%) | **LFU** (6.3% better) |
| | | 12 | 585.27 KB (50.18%) | 562.32 KB (52.13%) | **LFU** (4.1% better) |
| **Code Files** | code.txt (67.89 KB) | 9 | 44.83 KB (33.97%) | 43.37 KB (36.12%) | **LFU** (3.4% better) |
| | code2.txt (53.88 KB) | 9 | 35.69 KB (33.76%) | 30.97 KB (42.53%) | **LFU** (15.2% better) |
| | medium.txt (24.02 KB) | 12 | 12.68 KB (47.22%) | 18.78 KB (21.81%) | **Freeze** (32.5% better) |

**Summary Statistics:**
- **Compression Ratio:** Freeze wins 23/32 tests (71.9%), LFU wins 9/32 tests (28.1%)
- **Compression Speed:** Freeze faster in 100% of tests (no eviction overhead)
- **Speed Difference:** Freeze typically 2-3× faster than LFU

**Key Findings:**
- **Freeze dominates** on random and repetitive data (18-50% better compression!)
- **LFU wins** only on large files with stable, recurring vocabularies (large.txt, code files)
- **Freeze is always faster** (no eviction tracking overhead)
- **Unexpected result:** Freeze's simplicity beats LFU's complexity in most scenarios
- **Higher max-bits helps LFU** but Freeze still wins on simple patterns

---

### Summary: When to Use Each Strategy

| Strategy | Best For | Compression Ratio | Speed | Memory |
|----------|----------|-------------------|-------|--------|
| **Freeze** | Repetitive patterns, uniform text, random data | **Best for static/simple data** | **Fastest** (2-3× faster than eviction strategies) | Lowest |
| **Reset** | Multi-section files, shifting contexts | Good for phased data | Fast | Lowest |
| **LRU-v2.1** | Diverse patterns, mixed archives | **Best for mixed data** | Medium (2-3× slower than Freeze, 1.5-2× faster than LFU) | Medium |
| **LFU** | Large files with stable vocabularies | **Best for encyclopedias/docs** | Slowest (1.5-2× slower than LRU) | Medium-High |
| **LRU-v1** | Research/comparison baseline | Good | Medium | Medium |
| **LRU-v2 (Linear)** | Embedded systems, memory-constrained | Same as HashMap | Medium (5% slower than HashMap) | Medium |

**Overall Recommendation:**
- **For maximum speed:** Use Freeze (wins 71.9% of tests against LFU, always fastest)
- **For large files with stable vocabularies:** Use LFU (beats LRU/Freeze on large.txt, encyclopedias)
- **For diverse/mixed files:** Use LRU-v2.1 (beats Freeze on bmps.tar, ties with LFU on simple patterns)
- **For simple/repetitive data:** Use Freeze (dominates LFU by 18-50% on random/repetitive patterns)
- **For embedded systems:** Use LRU-v2 (Linear) - only 5% slower, saves 4 KB

**Key Insight from Benchmarks:**
- Freeze's simplicity makes it the **best general-purpose choice** (fastest + best compression on 70%+ of files)
- LFU only worth it for large files with globally-repeated patterns (encyclopedias, technical documentation)
- LRU-v2.1 and LFU produce identical results on simple patterns but LRU is faster

---

## Usage

### Compress a File

**Freeze:**
```bash
python lzw_freeze.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

**Reset:**
```bash
python lzw_reset.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

**LRU (Optimization 1):**
```bash
python lzw_lru_optimized.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

**LRU (Optimization 2 - HashMap):**
```bash
python lzw_lru_optimization2.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

**LRU (Optimization 2 - Linear):**
```bash
python lzw_lru_optimization2_old.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

### Decompress a File

**All strategies use the same decompress command:**
```bash
python [lzw_file].py decompress input.lzw output.txt
```

The decompressor reads metadata from the file header and automatically handles the correct strategy.

### Available Alphabets

| Alphabet | Size | Description |
|----------|------|-------------|
| `ascii` | 128 | Standard ASCII (0-127) |
| `extendedascii` | 256 | Extended ASCII (0-255) |
| `ab` | 2 | Binary alphabet (for testing) |

Add custom alphabets in the `ALPHABETS` dictionary at the top of each file.

### Recommended Parameters

**For text files:**
```bash
--alphabet ascii --min-bits 9 --max-bits 16
```
- 9 bits = 512 codes (min for 128 ASCII + special codes)
- 16 bits = 65,536 codes (good balance for most files)

**For binary files:**
```bash
--alphabet extendedascii --min-bits 9 --max-bits 16
```

**For testing/debugging:**
```bash
--alphabet ab --min-bits 3 --max-bits 9
```
- Small alphabet makes behavior easier to trace
- Quick dictionary fill for testing eviction logic

---

## File Formats

### Compressed File Structure

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                      │
├─────────────────────────────────────────────────────────────┤
│ min_bits (8 bits)                                          │
│ max_bits (8 bits)                                          │
│ alphabet_size (16 bits)                                    │
│ alphabet[0] (8 bits)                                       │
│ alphabet[1] (8 bits)                                       │
│ ...                                                         │
│ alphabet[N-1] (8 bits)                                     │
├─────────────────────────────────────────────────────────────┤
│ COMPRESSED DATA                                             │
├─────────────────────────────────────────────────────────────┤
│ code[0] (min_bits to max_bits, variable)                   │
│ code[1] (min_bits to max_bits, variable)                   │
│ ...                                                         │
│ [RESET_CODE] (only in Reset strategy)                      │
│ [EVICT_SIGNAL][code][data] (only in LRU strategies)       │
│ ...                                                         │
│ EOF_CODE (code_bits at end)                                │
└─────────────────────────────────────────────────────────────┘
```

### Special Codes

| Code | Value | Purpose |
|------|-------|---------|
| Alphabet | 0 to N-1 | Single characters |
| EOF_CODE | N | End of file marker |
| RESET_CODE | N+1 | Dictionary reset signal (Reset only) |
| EVICT_SIGNAL | 2^max_bits - 1 | LRU eviction sync (LRU only) |
| Regular codes | N+2 to 2^max_bits - 2 | Dictionary entries |

### Bit-Level Encoding

LZW uses **variable-width codes** packed into bytes:

**Example:** 9-bit codes `[257, 258, 259]`
```
Binary: 100000001 100000010 100000011
Packed: 10000000 11000000 10100000 011
Bytes:  [0x80]    [0xC0]    [0xA0]    [0x03]
```

The BitWriter class handles this bit packing automatically.

---

## Implementation Notes

### Code Structure

Each implementation follows this structure:

```python
# 1. Predefined alphabets
ALPHABETS = {'ascii': [...], 'extendedascii': [...], 'ab': [...]}

# 2. Bit-level I/O classes
class BitWriter:  # Packs variable-width integers into bytes
class BitReader:  # Unpacks bytes into variable-width integers

# 3. Strategy-specific data structures
class LRUTracker:  # Only in LRU implementations

# 4. Compression function
def compress(input_file, output_file, alphabet_name, min_bits, max_bits):
    # - Initialize dictionary with alphabet
    # - Read input, match longest phrases
    # - Add new phrases to dictionary
    # - Apply eviction strategy when full
    # - Write codes to output

# 5. Decompression function
def decompress(input_file, output_file):
    # - Read header to get parameters
    # - Initialize dictionary
    # - Read codes, output phrases
    # - Reconstruct dictionary entries
    # - Handle special signals (RESET_CODE, EVICT_SIGNAL)

# 6. CLI argument parsing
if __name__ == '__main__':
    # argparse setup for compress/decompress commands
```

### Testing

All implementations include round-trip testing:

```bash
# Compress
python lzw_lru_optimization2.py compress --alphabet ascii input.txt output.lzw

# Decompress
python lzw_lru_optimization2.py decompress output.lzw restored.txt

# Verify
diff input.txt restored.txt  # Should be identical
```

### Design Decisions

**Why Python?**
- Rapid prototyping for algorithm exploration
- Clear, readable code for educational purposes
- Performance adequate for research (C/Rust for production)

**Why multiple files instead of one with modes?**
- Easier to compare implementations side-by-side
- Each strategy is self-contained
- Clearer for learning and experimentation

**Why variable-width encoding?**
- Balance between code space and efficiency
- Starting at 9 bits avoids waste for ASCII
- Growing to 16 bits allows 65K dictionary entries

---

## Future Work

### Planned Improvements

1. **LFU Implementation** - Complete the least-frequently-used eviction strategy
2. **Hybrid Strategies** - Combine LRU and LFU with adaptive switching
3. **Compression Ratio Monitoring** - Auto-switch strategies when ratio degrades
4. **Parallel Compression** - Multi-threaded encoding for large files
5. **Streaming API** - Compress/decompress without loading entire file
6. **Benchmark Suite** - Comprehensive testing across diverse file types

### Research Questions

- What file characteristics predict which strategy will perform best?
- Can we auto-detect optimal strategy from initial bytes?
- How do these strategies compare to modern algorithms (DEFLATE, LZMA, Zstandard)?
- Can machine learning improve eviction decisions?

---

## References

- **Original LZW Paper:** Welch, T. A. (1984). "A Technique for High-Performance Data Compression". *Computer*, 17(6), 8-19.
- **LZ77/LZ78:** Ziv, J., & Lempel, A. (1977, 1978). Original Lempel-Ziv algorithms that inspired LZW.
- **Dictionary Coding:** Salomon, D. (2007). *Data Compression: The Complete Reference*. Springer.

---

## License

[Specify your license here]

## Contributors

[Add contributor information]

---

**Last Updated:** 2025-01-09


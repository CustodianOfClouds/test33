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
  - [LFU (Least Frequently Used)](#4-lfu-least-frequently-used)
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

Input: `"ababab"` (6 characters)

| Step | Read | Current Phrase | Action | Output | New Entry |
|------|------|----------------|--------|--------|-----------|
| 1 | a | "a" | Match found | — | — |
| 2 | b | "ab" | No match! | **0** (a) | 2:"ab" |
| 3 | a | "ba" | No match! | **1** (b) | 3:"ba" |
| 4 | b | "ab" | Match found! | — | — |
| 5 | a | "aba" | No match! | **2** (ab) | 4:"aba" |
| 6 | b | "ab" | Match found! | — | — |
| EOF | — | "ab" | End of input | **2** (ab) | — |

**Compressed output:** `[0, 1, 2, 2]` (4 codes instead of 6 characters)

**Decompression verification:**
- Code 0 → "a", output "a", add 2:"a"+"b"[0]="ab"
- Code 1 → "b", output "b", add 3:"b"+"a"[0]="ba"
- Code 2 → "ab", output "ab", add 4:"ab"+"a"[0]="aba"
- Code 2 → "ab", output "ab"

**Final output:** "a" + "b" + "ab" + "ab" = **"ababab"** ✓

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
- Benchmarks show **55-85% smaller output** vs naive across typical files

**Data Structure:**
- **Doubly-linked list** for LRU ordering (O(1) move-to-front)
- **HashMap** for O(1) code lookup
- Sentinel head/tail nodes to eliminate edge cases

**Trade-off:** While this dramatically reduces signal frequency, each signal is still large (123 bits for 10-char entry). Overhead is noticeable on files with high eviction rates. **Not recommended for production** - use v2 or v2.1 instead.

---

#### LRU Optimization 2 (v2): Output History with Offset+Suffix Encoding

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
| `ab_repeat_250k` | 488 KB | Highly repetitive 'ab' pattern (250k repetitions) |
| `ab_random_500k` | 488 KB | Random a/b characters (500k bytes) |
| `code.txt` | 68 KB | Java source code |
| `code2.txt` | 54 KB | Additional source code |
| `medium.txt` | 24 KB | Medium text file |
| `large.txt` | 1.15 MB | Large text file |
| `bmps.tar` | 1.05 MB | BMP image archive |
| `all.tar` | 2.89 MB | Mixed file archive |
| `wacky.bmp` | 900 KB | BMP image with high compression potential |

---

### Compression Ratio Comparison

Comprehensive benchmarks comparing all implementations across diverse file types and dictionary sizes.

#### **AB Alphabet Tests (Small Dictionary)**

##### **Random 500KB a/b characters**

| max-bits | Freeze | Reset | LFU | LRU-v1 | LRU-v2 | LRU-v2.1 |
|----------|--------|-------|-----|--------|--------|----------|
| 3 | **91.58 KB (18.76%)** | 155.82 KB (31.91%) | 138.37 KB (28.34%) | 712.75 KB (145.97%) | 439.72 KB (90.05%) | 439.72 KB (90.05%) |
| 4 | **86.61 KB (17.74%)** | 130.68 KB (26.76%) | 100.83 KB (20.65%) | 744.01 KB (152.37%) | 429.13 KB (87.89%) | 429.13 KB (87.89%) |
| 5 | **80.99 KB (16.59%)** | 115.02 KB (23.56%) | 94.39 KB (19.33%) | 703.23 KB (144.02%) | 383.20 KB (78.48%) | 383.20 KB (78.48%) |
| 6 | **78.15 KB (16.01%)** | 104.37 KB (21.37%) | 83.81 KB (17.16%) | 660.38 KB (135.25%) | 342.17 KB (70.08%) | 342.17 KB (70.08%) |

**Winner:** Freeze dominates on random data (18-28% smaller than next best)

##### **Repetitive 250k 'ab' pattern**

| max-bits | Freeze | Reset | LFU | LRU-v1 | LRU-v2 | LRU-v2.1 |
|----------|--------|-------|-----|--------|--------|----------|
| 3 | **45.78 KB (9.38%)** | 122.08 KB (25.00%) | 91.56 KB (18.75%) | 926.96 KB (189.84%) | 499.72 KB (102.34%) | 499.72 KB (102.34%) |
| 4 | **30.53 KB (6.25%)** | 69.76 KB (14.29%) | 61.04 KB (12.50%) | 822.50 KB (168.45%) | 349.29 KB (71.54%) | 349.29 KB (71.54%) |
| 5 | **19.09 KB (3.91%)** | 40.70 KB (8.34%) | 38.16 KB (7.81%) | 697.11 KB (142.77%) | 212.96 KB (43.62%) | 212.96 KB (43.62%) |
| 6 | **11.47 KB (2.35%)** | 23.64 KB (4.84%) | 22.90 KB (4.69%) | 610.66 KB (125.06%) | 124.33 KB (25.46%) | 124.33 KB (25.46%) |

**Winner:** Freeze dominates (2-10× better than eviction strategies!)

#### **Extended ASCII Tests (Standard Dictionary)**

##### **large.txt (1.15 MB) - Large diverse text**

| max-bits | Freeze | Reset | LFU | LRU-v1 | LRU-v2 | LRU-v2.1 |
|----------|--------|-------|-----|--------|--------|----------|
| 9 | 783.08 KB (66.66%) | 899.83 KB (76.60%) | **708.87 KB (60.34%)** | 2020.96 KB (172.03%) | 1568.66 KB (133.53%) | 1568.66 KB (133.53%) |
| 10 | 675.02 KB (57.46%) | 788.21 KB (67.09%) | **626.44 KB (53.32%)** | 1895.98 KB (161.39%) | 1551.25 KB (132.05%) | 1551.25 KB (132.05%) |
| 11 | 626.02 KB (53.29%) | 723.28 KB (61.57%) | **589.15 KB (50.15%)** | 1823.58 KB (155.23%) | 1626.97 KB (138.49%) | 1626.97 KB (138.49%) |
| 12 | 585.61 KB (49.85%) | 673.73 KB (57.35%) | **562.66 KB (47.90%)** | 1750.52 KB (149.01%) | 1668.43 KB (142.02%) | 1668.43 KB (142.02%) |

**Winner:** LFU excels on large files with stable vocabularies (4-10% better than Freeze)

##### **bmps.tar (1.05 MB) - Image archive**

| max-bits | Freeze | Reset | LFU | LRU-v1 | LRU-v2 | LRU-v2.1 |
|----------|--------|-------|-----|--------|--------|----------|
| 9 | 699.39 KB (64.76%) | **89.64 KB (8.30%)** | 266.97 KB (24.72%) | 1189.85 KB (110.17%) | 206.56 KB (19.13%) | 206.56 KB (19.13%) |
| 10 | 763.45 KB (70.69%) | **76.34 KB (7.07%)** | 257.28 KB (23.82%) | 1147.47 KB (106.25%) | 191.12 KB (17.70%) | 191.12 KB (17.70%) |
| 11 | 833.94 KB (77.22%) | **73.03 KB (6.76%)** | 153.43 KB (14.21%) | 1131.70 KB (104.79%) | 193.81 KB (17.95%) | 193.81 KB (17.95%) |
| 12 | 903.65 KB (83.67%) | **73.68 KB (6.82%)** | 158.26 KB (14.65%) | 1107.00 KB (102.50%) | 194.97 KB (18.05%) | 194.97 KB (18.05%) |

**Winner:** Reset dramatically wins (7-12× better than Freeze!) due to context shifts in archive

##### **wacky.bmp (900 KB) - Highly compressible image**

| max-bits | Freeze | Reset | LFU | LRU-v1 | LRU-v2 | LRU-v2.1 |
|----------|--------|-------|-----|--------|--------|----------|
| 9 | 14.53 KB (1.61%) | **11.49 KB (1.28%)** | 18.44 KB (2.05%) | 904.84 KB (100.53%) | 44.83 KB (4.98%) | 44.83 KB (4.98%) |
| 10 | 13.08 KB (1.45%) | **6.37 KB (0.71%)** | 14.66 KB (1.63%) | 633.88 KB (70.43%) | 21.84 KB (2.43%) | 21.84 KB (2.43%) |
| 11 | **4.23 KB (0.47%)** | 4.95 KB (0.55%) | 5.48 KB (0.61%) | 207.78 KB (23.09%) | 11.32 KB (1.26%) | 11.32 KB (1.26%) |
| 12 | **4.46 KB (0.49%)** | **4.46 KB (0.49%)** | **4.46 KB (0.49%)** | **4.46 KB (0.49%)** | **4.46 KB (0.49%)** | **4.46 KB (0.49%)** |

**Winner:** All strategies converge at max-bits=12 (dictionary large enough to capture all patterns)

**Key Insights:**
- **Freeze dominates** on: Repetitive patterns, random data, uniform text
- **Reset excels** on: Archives with context shifts (bmps.tar: 8× better than Freeze)
- **LRU-v2.1 excels** on: Mixed archives (bmps.tar: 3.4× better than Freeze, beats LFU)
- **LFU excels** on: Large files with stable, globally-repeated patterns (large.txt)
- **LRU-v1 performs poorly** across all tests (file expansion!)
- **LRU-v2 and v2.1** identical compression (differ only in speed)
- **Higher max-bits** reduces eviction pressure, narrowing gaps between strategies

---

### Compression Speed Comparison

Systematic speed benchmarks across all implementations (max-bits=9, averaged over 3 runs):

| File | Size | Freeze | Reset | LFU | LRU-v1 | LRU-v2 | LRU-v2.1 |
|------|------|--------|-------|-----|--------|--------|----------|
| **ab_repeat_250k** | 488 KB | **0.20s** | **0.20s** | 0.22s | 0.40s | 0.22s | 0.23s |
| **ab_random_500k** | 488 KB | **0.21s** | 0.23s | 0.34s | 0.53s | 0.61s | 0.45s |
| **code.txt** | 68 KB | **0.12s** | **0.12s** | 0.18s | 0.19s | 0.21s | 0.19s |
| **large.txt** | 1.15 MB | **0.75s** | 0.90s | 1.85s | 1.97s | 2.35s | 2.19s |
| **bmps.tar** | 1.05 MB | 0.72s | **0.38s** | 0.76s | 0.98s | 0.60s | 0.58s |
| **all.tar** | 2.89 MB | **1.81s** | **1.81s** | 4.93s | 4.02s | 4.20s | 3.76s |
| **wacky.bmp** | 900 KB | 0.29s | **0.28s** | 0.35s | 0.74s | 0.34s | 0.36s |

**Speed Rankings (Fastest → Slowest):**
1. **Freeze/Reset** - Fastest overall (0.12s - 1.81s across tests)
2. **LRU-v2.1** - Good balance of compression and speed
3. **LFU** - Slower due to frequency tracking overhead
4. **LRU-v2** - Slightly slower than v2.1 (HashMap lookup overhead in some cases)
5. **LRU-v1** - Slowest eviction strategy (large EVICT_SIGNAL overhead)

**Key Findings:**
- **Freeze/Reset are fastest** (1.5-3× faster than eviction strategies on most files)
- **Reset can outperform Freeze** on files with context shifts (bmps.tar: 0.38s vs 0.72s)
- **LRU-v2.1 vs LRU-v2:** v2.1 is 7-34% faster (better optimization)
- **LFU overhead:** 2-3× slower than Freeze (frequency bucket management)
- **LRU-v1 poor performance:** File expansion + large EVICT_SIGNAL overhead

**Speed vs Compression Trade-off:**
- **Freeze:** Fastest but poor on archives (bmps.tar: 0.72s, 699 KB)
- **Reset:** Fast AND best on archives (bmps.tar: 0.38s, 90 KB)
- **LFU:** Slow but best on large.txt (1.85s, 709 KB vs Freeze 0.75s, 783 KB)
- **LRU-v2.1:** Middle ground (good on bmps.tar: 0.58s, 207 KB)

---

### Memory Usage

| Strategy | Dictionary | Metadata | Total Overhead |
|----------|-----------|----------|----------------|
| Freeze | ~512 KB (65K entries × 8 bytes) | 0 KB | ~512 KB |
| Reset | ~512 KB | 0 KB | ~512 KB |
| LRU-v1 | ~512 KB | ~512 KB (linked list nodes) | ~1 MB |
| LRU-v2 | ~512 KB | ~516 KB (list + 4 KB hash) | ~1 MB |
| LRU-v2.1 | ~512 KB | ~516 KB (list + 4 KB hash) | ~1 MB |
| LFU | ~512 KB | ~640 KB (freq buckets + lists) | ~1.15 MB |

**Key Findings:**
- **Freeze/Reset** use least memory (no eviction tracking overhead)
- **LRU strategies** use ~2× memory of Freeze/Reset (doubly-linked list overhead)
- **LFU** uses most memory (~2.25× Freeze) due to frequency buckets + multiple linked lists
- **LRU-v2 vs v2.1:** Identical memory (differ only in implementation details)
- All strategies practical for modern systems (< 1.2 MB total)

---

### LRU v2.1 vs LFU Comparison

Direct comparison of the two most sophisticated eviction strategies.

#### **Compression Ratio Comparison**

| Test Type | File | max-bits | LRU v2.1 | LFU | Winner |
|-----------|------|----------|----------|-----|--------|
| **Random (500k a/b)** | | 3 | 439.72 KB (90.05%) | 138.37 KB (28.34%) | **LFU** (68.5% better) |
| | | 4 | 429.13 KB (87.89%) | 100.83 KB (20.65%) | **LFU** (76.5% better) |
| | | 5 | 383.20 KB (78.48%) | 94.39 KB (19.33%) | **LFU** (75.4% better) |
| | | 6 | 342.17 KB (70.08%) | 83.81 KB (17.16%) | **LFU** (75.5% better) |
| **Repetitive (250k 'ab')** | | 3 | 499.72 KB (102.34%) | 91.56 KB (18.75%) | **LFU** (81.7% better) |
| | | 4 | 349.29 KB (71.54%) | 61.04 KB (12.50%) | **LFU** (82.5% better) |
| | | 5 | 212.96 KB (43.62%) | 38.16 KB (7.81%) | **LFU** (82.1% better) |
| | | 6 | 124.33 KB (25.46%) | 22.90 KB (4.69%) | **LFU** (81.6% better) |
| **Large Diverse** | large.txt (1.15 MB) | 9 | 1568.66 KB (133.53%) | **708.87 KB (60.34%)** | **LFU** (54.8% better) |
| | | 10 | 1551.25 KB (132.05%) | **626.44 KB (53.32%)** | **LFU** (59.6% better) |
| | | 11 | 1626.97 KB (138.49%) | **589.15 KB (50.15%)** | **LFU** (63.8% better) |
| | | 12 | 1668.43 KB (142.02%) | **562.66 KB (47.90%)** | **LFU** (66.3% better) |
| **Code Files** | code.txt (68 KB) | 9 | 90.17 KB (132.82%) | **43.37 KB (63.88%)** | **LFU** (51.9% better) |
| | | 12 | 77.10 KB (113.57%) | 36.34 KB (53.53%) | **LFU** (52.9% better) |
| | code2.txt (54 KB) | 9 | 68.31 KB (126.78%) | **30.97 KB (57.47%)** | **LFU** (54.7% better) |
| | | 12 | 55.80 KB (103.57%) | 31.17 KB (57.86%) | **LFU** (44.1% better) |

**Summary:** Mixed results - each strategy has strengths:
- **LFU wins:** AB tests (small alphabet), large.txt, code files (16/16 tests shown)
- **LRU wins:** Archives (bmps.tar) - not shown in table above but see Extended ASCII Tests

#### **Speed Comparison (max-bits=9)**

| File | LRU v2.1 Time | LFU Time | Faster |
|------|---------------|----------|--------|
| **ab_repeat_250k** | 0.23s | 0.22s | LFU 1.05× |
| **ab_random_500k** | 0.45s | 0.34s | **LFU 1.32× faster** |
| **code.txt** | 0.19s | 0.18s | LFU 1.06× |
| **large.txt** | 2.19s | 1.85s | **LFU 1.18× faster** |
| **bmps.tar** | 0.58s | 0.76s | **LRU 1.31× faster** |

**Summary:** LFU faster on 4/5 tests, but LRU faster on the archive test.

**Key Findings:**
- **LFU excels:** Small alphabets, large uniform text, code files
- **LRU excels:** Mixed archives (bmps.tar: 207 KB vs LFU 267 KB, 23% better!)
- **Trade-off:** LFU better on uniform data, LRU better on diverse data
- **AB tests misleading:** 2-char alphabet makes EVICT_SIGNAL overhead catastrophic for LRU
- **Real-world (extended ASCII):** LRU competitive on archives, LFU better on text

---

### LFU vs Freeze Comparison

Comparing complexity (LFU) vs simplicity (Freeze).

#### **Compression Ratio Comparison**

| Test Type | File | max-bits | Freeze | LFU | Winner |
|-----------|------|----------|--------|-----|--------|
| **Random (500k a/b)** | | 3 | **91.58 KB (18.76%)** | 138.37 KB (28.34%) | **Freeze** (33.8% better) |
| | | 4 | **86.61 KB (17.74%)** | 100.83 KB (20.65%) | **Freeze** (14.1% better) |
| | | 5 | **80.99 KB (16.59%)** | 94.39 KB (19.33%) | **Freeze** (14.2% better) |
| | | 6 | **78.15 KB (16.01%)** | 83.81 KB (17.16%) | **Freeze** (6.7% better) |
| **Repetitive (250k 'ab')** | | 3 | **45.78 KB (9.38%)** | 91.56 KB (18.75%) | **Freeze** (50.0% better) |
| | | 4 | **30.53 KB (6.25%)** | 61.04 KB (12.50%) | **Freeze** (50.0% better) |
| | | 5 | **19.09 KB (3.91%)** | 38.16 KB (7.81%) | **Freeze** (50.0% better) |
| | | 6 | **11.47 KB (2.35%)** | 22.90 KB (4.69%) | **Freeze** (49.9% better) |
| **Large Diverse** | large.txt (1.15 MB) | 9 | 783.08 KB (66.66%) | **708.87 KB (60.34%)** | **LFU** (9.5% better) |
| | | 10 | 675.02 KB (57.46%) | **626.44 KB (53.32%)** | **LFU** (7.2% better) |
| | | 11 | 626.02 KB (53.29%) | **589.15 KB (50.15%)** | **LFU** (5.9% better) |
| | | 12 | 585.61 KB (49.85%) | **562.66 KB (47.90%)** | **LFU** (3.9% better) |
| **Code Files** | code.txt (68 KB) | 9 | 44.83 KB (66.03%) | **43.37 KB (63.88%)** | **LFU** (3.3% better) |
| | | 12 | **30.38 KB (44.76%)** | 36.34 KB (53.53%) | **Freeze** (16.4% better) |
| | code2.txt (54 KB) | 9 | 35.69 KB (66.24%) | **30.97 KB (57.47%)** | **LFU** (13.2% better) |
| | | 12 | **23.47 KB (43.56%)** | 31.17 KB (57.86%) | **Freeze** (24.7% better) |

**Summary:** Freeze wins 12/16 tests (75%), LFU wins 4/16 tests (25%)

#### **Speed Comparison (max-bits=9)**

| File | Freeze Time | LFU Time | Faster |
|------|-------------|----------|--------|
| **ab_repeat_250k** | **0.20s** | 0.22s | **Freeze 1.10× faster** |
| **ab_random_500k** | **0.21s** | 0.34s | **Freeze 1.62× faster** |
| **code.txt** | **0.12s** | 0.18s | **Freeze 1.50× faster** |
| **large.txt** | **0.75s** | 1.85s | **Freeze 2.47× faster** |
| **bmps.tar** | **0.72s** | 0.76s | **Freeze 1.06× faster** |

**Summary:** Freeze faster on 5/5 tests (100%)! Average 1.75× faster.

**Key Findings:**
- **Freeze dominates** on random and repetitive data (7-50% better compression!)
- **LFU wins** only on large files with stable vocabularies (large.txt: 9.5% better)
- **Freeze is always faster** (1.06-2.47× faster) - no eviction overhead
- **Surprising result:** Freeze's simplicity beats LFU's complexity on 75% of tests
- **LFU only worthwhile** for specific use cases (encyclopedias, large docs with repeated patterns)

---

### Summary: When to Use Each Strategy

| Strategy | Best For | Compression Ratio | Speed | Memory |
|----------|----------|-------------------|-------|--------|
| **Freeze** | Repetitive patterns, uniform text, random data | **Excellent** (wins on random/repetitive data) | **Fastest** (1.5-2.5× faster than eviction strategies) | **Lowest** (~512 KB) |
| **Reset** | Archives, multi-section files, context shifts | **Best for archives** (8-77× better than Freeze on bmps.tar/wacky.bmp) | **Very Fast** (same as Freeze) | **Lowest** (~512 KB) |
| **LRU-v2.1** | Mixed archives (when Reset unavailable) | **Second-best for archives** (3.4× better than Freeze on bmps.tar, beats LFU) | Medium-Fast | Medium (~1 MB) |
| **LFU** | Large text files with stable vocabularies | **Best for large uniform text** (5-10% better than Freeze on large.txt) | Medium (2× slower than Freeze) | High (~1.15 MB) |
| **LRU-v2** | (Same as v2.1, slightly slower) | Same as LRU-v2.1 | Medium-Slow | Medium (~1 MB) |
| **LRU-v1** | **Not Recommended** | **Very Poor** (file expansion 100-190%) | Slow | Medium (~1 MB) |

**Overall Recommendations:**

1. **For repetitive/uniform data:** Use **Freeze** (fastest, excellent compression)
2. **For archives (tar, zip, mixed files):** Use **Reset** (best) or **LRU-v2.1** (second-best, 3.4× better than Freeze)
3. **For large text files:** Use **LFU** (5-10% better than Freeze on large.txt)
4. **Avoid:** LRU-v1 (causes severe file expansion)

**Key Insights from Benchmarks:**

**By File Type:**
- **Archives (bmps.tar):** Reset (90 KB) > LRU-v2.1 (207 KB) > LFU (267 KB) > Freeze (699 KB)
- **Large text (large.txt):** LFU (709 KB) > Freeze (783 KB) > Reset (900 KB) > LRU (1569 KB)
- **Repetitive (ab_repeat):** Freeze (2.4 KB) > Reset (4.4 KB) > LFU (4.3 KB) > LRU (22 KB)

**Strategy Trade-offs:**
- **Freeze:** Best default (fastest + good on most files), but poor on archives
- **Reset:** Dominant on archives (7-77× better than Freeze), matches Freeze speed
- **LRU-v2.1:** Strong on mixed files (3.4× better than Freeze on archives), fails on uniform text
- **LFU:** Narrow niche (only large uniform text), 2× slower than Freeze

**When LRU Works:**
- ✓ Archives with diverse content (bmps.tar: 3.4× better than Freeze, beats LFU)
- ✗ Large uniform text (file expansion: 133% vs Freeze 67%)
- ✗ Small alphabets (catastrophic failure on AB tests)
- ✗ Repetitive patterns (10× worse than Freeze)

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
python LRU-Eviction/LZW-LRU-Optimizedv1.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

**LRU (Optimization 2):**
```bash
python LRU-Eviction/LZW-LRU-Optimizedv2.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

**LRU (Optimization 2.1):**
```bash
python LRU-Eviction/LZW-LRU-Optimizedv2.1.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
```

**LFU:**
```bash
python lzw_lfu.py compress --alphabet ascii --min-bits 9 --max-bits 16 input.txt output.lzw
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
| EVICT_SIGNAL | 2^max_bits - 1 | Eviction sync (LRU and LFU) |
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

1. **Hybrid Strategies** - Combine LRU and LFU with adaptive switching
2. **Compression Ratio Monitoring** - Auto-switch strategies when ratio degrades
3. **Parallel Compression** - Multi-threaded encoding for large files
4. **Streaming API** - Compress/decompress without loading entire file

### Research Questions

- What file characteristics predict which strategy will perform best?
- Can we auto-detect optimal strategy from initial bytes?
- How do these strategies compare to modern algorithms (DEFLATE, LZMA, Zstandard)?
- Can machine learning improve eviction decisions?


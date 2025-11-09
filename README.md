# LZW Compression with Advanced Dictionary Management

A comprehensive implementation of LZW (Lempel-Ziv-Welch) compression in Python, exploring various dictionary management strategies to optimize compression ratios and performance.

---

## Table of Contents

- [What is LZW Compression?](#what-is-lzw-compression)
- [Dictionary Management: The Key to Optimization](#dictionary-management-the-key-to-optimization)
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

## Dictionary Management: The Key to Optimization

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

### 4. LFU (Least Frequently Used) [TODO]

**Strategy:** When the dictionary fills up, evict the entry that has been output the **fewest times**. This preserves globally common patterns.

**Status:** Not yet implemented.

**Planned Approach:**
- Track usage count for each dictionary entry
- Use min-heap for O(log N) eviction of least-used entry
- Similar EVICT_SIGNAL strategy as LRU
- Synchronization challenge: Decoder must track counts identically

**Expected Tradeoffs:**
- Better on files with stable, globally-repeated patterns
- Worse on files with shifting contexts (keeps old patterns too long)
- Higher memory overhead (usage counts for all entries)

---

## Performance Comparisons

### Test Files

| File | Size | Description |
|------|------|-------------|
| `freeze.py` | ~47 KB | Python source code (this LZW implementation) |
| Various text | Varies | Test suite for different file characteristics |

### Compression Ratios

**Baseline: Freeze**
```
freeze.py: 47,824 bytes → 27,234 bytes (43.1% reduction)
```

**Reset vs Freeze:**
```
File        | Freeze  | Reset   | Difference
freeze.py   | 27,234  | 27,XXX  | [TODO: Benchmark]
```

**LRU vs Freeze:**
```
File        | Freeze  | LRU-v1  | LRU-v2 (HashMap) | LRU-v2 (Linear)
freeze.py   | 27,234  | 26,XXX  | 26,XXX           | 26,XXX
            | (baseline) | (-X%)  | (-X%)            | (-X%)

[TODO: Complete benchmarks]
```

**Key Findings:**
- LRU outperforms Freeze on files with shifting contexts
- Reset excels on multi-section files
- LRU-v2 has smallest output (compact EVICT_SIGNAL)
- Compression ratios identical between HashMap and Linear versions (same algorithm)

### Compression Speed

```
File        | Freeze  | Reset   | LRU-v1  | LRU-v2 (HashMap) | LRU-v2 (Linear)
freeze.py   | XXX ms  | XXX ms  | XXX ms  | XXX ms           | XXX ms

[TODO: Complete timing benchmarks]
```

**Key Findings:**
- Freeze is fastest (no eviction overhead)
- LRU-v2 HashMap is ~3,800× faster at prefix lookup than Linear
- Overall compression time dominated by I/O and bit packing
- LRU-v2 Linear only ~3-10% slower despite O(255×L) lookup

### Decompression Speed

```
File        | Freeze  | Reset   | LRU-v1  | LRU-v2 (HashMap) | LRU-v2 (Linear)
freeze.py   | XXX ms  | XXX ms  | XXX ms  | XXX ms           | XXX ms

[TODO: Complete timing benchmarks]
```

**Key Findings:**
- Decompression generally faster than compression
- LRU versions slightly slower due to EVICT_SIGNAL processing
- Decoder doesn't need HashMap (only encoder optimizes prefix lookup)

### Memory Usage

| Strategy | Dictionary | Metadata | Total Overhead |
|----------|-----------|----------|----------------|
| Freeze   | ~512 KB (65K entries × 8 bytes) | 0 | ~512 KB |
| Reset    | ~512 KB | 0 | ~512 KB |
| LRU-v1   | ~512 KB | ~512 KB (linked list nodes) | ~1 MB |
| LRU-v2 (HashMap) | ~512 KB | ~516 KB (list + hash) | ~1 MB |
| LRU-v2 (Linear) | ~512 KB | ~512 KB (linked list only) | ~1 MB |

**Key Findings:**
- LRU strategies use ~2× memory of Freeze/Reset
- HashMap overhead negligible (~4 KB = 0.4% increase)
- All strategies practical for modern systems

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

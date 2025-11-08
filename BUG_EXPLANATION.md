# LRU LZW Synchronization Bug - Complete Analysis

## Summary

The LRU eviction logic has a **fundamental synchronization problem** between encoder and decoder when codes are evicted and reused. This causes the decoder to produce incorrect output.

## The Bug

**Symptom:** With small dictionaries (forcing many evictions), the decompressed file is LARGER than the original and contains corrupted data.

**Root Cause:** When the encoder evicts code X and reuses it for a new entry, it can immediately output code X with the new value. But the decoder may still have code X with the OLD value, causing it to decode incorrectly.

## Detailed Explanation

### How the Bug Occurs

1. **Encoder** evicts code 6 ('abab') and reuses it for 'aba'
2. **Encoder** continues encoding and sees 'aba' → outputs code 6 (new value!)
3. **Decoder** hasn't evicted code 6 yet, still has code 6 = 'abab' (old value)  
4. **Decoder** reads code 6 → decodes as 'abab' instead of 'aba' ❌

### Why Standard LZW Doesn't Have This Problem

Standard LZW algorithms either:
- **Freeze** the dictionary when full (stop adding entries)
- **Reset** the dictionary when full (start over)
- **Never reuse codes** (just invalidate evicted entries)

With LRU eviction that **reuses codes immediately**, we break the synchronization invariant.

### The Synchronization Invariant

For LZW to work correctly:
> "When the encoder outputs code X, the decoder must have code X in its dictionary with the SAME value"

Standard LZW maintains this through:
- The special case: `if codeword == next_code` (handles codes not yet in decoder)
- Sequential code assignment (both encoder/decoder assign codes in same order)

But with code reuse:
- Encoder changes code X's meaning by evicting and reusing it
- Decoder doesn't know code X changed until it processes more entries
- The special case doesn't handle "code exists but with wrong value"

## Evidence

Test with `ab*40` (80 bytes) using max-bits=4 (16 codes):

**Encoder outputs:**
```
...code 6 for 'aba'... (after evicting 'abab' and reusing code 6)
Output FINAL code 9 for 'abab'
```

**Decoder reads:**
```
Read code 6 -> 'abab' (OLD value, not yet evicted!)
...later evicts code 6 and replaces with 'aba'
Read code 9 -> 'ababb' (WRONG!)
```

Result: Original=80 bytes, Decompressed=83 bytes ❌

## Why The Attempted Fix Partially Worked

I tried preventing the encoder from immediately using a code that was just evicted:

```python
just_added_phrase = None  # Track recently evicted/reused phrase
if combined in dictionary and combined != just_added_phrase:
    # Don't match phrases that were just added via eviction
```

This worked for "ab\*500" but failed for random data because:
- Simple patterns like "ababab..." only evict once per iteration
- Random data evicts more chaotically, sometimes evicting the same code multiple times
- The fix only prevents IMMEDIATE reuse (one iteration), not subsequent reuses

## Possible Solutions

### 1. Freeze Dictionary (Easiest)
Stop adding entries when dictionary is full. Not what user requested.

### 2. Reset Dictionary
Clear and restart when full. Loses compression efficiency.

### 3. Delayed Code Reuse
After evicting code X, mark it "invalid" for N iterations before reusing.
- Problem: How to synchronize N between encoder/decoder?

### 4. Explicit Eviction Signaling
Encoder sends special signals when codes are evicted.
- Problem: Increases compressed size, defeats purpose of compression

### 5. Different LRU Strategy
Track which codes CAN'T be evicted (recently used in encoding).
- Requires careful design to keep encoder/decoder synchronized

### 6. Two-Phase Eviction
- Phase 1: Mark code as "pending eviction" (encoder can't use it)
- Phase 2: Actually reuse the code after decoder catches up
- Problem: How does encoder know when decoder caught up?

## Recommendation

The fundamental issue is that **immediate code reuse breaks LZW's synchronization model**. Any solution requires either:

1. **Don't reuse codes** (mark as None/invalid instead)
2. **Add synchronization overhead** (signals, delays, etc.)
3. **Use a different eviction strategy** that doesn't reuse codes immediately

For a clean LRU implementation, option #1 (invalidate but don't reuse) may be simplest, though it doesn't reclaim the code space.

## Test Commands

```bash
# Test that shows the bug (small dictionary forces evictions)
python3 -c "print('ab' * 40, end='')" > test.txt
python3 lzw_lru.py compress test.txt test.lzw --alphabet ab --min-bits 3 --max-bits 4
python3 lzw_lru.py decompress test.lzw test_out.txt
diff test.txt test_out.txt  # Files differ!
```

## Current Implementation Status

- ✅ LRU tracker works correctly (O(1) operations with doubly-linked list + hashtable)
- ✅ Evictions happen in correct order
- ✅ Dictionary entries are tracked properly (alphabet excluded)
- ❌ **Encoder/decoder desynchronization when codes are reused**

The implementation is algorithmically correct for the LRU tracking, but the fundamental approach of reusing codes immediately is incompatible with LZW's decoding model.

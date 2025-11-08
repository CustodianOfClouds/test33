# LRU LZW Naive Implementation - Misalignment Analysis

## Summary

The naive LRU implementation (without EVICT_SIGNAL) causes misalignment between encoder and decoder when the encoder **evicts a code and immediately uses the newly added entry at that code position**.

## The Problem

### Encoder Behavior (Output #35)
```
1. Dictionary is FULL
2. Evicts code=6 which contains 'abab' (LRU entry)
3. Adds NEW entry at code=6: 'aba'
4. Immediately outputs code=6 (expecting it to decode as 'aba')
```

### Decoder Behavior (Input #35)
```
1. Receives code=6
2. At this point, code=6 STILL contains 'abab' (OLD value)
3. Outputs 'abab' (INCORRECT - should be 'aba')
4. THEN evicts code=6 and adds 'aba' at code=6
```

## Root Cause

**Timing mismatch:**
- **Encoder**: Updates dictionary entry BEFORE sending the code
- **Decoder**: Uses the code FIRST (with old value), THEN updates dictionary

The decoder is always "one step behind" - it reads a code with the OLD value before updating its dictionary to match the encoder's NEW value.

## Detailed Example (Output/Input #35)

### Encoder Log:
```
[ENC #34] OUTPUT code=5 for 'ab' (5 bits)
[ENC] Updated LRU: 'ab' is now MRU

[ENC] *** DICTIONARY FULL ***
[ENC] EVICTING code=6 -> 'abab' (LRU entry)
[ENC] ADDING code=6 -> 'aba' (reusing evicted code)
[ENC] LRU order after eviction: [...'ba', 'ab', 'aba']

[ENC #35] OUTPUT code=6 for 'aba' (5 bits)
                              ^^^
                        NEW value at code 6
```

### Decoder Log:
```
[DEC #35] READ code=6 -> 'abab' (5 bits)
                         ^^^^
                    OLD value still at code 6!

[DEC] *** DICTIONARY FULL ***
[DEC] EVICTING code=6 -> 'abab' (LRU entry)
[DEC] ADDING code=6 -> 'aba' (reusing evicted code)
[DEC] Updated LRU: code 6 is now MRU

[DEC #36] READ code=7 -> 'ba' (5 bits)
```

**Result:** Decoder outputs 'abab' (4 chars) instead of 'aba' (3 chars) → 1 extra character

## Frequency of Misalignment

Found **10 instances** where encoder evicts and immediately uses the same code:

| Output # | Code | Evicted Entry | New Entry |
|----------|------|---------------|-----------|
| #35      | 6    | 'abab'        | 'aba'     |
| #37      | 8    | 'baba'        | 'bab'     |
| #39      | 10   | (varies)      | (varies)  |
| #41      | 12   | (varies)      | (varies)  |
| #43      | 14   | (varies)      | (varies)  |
| #45      | 16   | (varies)      | (varies)  |
| #47      | 18   | (varies)      | (varies)  |
| #49      | 20   | (varies)      | (varies)  |
| #51      | 22   | (varies)      | (varies)  |
| #53      | 24   | (varies)      | (varies)  |

## Impact

- **Original file size:** 400 bytes
- **Decoded file size:** 419 bytes (+19 bytes)
- **Error accumulation:** Each misalignment adds extra characters, corrupting the output

## Why Does This Happen?

In standard LZW, this timing issue doesn't occur because:
1. Codes are only added sequentially (never reused)
2. Both encoder and decoder add the same new entry at the same time
3. The decoder can use the "special case" logic (codeword == next_code) to handle edge cases

But with LRU eviction:
1. Codes are **reused** after eviction
2. The encoder can immediately output a reused code
3. The decoder hasn't updated that code yet, so it decodes the OLD value
4. The "special case" logic doesn't help because codeword != next_code

## Solution

The current lzw_lru.py implementation solves this by:

1. Sending **EVICT_SIGNAL** when eviction occurs
2. Including the complete information about the new entry:
   - `[EVICT_SIGNAL] [code] [entry_length] [char1...charN]`
3. Decoder processes EVICT_SIGNAL before using the code
4. This ensures decoder's dictionary matches encoder's dictionary at all times

## How to Reproduce

```bash
# Create test input
python3 -c "print('ab' * 200, end='')" > test_input.txt

# Compress with naive LRU
python3 lzw_lru_naive.py compress test_input.txt test_output.lzw \
    --alphabet ab --min-bits 3 --max-bits 5 --debug 2> compress_debug.log

# Decompress with naive LRU
python3 lzw_lru_naive.py decompress test_output.lzw test_decoded.txt \
    --debug 2> decompress_debug.log

# Compare
diff test_input.txt test_decoded.txt
# Shows corruption at multiple points
```

## Next Steps

To minimize overhead while maintaining correctness:
- Only send EVICT_SIGNAL when the evicted code will be used immediately
- Detect this pattern: encoder adds entry E at code C, then immediately outputs code C
- Otherwise, let decoder mirror encoder's LRU logic (as in naive implementation)

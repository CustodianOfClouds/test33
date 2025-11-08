# LRU LZW Synchronization Issue

## The Problem

The encoder and decoder get out of sync when codes are evicted and reused.

### Encoder Sequence:
1. Output code X for phrase P
2. Try to add new entry (P + next_char)
3. Dictionary full → Evict LRU → Reuse code Y for new entry
4. Continue encoding
5. Later see the new entry again → Output code Y (new value)

### Decoder Sequence:
1. Read code X → decode to P
2. Try to add new entry (prev + P[0])  
3. Dictionary full → Evict LRU → Reuse code Z for new entry
4. Read code Y → decode using CURRENT dictionary (may have old value!)

## Root Cause

When the encoder evicts code Y and reuses it for a new entry, it can immediately output code Y with the new value. But the decoder may not have evicted code Y yet, so it decodes Y as the old value.

The encoder and decoder evict at different times:
- **Encoder**: Evicts when adding entry AFTER outputting a code
- **Decoder**: Evicts when adding entry AFTER reading a code

This creates a timing mismatch when the same code is evicted and reused multiple times.

## Potential Solutions

1. **Don't allow immediate reuse**: After evicting a code, don't use it in the same "round"
2. **Synchronize eviction timing**: Make encoder/decoder evict at exactly the same point
3. **Use different eviction strategy**: Instead of LRU, use a strategy that doesn't reuse codes immediately
4. **Track eviction state**: The encoder could signal which codes have been evicted

The standard LZW algorithm doesn't have this issue because codes are never reused - the dictionary just stops growing when full.

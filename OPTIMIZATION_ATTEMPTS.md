# LRU LZW Optimization Attempts

## Goal

Reduce the overhead of EVICT_SIGNAL by only sending it when absolutely necessary (when encoder evicts code C and immediately uses C in the same step).

## Findings from Naive Implementation

From `MISALIGNMENT_ANALYSIS.md`:
- **10 primary misalignments** where encoder evicts and immediately uses the same code
- **9 cascade misalignments** due to dictionary divergence
- Total corruption: 19 out of 54 steps (35.2%)
- **Optimization potential**: Only 10 signals needed instead of ~30 evictions

## Attempted Optimization (lzw_lru_optimized.py)

### Encoder Strategy
- Track recently evicted code
- When about to output a code, check if it matches recently_evicted_code
- If yes, send EVICT_SIGNAL before outputting
- Otherwise, output normally

### Decoder Strategy  
- Defer dictionary additions until after reading next code
- If next code is EVICT_SIGNAL, process it (this handles the addition)
- Otherwise, do the pending addition locally (mirror encoder's LRU)

### Results
- ✓ Works correctly with max-bits=3 (dict size 8)
- ✗ Breaks with max-bits=4+ (invalid codeword errors)
- File size reduction: 176 bytes vs 335 bytes (47% smaller!)
  
### Issues Identified
1. **Bit-width transition handling**: Deferred additions cause next_code desync during bit-width increments
2. **Complex synchronization**: Encoder and decoder must maintain identical dictionary state at all times
3. **Pending addition timing**: Hard to know when to process pending additions vs wait for signals

## Conclusion

The optimization IS possible and DOES reduce overhead significantly, but requires careful handling of:
1. Bit-width transitions
2. Dictionary addition timing
3. next_code synchronization between encoder/decoder

The naive implementation clearly demonstrates that the evict-then-use pattern is the root cause of ALL misalignments, confirming the optimization strategy is sound. The implementation challenges are solvable but require more careful state management.

## Next Steps

To successfully implement this optimization:
1. Ensure next_code stays synchronized between encoder/decoder
2. Handle bit-width increments correctly with deferred additions
3. Or: Use a different approach (e.g., encoder buffering, different signal format)

# EVICT_SIGNAL Implementation Plan (Revised)

## Approach: Signal at Eviction Time

When the encoder evicts a code, immediately send:
1. EVICT_SIGNAL (tells decoder to evict)
2. The code number being evicted

This keeps encoder/decoder perfectly synchronized.

## Encoder Logic

```python
# When dictionary is full:
lru_entry = find_lru()
evicted_code = dictionary[lru_entry]

# Send eviction signal
writer.write(EVICT_SIGNAL, code_bits)
writer.write(evicted_code, code_bits)  # Tell decoder which code

# Evict and reuse
del dictionary[lru_entry]
dictionary[combined] = evicted_code
```

## Decoder Logic

```python
# When reading codeword:
if codeword == EVICT_SIGNAL:
    # Read which code to evict
    code_to_evict = reader.read(code_bits)
    
    # Evict it
    # Find the phrase with this code
    for phrase, code in dictionary.items():
        if code == code_to_evict:
            del dictionary[phrase]
            break
    
    # Continue normal processing
```

## Bit Overhead

- 2 codewords per eviction (EVICT_SIGNAL + code number)
- Only happens when dictionary is full
- Small dictionaries: more overhead
- Large dictionaries: minimal overhead

## Testing Plan

1. Test ab*40 with max_bits=4 (triggers evictions)
2. Test random data
3. Test with .doc/.exe files

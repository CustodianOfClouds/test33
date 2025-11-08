# LRU Order Issue

## Encoder Order (lines 343-409)

```python
# 1. Output code for current phrase
writer.write(code_to_write, code_bits)

# 2. Update LRU for current phrase (the one we just output)
if lru_tracker.contains(current):
    lru_tracker.use(current)

# 3. Add new entry to dictionary
dictionary[combined] = next_code
lru_tracker.use(combined)  # Mark new entry as MRU
next_code += 1
```

**LRU Order after this: ... -> current -> combined (newest)**

## Decoder Order (lines 596-653)

```python
# 1. Decode codeword
current = dictionary[codeword]

# 2. Write decoded string
out.write(current.encode('latin-1'))

# 3. Add new entry to dictionary
new_entry = prev + current[0]
dictionary[next_code] = new_entry
lru_tracker.use(next_code)  # Mark new entry as MRU
next_code += 1

# 4. Update LRU for codeword (the one we just decoded)
if codeword >= alphabet_size + 2:
    lru_tracker.use(codeword)  # THIS IS TOO LATE!
```

**LRU Order after this: ... -> new_entry -> codeword (newest)**

## The Problem

The encoder makes the OUTPUT code MRU **BEFORE** adding the new entry.
The decoder makes the DECODED code MRU **AFTER** adding the new entry.

This causes the LRU queues to diverge!

## The Fix

Move the decoder's LRU update for codeword to BEFORE the new entry addition,
matching the encoder's order.

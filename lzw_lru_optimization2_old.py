#!/usr/bin/env python3
"""
LZW Compression Tool (Optimization 2 with O(L) Linear Search)

Same algorithm as lzw_lru_optimization2.py but uses LINEAR SEARCH instead of HashMap.
This version is for BENCHMARKING to measure the value of O(1) HashMap optimization.

Key Difference from O(1) version:
- O(1): Uses HashMap for instant prefix lookup
- This (O(L)): Linear search through 255-entry buffer
- Performance: O(1) is ~3-10% faster overall, same compression ratio

Why Keep This Version:
- Demonstrates tradeoff: 4KB memory vs O(255*L) time complexity
- Useful for embedded systems with tight memory constraints
- Proves O(1) optimization is worthwhile but not critical

Algorithm identical to optimization2.py except prefix lookup method.

Usage:
    Compress:   python3 lzw_lru_optimization2_old.py compress input.txt output.lzw --alphabet ascii
    Decompress: python3 lzw_lru_optimization2_old.py decompress input.lzw output.txt
"""


import sys
import argparse
from typing import TypeVar, Generic, Optional, Dict

# Predefined alphabets
ALPHABETS = {
    'ascii': [chr(i) for i in range(128)],
    'extendedascii': [chr(i) for i in range(256)],
    'ab': ['a', 'b']
}

# Global debug flag

# ============================================================================
# BIT-LEVEL I/O CLASSES
# ============================================================================

class BitWriter:
    """Writes variable-width integers as a stream of bits to a binary file."""

    def __init__(self, filename):
        self.file = open(filename, 'wb')
        self.buffer = 0
        self.n_bits = 0

    def write(self, value, num_bits):
        """Write 'num_bits' bits from 'value' to output."""
        self.buffer = (self.buffer << num_bits) | value
        self.n_bits += num_bits

        while self.n_bits >= 8:
            self.n_bits -= 8
            byte = self.buffer >> self.n_bits
            self.file.write(bytes([byte]))
            self.buffer &= (1 << self.n_bits) - 1

    def close(self):
        """Flush any remaining bits and close file."""
        if self.n_bits > 0:
            byte = self.buffer << (8 - self.n_bits)
            self.file.write(bytes([byte]))
        self.file.close()

class BitReader:
    """Reads variable-width integers from a stream of bits in a binary file."""

    def __init__(self, filename):
        self.file = open(filename, 'rb')
        self.buffer = 0
        self.n_bits = 0

    def read(self, num_bits):
        """Read 'num_bits' bits from input. Returns None at EOF."""
        while self.n_bits < num_bits:
            byte_data = self.file.read(1)
            if not byte_data:
                return None
            self.buffer = (self.buffer << 8) | byte_data[0]
            self.n_bits += 8

        self.n_bits -= num_bits
        value = self.buffer >> self.n_bits
        self.buffer &= (1 << self.n_bits) - 1
        return value

    def close(self):
        """Close the input file."""
        self.file.close()

# ============================================================================
# LRU TRACKER DATA STRUCTURE
# ============================================================================

K = TypeVar('K')

class LRUTracker(Generic[K]):
    """O(1) LRU tracker using doubly-linked list + HashMap."""
    __slots__ = ('map', 'head', 'tail')

    class Node:
        __slots__ = ('key', 'prev', 'next')

        def __init__(self, key: Optional[K]) -> None:
            self.key: Optional[K] = key
            self.prev: Optional['LRUTracker.Node'] = None
            self.next: Optional['LRUTracker.Node'] = None

    def __init__(self) -> None:
        self.map: Dict[K, 'LRUTracker.Node'] = {}
        self.head: LRUTracker.Node = self.Node(None)
        self.tail: LRUTracker.Node = self.Node(None)
        self.head.next = self.tail
        self.tail.prev = self.head

    def use(self, key: K) -> None:
        """Mark key as recently used. Adds key if not present."""
        node = self.map.get(key)
        if node is not None:
            self._remove_node(node)
            self._add_to_front(node)
        else:
            node = self.Node(key)
            self.map[key] = node
            self._add_to_front(node)

    def find_lru(self) -> Optional[K]:
        """Return least recently used key, or None if empty."""
        if self.tail.prev == self.head:
            return None
        return self.tail.prev.key

    def remove(self, key: K) -> None:
        """Remove key from tracking."""
        node = self.map.pop(key, None)
        if node is not None:
            self._remove_node(node)

    def contains(self, key: K) -> bool:
        """Check if key is being tracked."""
        return key in self.map

    def _add_to_front(self, node: 'LRUTracker.Node') -> None:
        """Add node after head (most recently used position)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node  # type: ignore
        self.head.next = node

    def _remove_node(self, node: 'LRUTracker.Node') -> None:
        """Remove node from list (maintains links)."""
        node.prev.next = node.next  # type: ignore
        node.next.prev = node.prev  # type: ignore

# ============================================================================
# LZW COMPRESSION WITH OPTIMIZATION 2
# ============================================================================

def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    """
    Compress a file using LZW with OPTIMIZATION 2: Minimal EVICT_SIGNAL.

    EVICT_SIGNAL no longer includes dictionary entry bytes - decoder reconstructs!
    """
    alphabet = ALPHABETS[alphabet_name]
    valid_chars = set(alphabet)

    # Write file header
    writer = BitWriter(output_file)
    writer.write(min_bits, 8)
    writer.write(max_bits, 8)
    writer.write(len(alphabet), 16)
    for char in alphabet:
        writer.write(ord(char), 8)

    # Initialize dictionary
    dictionary = {char: i for i, char in enumerate(alphabet)}

    EOF_CODE = len(alphabet)
    next_code = len(alphabet) + 1
    max_size = 1 << max_bits
    EVICT_SIGNAL = max_size - 1

    # Variable-width encoding
    code_bits = min_bits
    threshold = 1 << code_bits

    # LRU tracker for dictionary entries (NOT alphabet entries)
    lru_tracker = LRUTracker()

    # Track evicted codes and their new values
    # evicted_codes[code] = (full_entry, prefix_at_eviction_time)
    evicted_codes = {}

    # OPTIMIZATION 2 (OLD): Output history with O(255*L) linear search
    # Circular buffer of last 255 outputs (8-bit offset limit)
    # Uses linear search O(255*L) instead of HashMap O(1)
    # Minimal memory overhead vs 4KB for HashMap version
    OUTPUT_HISTORY_SIZE = 255
    output_history = []           # Circular buffer of recent outputs



    # Read and compress file byte by byte (streaming for memory efficiency)
    with open(input_file, 'rb') as f:
        # Read first byte
        first_byte = f.read(1)

        # Empty file
        if not first_byte:
            writer.write(EOF_CODE, min_bits)
            writer.close()
            return

        # Convert byte to character for dictionary matching
        first_char = chr(first_byte[0])

        # Validate first character is in alphabet
        if first_char not in valid_chars:
            raise ValueError(f"Byte value {first_byte[0]} at position 0 not in alphabet")

        current = first_char  # Current phrase being matched
        pos = 1  # Track position for better error messages

        # Main LZW compression loop
        while True:
            byte_data = f.read(1)  # Read next byte
            if not byte_data:          # End of input
                break

            # Convert byte to character
            char = chr(byte_data[0])

            # Validate character
            if char not in valid_chars:
                raise ValueError(f"Byte value {byte_data[0]} at position {pos} not in alphabet")
            pos += 1

            combined = current + char  # Try extending current phrase

            if combined in dictionary:
                # Phrase exists in dictionary - keep extending
                current = combined
            else:
                # Phrase not in dictionary - output code and add new entry
                output_code = dictionary[current]

                # OPTIMIZATION 2 (OLD): Check if this code was evicted and is being reused
                if output_code in evicted_codes:
                    # Unpack stored entry and prefix
                    entry, prefix = evicted_codes[output_code]

                    # Compute suffix (character that extends prefix to entry)
                    suffix = entry[len(prefix):]
                    if len(suffix) != 1:
                        raise ValueError(f"Logic error: suffix should be 1 char, got {len(suffix)}")

                    # LINEAR SEARCH (O(255*L)) through output history
                    # Search backwards for most recent occurrence of prefix
                    offset = None
                    for i in range(len(output_history) - 1, -1, -1):
                        if output_history[i] == prefix:  # O(L) string comparison
                            offset = len(output_history) - i
                            break

                    if offset is not None and offset <= 255:
                        # Send compact EVICT_SIGNAL: [EVICT_SIGNAL][code][offset][suffix]
                        writer.write(EVICT_SIGNAL, code_bits)
                        writer.write(output_code, code_bits)
                        writer.write(offset, 8)       # 1 byte offset
                        writer.write(ord(suffix), 8)  # 1 byte suffix
                    else:
                        # Fallback: send full entry (prefix not in recent history)
                        # Format: [EVICT_SIGNAL][code][0][entry_length][char1]...[charN]
                        writer.write(EVICT_SIGNAL, code_bits)
                        writer.write(output_code, code_bits)
                        writer.write(0, 8)            # offset=0 signals "full entry follows"
                        writer.write(len(entry), 16)
                        for c in entry:
                            writer.write(ord(c), 8)

                    # Remove from evicted_codes - decoder is now synchronized
                    del evicted_codes[output_code]

                # Output code for current phrase
                writer.write(output_code, code_bits)

                # Add current output to history
                output_history.append(current)
                if len(output_history) > OUTPUT_HISTORY_SIZE:
                    output_history.pop(0)  # Remove oldest from buffer

                # Update LRU for current phrase (if it's a dictionary entry, not alphabet)
                if lru_tracker.contains(current):
                    lru_tracker.use(current)

                # Add new entry to dictionary (or evict LRU if full)
                if next_code < EVICT_SIGNAL:
                    # Dictionary not full yet - add normally

                    # Check if we need to increase bit width
                    if next_code >= threshold and code_bits < max_bits:
                        code_bits += 1
                        threshold <<= 1

                    # Add new phrase to dictionary
                    dictionary[combined] = next_code
                    lru_tracker.use(combined)
                    next_code += 1
                else:
                    # Dictionary FULL - evict LRU entry and reuse its code
                    lru_entry = lru_tracker.find_lru()
                    if lru_entry is not None:
                        lru_code = dictionary[lru_entry]

                        # Remove old entry from dictionary and LRU tracker
                        del dictionary[lru_entry]
                        lru_tracker.remove(lru_entry)

                        # Add new entry at evicted code position
                        dictionary[combined] = lru_code
                        lru_tracker.use(combined)

                        # Track eviction with both full entry and prefix
                        # Prefix is needed to compute offset+suffix encoding
                        evicted_codes[lru_code] = (combined, current)

                # Start new phrase with current character
                current = char

    # Write final phrase
    final_code = dictionary[current]

    # Check if final code was evicted
    if final_code in evicted_codes:
        entry, prefix = evicted_codes[final_code]
        suffix = entry[len(prefix):]

        # LINEAR SEARCH through output history
        offset = None
        for i in range(len(output_history) - 1, -1, -1):
            if output_history[i] == prefix:
                offset = len(output_history) - i
                break

        if offset is not None and offset <= 255:
            # Send compact EVICT_SIGNAL
            writer.write(EVICT_SIGNAL, code_bits)
            writer.write(final_code, code_bits)
            writer.write(offset, 8)
            writer.write(ord(suffix), 8)
        else:
            # Fallback: send full entry
            writer.write(EVICT_SIGNAL, code_bits)
            writer.write(final_code, code_bits)
            writer.write(0, 8)
            writer.write(len(entry), 16)
            for c in entry:
                writer.write(ord(c), 8)

        del evicted_codes[final_code]

    writer.write(final_code, code_bits)

    # Add final output to history
    output_history.append(current)

    # Update LRU for final phrase
    if lru_tracker.contains(current):
        lru_tracker.use(current)

    # Check if decoder will increment bit width before reading EOF
    # Decoder increments after reading final phrase, so EOF needs correct bit width
    if next_code >= threshold and code_bits < max_bits:
        code_bits += 1

    # Write EOF marker
    writer.write(EOF_CODE, code_bits)
    writer.close()

    print(f"Compressed: {input_file} -> {output_file}")

# ============================================================================
# LZW DECOMPRESSION WITH OPTIMIZATION 2
# ============================================================================

def decompress(input_file, output_file):
    """
    Decompress a file using OPTIMIZATION 2 (OLD - linear search version).

    Uses output history to reconstruct entries from offset+suffix encoding.
    """
    reader = BitReader(input_file)

    # Read file header
    min_bits = reader.read(8)
    max_bits = reader.read(8)
    alphabet_size = reader.read(16)
    alphabet = [chr(reader.read(8)) for _ in range(alphabet_size)]

    # Initialize dictionary with alphabet
    # Example: {0: 'a', 1: 'b'} for alphabet ['a', 'b']
    dictionary = {i: char for i, char in enumerate(alphabet)}

    # Reserve codes (same as encoder)
    EOF_CODE = alphabet_size
    next_code = alphabet_size + 1
    max_size = 1 << max_bits
    EVICT_SIGNAL = max_size - 1

    # Variable-width decoding parameters
    code_bits = min_bits
    threshold = 1 << code_bits

    # LRU tracker for dictionary entries (NOT alphabet entries)
    # Mirrors encoder's LRU tracker to stay synchronized
    lru_tracker = LRUTracker()

    # OPTIMIZATION 2 (OLD): Output history for offset-based reconstruction
    # Decoder uses direct indexing: output_history[-offset] which is O(1)
    # No need for HashMap (encoder needs linear search for reverse lookup)
    OUTPUT_HISTORY_SIZE = 255
    output_history = []

    # Flag to skip dictionary addition after EVICT_SIGNAL
    # When EVICT_SIGNAL received, encoder already added entry via eviction
    # Decoder shouldn't add another entry on next iteration
    skip_next_addition = False

    # Read first codeword
    codeword = reader.read(code_bits)

    if codeword is None:
        raise ValueError("Corrupted file: unexpected end of file")

    # Empty file case
    if codeword == EOF_CODE:
        reader.close()
        open(output_file, 'wb').close()
        return

    # Decode and output first codeword
    prev = dictionary[codeword]

    with open(output_file, 'wb') as out:
        out.write(prev.encode('latin-1'))

        # Add first output to history
        output_history.append(prev)

        # Main decompression loop
        while True:
            # Check if we need to increase bit width
            # Happens when next_code reaches threshold (512, 1024, etc.)
            if next_code >= threshold and code_bits < max_bits:
                code_bits += 1
                threshold <<= 1

            # Read next codeword
            codeword = reader.read(code_bits)

            if codeword is None:
                raise ValueError("Corrupted file: unexpected end of file")

            if codeword == EOF_CODE:
                break

            # Handle EVICT_SIGNAL (evict-then-use pattern detected by encoder)
            if codeword == EVICT_SIGNAL:
                # Read eviction information
                evicted_code = reader.read(code_bits)
                offset = reader.read(8)

                if offset > 0:
                    # OPTIMIZATION 2: Reconstruct from offset+suffix
                    suffix_byte = reader.read(8)
                    suffix = chr(suffix_byte)

                    # Look back in output history
                    if offset > len(output_history):
                        raise ValueError(f"Invalid offset {offset}, history size {len(output_history)}")

                    prefix = output_history[-offset]
                    new_entry = prefix + suffix
                else:
                    # Fallback: full entry provided (prefix not in recent history)
                    entry_length = reader.read(16)
                    new_entry = ''.join(chr(reader.read(8)) for _ in range(entry_length))

                # Remove old entry from LRU tracker (if it's a dictionary entry)
                if evicted_code in dictionary and evicted_code >= alphabet_size + 1:
                    lru_tracker.remove(evicted_code)

                # Add new entry at the evicted code position
                dictionary[evicted_code] = new_entry
                lru_tracker.use(evicted_code)

                # Skip dictionary addition on next iteration
                # Encoder already added an entry when it evicted
                skip_next_addition = True

                # Continue to next codeword (don't output, don't update prev)
                continue

            # Decode codeword to string
            if codeword in dictionary:
                current = dictionary[codeword]
            elif codeword == next_code:
                # Special LZW case: codeword not in dictionary yet
                # Happens when pattern is: ...AB + ABA where AB just got added
                current = prev + prev[0]
            else:
                raise ValueError(f"Invalid codeword: {codeword}")

            # Output decoded string
            out.write(current.encode('latin-1'))

            # Add to output history (circular buffer)
            output_history.append(current)
            if len(output_history) > OUTPUT_HISTORY_SIZE:
                output_history.pop(0)

            # Add new entry to dictionary (mirror encoder's logic)
            # Skip if previous iteration received EVICT_SIGNAL
            if not skip_next_addition:
                new_entry = prev + current[0]

                if next_code < EVICT_SIGNAL:
                    # Dictionary not full yet - add normally
                    dictionary[next_code] = new_entry
                    lru_tracker.use(next_code)
                    next_code += 1
                else:
                    # Dictionary FULL - mirror encoder's LRU eviction
                    lru_code = lru_tracker.find_lru()
                    if lru_code is not None:
                        # Remove old entry from dictionary and tracker
                        del dictionary[lru_code]
                        lru_tracker.remove(lru_code)

                        # Add new entry at evicted code position
                        dictionary[lru_code] = new_entry
                        lru_tracker.use(lru_code)

            # Reset skip flag
            skip_next_addition = False

            # Update LRU for the codeword we just used (if it's a dictionary entry)
            if codeword >= alphabet_size + 1 and codeword < EVICT_SIGNAL:
                if codeword in dictionary:
                    lru_tracker.use(codeword)

            # Update prev for next iteration
            prev = current

    reader.close()

    print(f"Decompressed: {input_file} -> {output_file}")

# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    """Parse command-line arguments and run compression or decompression."""

    parser = argparse.ArgumentParser(description='LZW compression (optimization 2: minimal EVICT_SIGNAL)')
    sub = parser.add_subparsers(dest='mode', required=True)

    # Compress subcommand
    c = sub.add_parser('compress')
    c.add_argument('input')
    c.add_argument('output')
    c.add_argument('--alphabet', required=True, choices=list(ALPHABETS.keys()))
    c.add_argument('--min-bits', type=int, default=9)
    c.add_argument('--max-bits', type=int, default=16)

    # Decompress subcommand
    d = sub.add_parser('decompress')
    d.add_argument('input')
    d.add_argument('output')

    args = parser.parse_args()

    try:
        if args.mode == 'compress':
            compress(args.input, args.output, args.alphabet, args.min_bits, args.max_bits)
        else:
            decompress(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        sys.exit(1)

if __name__ == '__main__':
    main()

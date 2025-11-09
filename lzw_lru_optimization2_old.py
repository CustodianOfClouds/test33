#!/usr/bin/env python3
"""
LZW Compression Tool (Optimization 2: Output History + Offset)

Optimization: EVICT_SIGNAL references recent output history!

Both encoder/decoder maintain circular buffer of recent outputs.
When EVICT_SIGNAL needed, encoder sends offset to prefix in history + suffix.

EVICT_SIGNAL format reduced from:
  [EVICT_SIGNAL][code][entry_length][char1]...[charN][code_again]
to:
  [EVICT_SIGNAL][code][offset_back][suffix_char][code_again]

Example: For entry "bababab" with prefix "bababa" that was 3 outputs ago:
  Old: 9 + 9 + 16 + 56 + 9 = 99 bits
  New: 9 + 9 + 8 + 8 + 9 = 43 bits
  Savings: 57% per signal!

Usage:
    Compress:   python3 lzw_lru_optimization2.py compress input.txt output.lzw --alphabet ascii
    Decompress: python3 lzw_lru_optimization2.py decompress input.lzw output.txt --debug
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
DEBUG = False

def debug_print(*args, **kwargs):
    """Print debug messages if DEBUG is enabled."""
    if DEBUG:
        print(*args, **kwargs, file=sys.stderr)

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

    # Track ALL evicted codes and their new values (since dict became full)
    # evicted_codes[code] = (full_entry, prefix_at_eviction_time)
    evicted_codes = {}

    # OPTIMIZATION 2 (OLD VERSION): Maintain circular buffer with LINEAR SEARCH
    # Max 255 entries (8-bit offset), stores recent output strings
    #
    # This is the O(255 × L) version - linear search through output history
    # Used for benchmarking comparison with O(1) HashMap version
    #
    # PERFORMANCE:
    #   Complexity: O(255 × L) per EVICT_SIGNAL where L = avg string length
    #   For 1MB file: ~5000 EVICT_SIGNALs × 255 comparisons × 15 chars = ~19M operations
    #
    # Memory: Minimal overhead (only the 255-entry circular buffer, no HashMap)
    OUTPUT_HISTORY_SIZE = 255
    output_history = []           # Circular buffer of recent outputs

    debug_print("\n" + "="*80)
    debug_print("OPTIMIZATION 2 ENCODER START")
    debug_print("="*80)
    debug_print(f"Strategy: Reference output history with offset + suffix!")
    debug_print("="*80 + "\n")

    signal_count = 0
    eviction_count = 0
    output_count = 0
    fallback_count = 0  # Times we couldn't find prefix in history

    # Read and compress
    with open(input_file, 'rb') as f:
        first_byte = f.read(1)

        if not first_byte:
            writer.write(EOF_CODE, min_bits)
            writer.close()
            debug_print("Empty file - wrote EOF")
            return

        first_char = chr(first_byte[0])
        if first_char not in valid_chars:
            raise ValueError(f"Byte value {first_byte[0]} at position 0 not in alphabet")

        current = first_char
        pos = 1

        while True:
            byte_data = f.read(1)
            if not byte_data:
                break

            char = chr(byte_data[0])
            if char not in valid_chars:
                raise ValueError(f"Byte value {byte_data[0]} at position {pos} not in alphabet")
            pos += 1

            combined = current + char

            if combined in dictionary:
                current = combined
            else:
                # About to output code for current phrase
                output_code = dictionary[current]

                # OPTIMIZATION: Check if this code was evicted and now has a new value
                if output_code in evicted_codes:
                    # Encoder is about to use a code that was evicted!
                    debug_print(f"[ENC] *** EVICT-THEN-USE DETECTED! ***")
                    debug_print(f"[ENC] Code {output_code} was evicted, now being used")

                    # OPTIMIZATION 2: Output History + Offset format:
                    # [EVICT_SIGNAL][code][offset][suffix][code_again]
                    #
                    # Unpack stored entry and prefix
                    entry, prefix = evicted_codes[output_code]

                    # Compute suffix: the character that extends prefix to entry
                    suffix = entry[len(prefix):]
                    if len(suffix) != 1:
                        raise ValueError(f"Logic error: suffix should be 1 char, got {len(suffix)} (entry='{entry}', prefix='{prefix}')")

                    # LINEAR SEARCH (O(255 × L)) through output history
                    # Search backwards for most recent occurrence of prefix
                    offset = None
                    for i in range(len(output_history) - 1, -1, -1):
                        if output_history[i] == prefix:  # O(L) string comparison
                            offset = len(output_history) - i
                            break

                    if offset is not None and offset <= 255:
                        # Found in history! Send compact format
                        debug_print(f"[ENC] Entry='{entry}', prefix='{prefix}' found at offset={offset}, suffix='{suffix}'")
                        debug_print(f"[ENC] Sending offset-based EVICT_SIGNAL")

                        writer.write(EVICT_SIGNAL, code_bits)
                        writer.write(output_code, code_bits)
                        writer.write(offset, 8)  # 1 byte offset
                        writer.write(ord(suffix), 8)  # 1 byte suffix

                        signal_count += 1
                        debug_print(f"[ENC] Signal sent: code={output_code}, offset={offset}, suffix='{suffix}'")
                    else:
                        # Fallback: send full entry (prefix not in recent history)
                        fallback_count += 1
                        debug_print(f"[ENC] Prefix not found in history, using fallback (full entry)")
                        debug_print(f"[ENC] Sending full entry: '{entry}'")

                        writer.write(EVICT_SIGNAL, code_bits)
                        writer.write(output_code, code_bits)
                        writer.write(0, 8)  # offset=0 signals "full entry follows"
                        writer.write(len(entry), 16)
                        for c in entry:
                            writer.write(ord(c), 8)

                        signal_count += 1

                    # Remove from evicted_codes since we've now synced it
                    del evicted_codes[output_code]

                # Output code for current phrase
                writer.write(output_code, code_bits)  # Code sent again (data)
                output_count += 1
                debug_print(f"[ENC #{output_count}] OUTPUT code={output_code} for '{current}' ({code_bits} bits)")

                # OPTIMIZATION 2 (OLD): Add to output history (linear search version)
                output_history.append(current)

                if len(output_history) > OUTPUT_HISTORY_SIZE:
                    output_history.pop(0)  # Remove oldest from buffer

                # Update LRU if current phrase is tracked
                if lru_tracker.contains(current):
                    lru_tracker.use(current)

                # Add new entry to dictionary
                if next_code < EVICT_SIGNAL:
                    # Check if we need to increase bit width
                    if next_code >= threshold and code_bits < max_bits:
                        code_bits += 1
                        threshold <<= 1
                        debug_print(f"[ENC] Increased bit width to {code_bits} bits")

                    # Add new phrase
                    dictionary[combined] = next_code
                    lru_tracker.use(combined)
                    debug_print(f"[ENC] ADDED code={next_code} -> '{combined}'")
                    next_code += 1
                else:
                    # Dictionary FULL - evict LRU
                    lru_entry = lru_tracker.find_lru()
                    if lru_entry is not None:
                        lru_code = dictionary[lru_entry]
                        eviction_count += 1

                        debug_print(f"[ENC] EVICTING code={lru_code} -> '{lru_entry}' (LRU)")
                        debug_print(f"[ENC] ADDING code={lru_code} -> '{combined}' (reusing code)")

                        # Remove old entry
                        del dictionary[lru_entry]
                        lru_tracker.remove(lru_entry)

                        # Add new entry at evicted position
                        dictionary[combined] = lru_code
                        lru_tracker.use(combined)

                        # Track this eviction in case code is used later
                        # Store both the full entry and the prefix (current phrase being output)
                        evicted_codes[lru_code] = (combined, current)

                        debug_print(f"[ENC] Tracking evicted code={lru_code}: entry='{combined}', prefix='{current}'")

                current = char

    # Write final phrase
    final_code = dictionary[current]

    # Check if final code was evicted
    if final_code in evicted_codes:
        debug_print(f"[ENC] *** EVICT-THEN-USE on final phrase! ***")

        entry, prefix = evicted_codes[final_code]
        suffix = entry[len(prefix):]

        # LINEAR SEARCH through output history
        offset = None
        for i in range(len(output_history) - 1, -1, -1):
            if output_history[i] == prefix:
                offset = len(output_history) - i
                break

        if offset is not None and offset <= 255:
            writer.write(EVICT_SIGNAL, code_bits)
            writer.write(final_code, code_bits)
            writer.write(offset, 8)
            writer.write(ord(suffix), 8)
            signal_count += 1
        else:
            writer.write(EVICT_SIGNAL, code_bits)
            writer.write(final_code, code_bits)
            writer.write(0, 8)
            writer.write(len(entry), 16)
            for c in entry:
                writer.write(ord(c), 8)
            signal_count += 1
            fallback_count += 1

        del evicted_codes[final_code]

    writer.write(final_code, code_bits)
    output_count += 1
    debug_print(f"[ENC #{output_count}] OUTPUT code={final_code} for '{current}' (final)")

    # Add final output to history (linear search version)
    output_history.append(current)

    if lru_tracker.contains(current):
        lru_tracker.use(current)

    # Check if decoder will increment bit width before reading EOF
    if next_code >= threshold and code_bits < max_bits:
        code_bits += 1
        debug_print(f"[ENC] Increased bit width to {code_bits} bits before EOF")

    writer.write(EOF_CODE, code_bits)
    debug_print(f"[ENC] Wrote EOF code={EOF_CODE}")
    writer.close()

    debug_print("\n" + "="*80)
    debug_print("OPTIMIZATION 2 ENCODER COMPLETE")
    debug_print("="*80)
    debug_print(f"Total outputs: {output_count}")
    debug_print(f"Total evictions: {eviction_count}")
    debug_print(f"Signals sent: {signal_count}")
    debug_print(f"Offset-based signals: {signal_count - fallback_count}")
    debug_print(f"Fallback (full entry): {fallback_count}")
    debug_print(f"Optimization: {signal_count}/{eviction_count} = {signal_count/eviction_count*100:.1f}% of evictions signaled" if eviction_count > 0 else "No evictions")
    debug_print("="*80 + "\n")

    print(f"Compressed: {input_file} -> {output_file}")

# ============================================================================
# LZW DECOMPRESSION WITH OPTIMIZATION 2
# ============================================================================

def decompress(input_file, output_file):
    """
    Decompress a file using OPTIMIZATION 2.

    EVICT_SIGNAL no longer contains entry - decoder reconstructs using prev + prev[0]!
    """
    reader = BitReader(input_file)

    # Read header
    min_bits = reader.read(8)
    max_bits = reader.read(8)
    alphabet_size = reader.read(16)
    alphabet = [chr(reader.read(8)) for _ in range(alphabet_size)]

    # Initialize dictionary
    dictionary = {i: char for i, char in enumerate(alphabet)}

    EOF_CODE = alphabet_size
    next_code = alphabet_size + 1
    max_size = 1 << max_bits
    EVICT_SIGNAL = max_size - 1

    # Variable-width decoding
    code_bits = min_bits
    threshold = 1 << code_bits

    # LRU tracker for dictionary codes (NOT alphabet codes)
    lru_tracker = LRUTracker()

    # OPTIMIZATION 2: Maintain output history (same as encoder)
    # Note: Decoder only needs the list, not the HashMap
    # Decoder uses direct indexing: output_history[-offset] which is O(1)
    # Encoder needs HashMap for reverse lookup: "string" -> position
    OUTPUT_HISTORY_SIZE = 255
    output_history = []

    debug_print("\n" + "="*80)
    debug_print("OPTIMIZATION 2 DECODER START")
    debug_print("="*80)
    debug_print(f"Strategy: Look up prefix in output history using offset")
    debug_print("="*80 + "\n")

    signal_count = 0
    eviction_count = 0
    input_count = 0
    fallback_count = 0

    # Flag to skip dictionary addition after EVICT_SIGNAL
    skip_next_addition = False

    # Read first codeword
    codeword = reader.read(code_bits)

    if codeword is None:
        raise ValueError("Corrupted file: unexpected end of file")

    if codeword == EOF_CODE:
        reader.close()
        open(output_file, 'wb').close()
        debug_print("Empty file - got EOF")
        return

    # Decode first codeword
    if codeword not in dictionary:
        raise ValueError(f"Invalid first codeword: {codeword}")

    prev = dictionary[codeword]
    input_count += 1
    debug_print(f"[DEC #{input_count}] READ code={codeword} -> '{prev}'")

    with open(output_file, 'wb') as out:
        out.write(prev.encode('latin-1'))

        # Add first output to history
        output_history.append(prev)

        while True:
            # Check if we need to increase bit width
            if next_code >= threshold and code_bits < max_bits:
                code_bits += 1
                threshold <<= 1
                debug_print(f"[DEC] Increased bit width to {code_bits} bits")

            # Read next codeword
            codeword = reader.read(code_bits)

            if codeword is None:
                raise ValueError("Corrupted file: unexpected end of file")

            if codeword == EOF_CODE:
                debug_print(f"[DEC] READ EOF")
                break

            # Check for EVICT_SIGNAL
            if codeword == EVICT_SIGNAL:
                # Encoder evicted and is using the code immediately
                debug_print(f"[DEC] *** EVICT_SIGNAL received ***")

                evicted_code = reader.read(code_bits)
                offset = reader.read(8)

                signal_count += 1

                if offset > 0:
                    # OPTIMIZATION 2: Use output history + suffix
                    suffix_byte = reader.read(8)
                    suffix = chr(suffix_byte)

                    # Look back in output history
                    if offset > len(output_history):
                        raise ValueError(f"Invalid offset {offset}, history size {len(output_history)}")

                    prefix = output_history[-offset]
                    new_entry = prefix + suffix

                    debug_print(f"[DEC] Offset={offset}, prefix='{prefix}' (from history) + suffix='{suffix}' = '{new_entry}'")
                else:
                    # Fallback: full entry provided
                    fallback_count += 1
                    entry_length = reader.read(16)
                    new_entry = ''.join(chr(reader.read(8)) for _ in range(entry_length))

                    debug_print(f"[DEC] Fallback mode: full entry='{new_entry}'")

                # Remove old entry from LRU tracker (if tracked)
                if evicted_code in dictionary and evicted_code >= alphabet_size + 1:
                    lru_tracker.remove(evicted_code)

                # Add reconstructed entry at the specified code position
                dictionary[evicted_code] = new_entry
                lru_tracker.use(evicted_code)

                debug_print(f"[DEC] Dictionary updated: [{evicted_code}] = '{new_entry}'")

                # Set flag to skip dictionary addition on next iteration
                skip_next_addition = True

                # Don't output anything, don't update prev, continue to next code
                continue

            input_count += 1

            # Decode codeword
            if codeword in dictionary:
                current = dictionary[codeword]
                debug_print(f"[DEC #{input_count}] READ code={codeword} -> '{current}'")
            elif codeword == next_code:
                # Special LZW case
                current = prev + prev[0]
                debug_print(f"[DEC #{input_count}] READ code={codeword} -> '{current}' (special case)")
            else:
                debug_print(f"\n[DEC] *** ERROR: Invalid codeword {codeword} ***")
                raise ValueError(f"Invalid codeword: {codeword}")

            # Write decoded string
            out.write(current.encode('latin-1'))

            # OPTIMIZATION 2: Add to output history
            output_history.append(current)
            if len(output_history) > OUTPUT_HISTORY_SIZE:
                output_history.pop(0)

            # Add new entry to dictionary (this is where eviction might happen)
            if not skip_next_addition:
                new_entry = prev + current[0]

                if next_code < EVICT_SIGNAL:
                    # Dictionary not full yet - add normally
                    dictionary[next_code] = new_entry
                    lru_tracker.use(next_code)
                    debug_print(f"[DEC] ADDED code={next_code} -> '{new_entry}'")
                    next_code += 1
                else:
                    # Dictionary FULL - mirror encoder's LRU eviction
                    lru_code = lru_tracker.find_lru()
                    if lru_code is not None:
                        lru_entry = dictionary[lru_code]

                        eviction_count += 1
                        debug_print(f"[DEC] EVICTING code={lru_code} -> '{lru_entry}' (LRU)")
                        debug_print(f"[DEC] ADDING code={lru_code} -> '{new_entry}' (mirroring encoder)")

                        # Remove old entry
                        del dictionary[lru_code]
                        lru_tracker.remove(lru_code)

                        # Add new entry at evicted position
                        dictionary[lru_code] = new_entry
                        lru_tracker.use(lru_code)
            else:
                debug_print(f"[DEC] SKIPPING dictionary addition (just received EVICT_SIGNAL)")

            # Reset flag after processing
            skip_next_addition = False

            # Update LRU for codeword if tracked
            if codeword >= alphabet_size + 1 and codeword < EVICT_SIGNAL:
                if codeword in dictionary:
                    lru_tracker.use(codeword)

            prev = current

    reader.close()

    debug_print("\n" + "="*80)
    debug_print("OPTIMIZATION 2 DECODER COMPLETE")
    debug_print("="*80)
    debug_print(f"Total inputs: {input_count}")
    debug_print(f"Total evictions: {eviction_count}")
    debug_print(f"Signals received: {signal_count}")
    debug_print(f"Offset-based signals: {signal_count - fallback_count}")
    debug_print(f"Fallback (full entry): {fallback_count}")
    debug_print("="*80 + "\n")

    print(f"Decompressed: {input_file} -> {output_file}")

# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    """Parse command-line arguments and run compression or decompression."""
    global DEBUG

    parser = argparse.ArgumentParser(description='LZW compression (optimization 2: minimal EVICT_SIGNAL)')
    sub = parser.add_subparsers(dest='mode', required=True)

    # Compress subcommand
    c = sub.add_parser('compress')
    c.add_argument('input')
    c.add_argument('output')
    c.add_argument('--alphabet', required=True, choices=list(ALPHABETS.keys()))
    c.add_argument('--min-bits', type=int, default=9)
    c.add_argument('--max-bits', type=int, default=16)
    c.add_argument('--debug', action='store_true', help='Enable debug output')

    # Decompress subcommand
    d = sub.add_parser('decompress')
    d.add_argument('input')
    d.add_argument('output')
    d.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    # Set global debug flag
    if hasattr(args, 'debug') and args.debug:
        DEBUG = True

    try:
        if args.mode == 'compress':
            compress(args.input, args.output, args.alphabet, args.min_bits, args.max_bits)
        else:
            decompress(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        if DEBUG:
            traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

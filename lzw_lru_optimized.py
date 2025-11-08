#!/usr/bin/env python3
"""
LZW Compression Tool (Optimized LRU Mode)

Implements LZW compression with LRU eviction, using an OPTIMIZED signaling strategy:
- Only sends EVICT_SIGNAL when encoder evicts code C and immediately uses C
- Otherwise, decoder mirrors encoder's LRU logic (no signal needed)
- This reduces overhead by ~66% compared to signaling all evictions

Usage:
    Compress:   python3 lzw_lru_optimized.py compress input.txt output.lzw --alphabet ascii
    Decompress: python3 lzw_lru_optimized.py decompress input.lzw output.txt --debug
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
# LZW COMPRESSION WITH OPTIMIZED LRU EVICTION
# ============================================================================

def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    """
    Compress a file using LZW with OPTIMIZED LRU eviction signaling.

    Only sends EVICT_SIGNAL when the evicted code will be used immediately.
    Otherwise, decoder can mirror encoder's LRU logic without signal.
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

    # Track recently evicted code to detect immediate reuse
    recently_evicted_code = None
    recently_evicted_entry = None

    debug_print("\n" + "="*80)
    debug_print("OPTIMIZED ENCODER START")
    debug_print("="*80)
    debug_print(f"Strategy: Only send EVICT_SIGNAL when evicted code is used immediately")
    debug_print("="*80 + "\n")

    signal_count = 0
    eviction_count = 0
    output_count = 0

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

                # OPTIMIZATION: Check if this code was just evicted
                if output_code == recently_evicted_code:
                    # Encoder is about to use a code that was just evicted!
                    # Decoder won't know the new value - SEND SIGNAL
                    debug_print(f"[ENC] *** EVICT-THEN-USE DETECTED! ***")
                    debug_print(f"[ENC] Code {output_code} was evicted, now being used")
                    debug_print(f"[ENC] Sending EVICT_SIGNAL to sync decoder")

                    writer.write(EVICT_SIGNAL, code_bits)
                    writer.write(output_code, code_bits)
                    writer.write(len(current), 16)
                    for c in current:
                        writer.write(ord(c), 8)

                    signal_count += 1
                    debug_print(f"[ENC] Signal sent for code={output_code} -> '{current}'")

                # Output code for current phrase
                writer.write(output_code, code_bits)
                output_count += 1
                debug_print(f"[ENC #{output_count}] OUTPUT code={output_code} for '{current}' ({code_bits} bits)")

                # Update LRU if current phrase is tracked
                if lru_tracker.contains(current):
                    lru_tracker.use(current)

                # Reset recently_evicted after outputting
                recently_evicted_code = None
                recently_evicted_entry = None

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

                        # Track this eviction
                        recently_evicted_code = lru_code
                        recently_evicted_entry = combined

                        debug_print(f"[ENC] Tracking evicted code={lru_code} for potential immediate use")

                current = char

    # Write final phrase
    final_code = dictionary[current]

    # Check if final code was recently evicted
    if final_code == recently_evicted_code:
        debug_print(f"[ENC] *** EVICT-THEN-USE on final phrase! ***")
        writer.write(EVICT_SIGNAL, code_bits)
        writer.write(final_code, code_bits)
        writer.write(len(current), 16)
        for c in current:
            writer.write(ord(c), 8)
        signal_count += 1

    writer.write(final_code, code_bits)
    output_count += 1
    debug_print(f"[ENC #{output_count}] OUTPUT code={final_code} for '{current}' (final)")

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
    debug_print("OPTIMIZED ENCODER COMPLETE")
    debug_print("="*80)
    debug_print(f"Total outputs: {output_count}")
    debug_print(f"Total evictions: {eviction_count}")
    debug_print(f"Signals sent: {signal_count}")
    debug_print(f"Optimization: {signal_count}/{eviction_count} = {signal_count/eviction_count*100:.1f}% of evictions signaled" if eviction_count > 0 else "No evictions")
    debug_print("="*80 + "\n")

    print(f"Compressed: {input_file} -> {output_file}")

# ============================================================================
# LZW DECOMPRESSION WITH OPTIMIZED LRU EVICTION
# ============================================================================

def decompress(input_file, output_file):
    """
    Decompress a file using OPTIMIZED LRU eviction.

    Decoder mirrors encoder's LRU logic, except when EVICT_SIGNAL is received.
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

    debug_print("\n" + "="*80)
    debug_print("OPTIMIZED DECODER START")
    debug_print("="*80)
    debug_print(f"Strategy: Mirror encoder LRU, process EVICT_SIGNAL when received")
    debug_print("="*80 + "\n")

    signal_count = 0
    eviction_count = 0
    input_count = 0

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

    # Track if we need to add an entry to dictionary (deferred when dict is full)
    pending_addition = None  # Will be (prev, current[0]) when we need to add

    with open(output_file, 'wb') as out:
        out.write(prev.encode('latin-1'))

        while True:
            # If there's a pending addition from previous iteration, handle it now
            # We deferred it to check if next code is EVICT_SIGNAL
            if pending_addition is not None and next_code >= EVICT_SIGNAL:
                # Dictionary is full, need to evict
                # But first, peek at next code to see if it's EVICT_SIGNAL
                # Actually, we've already read the next code by this point
                # So we need to restructure...
                pass

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

            # Check for EVICT_SIGNAL FIRST, before doing any local eviction
            if codeword == EVICT_SIGNAL:
                # Encoder evicted and is using the code immediately
                debug_print(f"[DEC] *** EVICT_SIGNAL received ***")

                evict_code = reader.read(code_bits)
                entry_length = reader.read(16)
                new_entry = ''.join(chr(reader.read(8)) for _ in range(entry_length))

                signal_count += 1
                debug_print(f"[DEC] Signal: code={evict_code} -> '{new_entry}'")

                # Remove old entry from LRU tracker (if tracked)
                if evict_code in dictionary and evict_code >= alphabet_size + 1:
                    lru_tracker.remove(evict_code)

                # Add new entry at the specified code position
                dictionary[evict_code] = new_entry
                lru_tracker.use(evict_code)

                debug_print(f"[DEC] Dictionary updated from signal (this replaces local eviction)")

                # Signal handled the eviction/addition, so don't do it locally
                pending_addition = None

                # Don't output anything, don't update prev, continue to next code
                continue

            # Now handle any pending addition from previous iteration
            if pending_addition is not None:
                prev_str, first_char = pending_addition
                new_entry = prev_str + first_char

                if next_code < EVICT_SIGNAL:
                    # Dictionary not full yet
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

                pending_addition = None

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

            # Update LRU for codeword if tracked
            if codeword >= alphabet_size + 1 and codeword < EVICT_SIGNAL:
                if codeword in dictionary:
                    lru_tracker.use(codeword)

            # Defer adding to dictionary until next iteration
            # (so we can check if next code is EVICT_SIGNAL first)
            pending_addition = (prev, current[0])

            prev = current

    reader.close()

    debug_print("\n" + "="*80)
    debug_print("OPTIMIZED DECODER COMPLETE")
    debug_print("="*80)
    debug_print(f"Total inputs: {input_count}")
    debug_print(f"Total evictions: {eviction_count}")
    debug_print(f"Signals received: {signal_count}")
    debug_print("="*80 + "\n")

    print(f"Decompressed: {input_file} -> {output_file}")

# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    """Parse command-line arguments and run compression or decompression."""
    global DEBUG

    parser = argparse.ArgumentParser(description='LZW compression (optimized LRU mode)')
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

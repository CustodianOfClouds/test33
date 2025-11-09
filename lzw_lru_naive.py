#!/usr/bin/env python3
"""
LZW Compression Tool (Naive LRU Mode - For Debugging)

This is a NAIVE implementation that directly mirrors LRU logic from encoder to decoder
WITHOUT the EVICT_SIGNAL mechanism. This will expose synchronization issues.

The purpose is to identify WHEN and WHERE the encoder and decoder states misalign.

Usage:
    Compress:   python3 lzw_lru_naive.py compress input.txt output.lzw --alphabet ascii
    Decompress: python3 lzw_lru_naive.py decompress input.lzw output.txt --debug
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
    """
    O(1) LRU tracker using doubly-linked list + HashMap.
    """
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

    def get_all_keys_lru_order(self) -> list:
        """Return all keys in LRU order (LRU first, MRU last)."""
        keys = []
        node = self.tail.prev
        while node != self.head:
            if node.key is not None:
                keys.append(node.key)
            node = node.prev
        return keys

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
# LZW COMPRESSION WITH NAIVE LRU EVICTION
# ============================================================================

def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    """
    Compress a file using LZW with NAIVE LRU eviction policy.

    This version does NOT send EVICT_SIGNAL - it just evicts and reuses codes.
    This will cause misalignment issues that we want to debug.
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

    # Variable-width encoding
    code_bits = min_bits
    threshold = 1 << code_bits

    # LRU tracker for dictionary entries (NOT alphabet entries)
    lru_tracker = LRUTracker()

    debug_print("\n" + "="*80)
    debug_print("ENCODER START")
    debug_print("="*80)
    debug_print(f"Alphabet size: {len(alphabet)}")
    debug_print(f"EOF_CODE: {EOF_CODE}")
    debug_print(f"Max dictionary size: {max_size}")
    debug_print(f"Starting with {min_bits} bits, max {max_bits} bits")
    debug_print("="*80 + "\n")

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
        output_count = 0

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
                # Output code for current phrase
                output_code = dictionary[current]
                writer.write(output_code, code_bits)
                output_count += 1

                debug_print(f"[ENC #{output_count}] OUTPUT code={output_code} for '{current}' ({code_bits} bits)")

                # Update LRU if current phrase is tracked
                if lru_tracker.contains(current):
                    lru_tracker.use(current)
                    debug_print(f"[ENC] Updated LRU: '{current}' is now MRU")

                # Add new entry to dictionary
                if next_code < max_size:
                    # Check if we need to increase bit width
                    if next_code >= threshold and code_bits < max_bits:
                        code_bits += 1
                        threshold <<= 1
                        debug_print(f"[ENC] Increased bit width to {code_bits} bits (threshold now {threshold})")

                    # Add new phrase
                    dictionary[combined] = next_code
                    lru_tracker.use(combined)
                    debug_print(f"[ENC] ADDED code={next_code} -> '{combined}' (dict size: {len(dictionary)})")
                    debug_print(f"[ENC] LRU order (LRU->MRU): {lru_tracker.get_all_keys_lru_order()}")
                    next_code += 1
                else:
                    # Dictionary FULL - evict LRU (NAIVE - no signal to decoder!)
                    lru_entry = lru_tracker.find_lru()
                    if lru_entry is not None:
                        lru_code = dictionary[lru_entry]

                        debug_print(f"\n[ENC] *** DICTIONARY FULL ***")
                        debug_print(f"[ENC] LRU order before eviction: {lru_tracker.get_all_keys_lru_order()}")
                        debug_print(f"[ENC] EVICTING code={lru_code} -> '{lru_entry}' (LRU entry)")
                        debug_print(f"[ENC] ADDING code={lru_code} -> '{combined}' (reusing evicted code)")
                        debug_print(f"[ENC] *** NO SIGNAL SENT TO DECODER (naive mode) ***\n")

                        # Remove old entry
                        del dictionary[lru_entry]
                        lru_tracker.remove(lru_entry)

                        # Add new entry at evicted position
                        dictionary[combined] = lru_code
                        lru_tracker.use(combined)

                        debug_print(f"[ENC] LRU order after eviction: {lru_tracker.get_all_keys_lru_order()}")

                current = char

    # Write final phrase
    final_code = dictionary[current]
    writer.write(final_code, code_bits)
    output_count += 1
    debug_print(f"[ENC #{output_count}] OUTPUT code={final_code} for '{current}' (final phrase, {code_bits} bits)")

    if lru_tracker.contains(current):
        lru_tracker.use(current)

    # Check if decoder will increment bit width before reading EOF
    if next_code >= threshold and code_bits < max_bits:
        code_bits += 1
        debug_print(f"[ENC] Increased bit width to {code_bits} bits before EOF")

    writer.write(EOF_CODE, code_bits)
    debug_print(f"[ENC] Wrote EOF code={EOF_CODE} ({code_bits} bits)")
    writer.close()

    debug_print("\n" + "="*80)
    debug_print("ENCODER COMPLETE")
    debug_print("="*80 + "\n")

    print(f"Compressed: {input_file} -> {output_file}")

# ============================================================================
# LZW DECOMPRESSION WITH NAIVE LRU EVICTION
# ============================================================================

def decompress(input_file, output_file):
    """
    Decompress a file using NAIVE LRU eviction policy.

    This version tries to mirror the encoder's LRU logic without receiving
    EVICT_SIGNAL. This will expose synchronization issues.
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

    # Variable-width decoding
    code_bits = min_bits
    threshold = 1 << code_bits

    # LRU tracker for dictionary codes (NOT alphabet codes)
    lru_tracker = LRUTracker()

    debug_print("\n" + "="*80)
    debug_print("DECODER START")
    debug_print("="*80)
    debug_print(f"Alphabet size: {alphabet_size}")
    debug_print(f"EOF_CODE: {EOF_CODE}")
    debug_print(f"Max dictionary size: {max_size}")
    debug_print(f"Starting with {min_bits} bits, max {max_bits} bits")
    debug_print("="*80 + "\n")

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
        debug_print(f"\n[DEC] *** ERROR: First codeword {codeword} not in dictionary! ***")
        debug_print(f"[DEC] Dictionary keys: {sorted(dictionary.keys())}")
        raise ValueError(f"Invalid first codeword: {codeword}")

    prev = dictionary[codeword]
    input_count = 1

    debug_print(f"[DEC #{input_count}] READ code={codeword} -> '{prev}' ({code_bits} bits)")

    with open(output_file, 'wb') as out:
        out.write(prev.encode('latin-1'))

        while True:
            # Check if we need to increase bit width
            if next_code >= threshold and code_bits < max_bits:
                code_bits += 1
                threshold <<= 1
                debug_print(f"[DEC] Increased bit width to {code_bits} bits (threshold now {threshold})")

            # Read next codeword
            codeword = reader.read(code_bits)

            if codeword is None:
                raise ValueError("Corrupted file: unexpected end of file")

            if codeword == EOF_CODE:
                debug_print(f"[DEC] READ EOF code={EOF_CODE}")
                break

            input_count += 1

            # Decode codeword
            if codeword in dictionary:
                current = dictionary[codeword]
                debug_print(f"[DEC #{input_count}] READ code={codeword} -> '{current}' ({code_bits} bits)")
            elif codeword == next_code:
                # Special LZW case
                current = prev + prev[0]
                debug_print(f"[DEC #{input_count}] READ code={codeword} -> '{current}' (SPECIAL CASE: not yet in dict, {code_bits} bits)")
            else:
                # MISALIGNMENT DETECTED!
                debug_print(f"\n[DEC] *** MISALIGNMENT DETECTED! ***")
                debug_print(f"[DEC] READ code={codeword} ({code_bits} bits)")
                debug_print(f"[DEC] Code NOT in dictionary!")
                debug_print(f"[DEC] next_code={next_code}")
                debug_print(f"[DEC] Dictionary codes: {sorted([k for k in dictionary.keys() if k >= alphabet_size + 1])}")
                debug_print(f"[DEC] LRU order: {lru_tracker.get_all_keys_lru_order()}")
                debug_print(f"[DEC] Previous decoded: '{prev}'")
                debug_print(f"[DEC] *** This is where encoder and decoder are OUT OF SYNC! ***\n")
                raise ValueError(f"Invalid codeword: {codeword} (next_code={next_code})")

            # Write decoded string
            out.write(current.encode('latin-1'))

            # Add new entry to dictionary
            if next_code < max_size:
                new_entry = prev + current[0]
                dictionary[next_code] = new_entry
                lru_tracker.use(next_code)
                debug_print(f"[DEC] ADDED code={next_code} -> '{new_entry}' (dict size: {len(dictionary)})")
                debug_print(f"[DEC] LRU order (LRU->MRU): {lru_tracker.get_all_keys_lru_order()}")
                next_code += 1
            else:
                # Dictionary FULL - evict LRU (mirroring encoder)
                lru_code = lru_tracker.find_lru()
                if lru_code is not None:
                    lru_entry = dictionary[lru_code]
                    new_entry = prev + current[0]

                    debug_print(f"\n[DEC] *** DICTIONARY FULL ***")
                    debug_print(f"[DEC] LRU order before eviction: {lru_tracker.get_all_keys_lru_order()}")
                    debug_print(f"[DEC] EVICTING code={lru_code} -> '{lru_entry}' (LRU entry)")
                    debug_print(f"[DEC] ADDING code={lru_code} -> '{new_entry}' (reusing evicted code)")

                    # Remove old entry
                    del dictionary[lru_code]
                    lru_tracker.remove(lru_code)

                    # Add new entry at evicted position
                    dictionary[lru_code] = new_entry
                    lru_tracker.use(lru_code)

                    debug_print(f"[DEC] LRU order after eviction: {lru_tracker.get_all_keys_lru_order()}\n")

            # Update LRU for codeword if tracked
            if codeword >= alphabet_size + 1 and codeword < max_size:
                if codeword in dictionary:
                    lru_tracker.use(codeword)
                    debug_print(f"[DEC] Updated LRU: code {codeword} is now MRU")

            prev = current

    reader.close()

    debug_print("\n" + "="*80)
    debug_print("DECODER COMPLETE")
    debug_print("="*80 + "\n")

    print(f"Decompressed: {input_file} -> {output_file}")

# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    """Parse command-line arguments and run compression or decompression."""
    global DEBUG

    parser = argparse.ArgumentParser(description='LZW compression (naive LRU mode - for debugging)')
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

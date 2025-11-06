#!/usr/bin/env python3
"""
LZW Compression Tool (Freeze Mode)

A command-line tool for LZW compression/decompression using the freeze policy.
When the dictionary fills up, it "freezes" and no new entries are added.

Usage:
    Compress: python3 lzw_freeze.py compress input.txt output.lzw --alphabet ascii
    Decompress: python3 lzw_freeze.py decompress input.lzw output.txt
"""

import sys
import argparse
from typing import List, Dict, Optional


# ============================================================================
# PREDEFINED ALPHABETS
# ============================================================================

ALPHABETS = {
    'ascii': [chr(i) for i in range(128)],
    'extendedascii': [chr(i) for i in range(256)],
    'ab': ['a', 'b']
}


# ============================================================================
# BIT-LEVEL I/O CLASSES
# ============================================================================

class BitWriter:
    """Writes variable-width integers to a file as a stream of bits."""

    def __init__(self, filename: str):
        self.file = open(filename, 'wb')
        self.buffer = 0  # Accumulates bits before writing
        self.n_bits = 0  # Number of bits currently in buffer

    def write(self, value: int, num_bits: int):
        """Write 'num_bits' bits from 'value' to the output."""
        if num_bits < 0 or num_bits > 32:
            raise ValueError(f"num_bits must be between 0 and 32, got {num_bits}")

        # Add bits to buffer
        self.buffer = (self.buffer << num_bits) | value
        self.n_bits += num_bits

        # Write complete bytes
        while self.n_bits >= 8:
            self.n_bits -= 8
            byte = (self.buffer >> self.n_bits) & 0xFF
            self.file.write(bytes([byte]))

    def close(self):
        """Flush remaining bits and close the file."""
        # Pad with zeros to complete the last byte
        if self.n_bits > 0:
            byte = (self.buffer << (8 - self.n_bits)) & 0xFF
            self.file.write(bytes([byte]))
        self.file.close()


class BitReader:
    """Reads variable-width integers from a file as a stream of bits."""

    def __init__(self, filename: str):
        self.file = open(filename, 'rb')
        self.buffer = 0  # Holds bits read from file
        self.n_bits = 0  # Number of bits currently in buffer

    def read(self, num_bits: int) -> Optional[int]:
        """Read 'num_bits' bits from the input. Returns None at EOF."""
        if num_bits < 0 or num_bits > 32:
            raise ValueError(f"num_bits must be between 0 and 32, got {num_bits}")

        # Fill buffer with enough bits
        while self.n_bits < num_bits:
            byte_data = self.file.read(1)
            if not byte_data:
                return None  # EOF
            self.buffer = (self.buffer << 8) | byte_data[0]
            self.n_bits += 8

        # Extract the requested bits
        self.n_bits -= num_bits
        value = (self.buffer >> self.n_bits) & ((1 << num_bits) - 1)
        return value

    def is_empty(self) -> bool:
        """Check if we're at the end of file with no bits left."""
        if self.n_bits > 0:
            return False
        byte_data = self.file.read(1)
        if not byte_data:
            return True
        # Put the byte back into buffer
        self.buffer = byte_data[0]
        self.n_bits = 8
        return False

    def close(self):
        """Close the file."""
        self.file.close()


# ============================================================================
# COMPRESSION HEADER
# ============================================================================

def write_header(writer: BitWriter, min_code_bits: int, max_code_bits: int,
                 alphabet: List[str]):
    """
    Write compression metadata to the output file.

    Format:
        - 8 bits: min_code_bits (starting bit width for codewords)
        - 8 bits: max_code_bits (maximum bit width for codewords)
        - 8 bits: policy code (0 = freeze)
        - 16 bits: alphabet size
        - 8 bits per character: alphabet symbols
    """
    writer.write(min_code_bits, 8)
    writer.write(max_code_bits, 8)
    writer.write(0, 8)  # Policy: 0 = freeze
    writer.write(len(alphabet), 16)
    for char in alphabet:
        writer.write(ord(char), 8)


def read_header(reader: BitReader) -> Dict:
    """
    Read compression metadata from the input file.

    Returns a dictionary with keys: min_code_bits, max_code_bits,
    policy, alphabet_size, alphabet
    """
    min_code_bits = reader.read(8)
    max_code_bits = reader.read(8)
    policy = reader.read(8)
    alphabet_size = reader.read(16)

    alphabet = []
    for _ in range(alphabet_size):
        char_code = reader.read(8)
        alphabet.append(chr(char_code))

    return {
        'min_code_bits': min_code_bits,
        'max_code_bits': max_code_bits,
        'policy': policy,
        'alphabet_size': alphabet_size,
        'alphabet': alphabet
    }


# ============================================================================
# LZW COMPRESSION (FREEZE MODE)
# ============================================================================

def compress(input_file: str, output_file: str, alphabet_name: str,
             min_code_bits: int = 9, max_code_bits: int = 16):
    """
    Compress a file using LZW with freeze policy.

    Args:
        input_file: Path to input file to compress
        output_file: Path to output compressed file
        alphabet_name: Name of alphabet to use (ascii, extendedascii, or ab)
        min_code_bits: Starting bit width for codewords (default: 9)
        max_code_bits: Maximum bit width for codewords (default: 16)
    """
    # Get alphabet
    if alphabet_name not in ALPHABETS:
        raise ValueError(f"Unknown alphabet: {alphabet_name}. "
                        f"Available: {', '.join(ALPHABETS.keys())}")
    alphabet = ALPHABETS[alphabet_name]

    # Validate parameters
    if min_code_bits < 1:
        raise ValueError(f"min_code_bits must be at least 1, got {min_code_bits}")
    if max_code_bits < min_code_bits:
        raise ValueError(f"max_code_bits ({max_code_bits}) must be >= "
                        f"min_code_bits ({min_code_bits})")

    # Create valid character set for input validation
    valid_chars = set(alphabet)

    # Initialize output writer
    writer = BitWriter(output_file)
    write_header(writer, min_code_bits, max_code_bits, alphabet)

    # Initialize dictionary with single characters
    dictionary: Dict[str, int] = {}
    for i, char in enumerate(alphabet):
        dictionary[char] = i

    next_code = len(alphabet)
    EOF_CODE = next_code
    next_code += 1

    # Compression parameters
    current_code_bits = min_code_bits
    max_dict_size = 1 << max_code_bits  # 2^max_code_bits
    width_threshold = 1 << current_code_bits

    # Read input file
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            input_text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Validate input
    for i, char in enumerate(input_text):
        if char not in valid_chars:
            raise ValueError(f"Character '{char}' (code {ord(char)}) at position {i} "
                           f"is not in the {alphabet_name} alphabet")

    if not input_text:
        writer.write(EOF_CODE, current_code_bits)
        writer.close()
        return

    # LZW compression algorithm
    current_string = input_text[0]

    for i in range(1, len(input_text)):
        char = input_text[i]
        combined = current_string + char

        if combined in dictionary:
            # Phrase exists in dictionary, keep extending
            current_string = combined
        else:
            # Output code for current_string
            code = dictionary[current_string]
            writer.write(code, current_code_bits)

            # Add new phrase to dictionary if not full (freeze mode)
            if next_code < max_dict_size:
                # Increase bit width if needed
                if next_code >= width_threshold and current_code_bits < max_code_bits:
                    current_code_bits += 1
                    width_threshold = 1 << current_code_bits

                # Add new entry
                dictionary[combined] = next_code
                next_code += 1

            # Start new phrase with current character
            current_string = char

    # Output final phrase
    if current_string:
        code = dictionary[current_string]
        writer.write(code, current_code_bits)

    # Increase bit width for EOF if needed
    if next_code >= width_threshold and current_code_bits < max_code_bits:
        current_code_bits += 1

    # Write EOF marker
    writer.write(EOF_CODE, current_code_bits)
    writer.close()

    print(f"Compressed {input_file} -> {output_file}")
    print(f"Alphabet: {alphabet_name} ({len(alphabet)} symbols)")
    print(f"Code bits: {min_code_bits} to {max_code_bits}")


# ============================================================================
# LZW DECOMPRESSION
# ============================================================================

def decompress(input_file: str, output_file: str):
    """
    Decompress a file that was compressed with LZW freeze mode.

    Args:
        input_file: Path to compressed input file
        output_file: Path to decompressed output file
    """
    reader = BitReader(input_file)

    # Read header
    header = read_header(reader)
    min_code_bits = header['min_code_bits']
    max_code_bits = header['max_code_bits']
    alphabet = header['alphabet']
    alphabet_size = header['alphabet_size']

    # Initialize dictionary with single characters
    dictionary: Dict[int, str] = {}
    for i, char in enumerate(alphabet):
        dictionary[i] = char

    EOF_CODE = alphabet_size
    next_code = alphabet_size + 1

    # Decompression parameters
    current_code_bits = min_code_bits
    max_dict_size = 1 << max_code_bits
    width_threshold = 1 << current_code_bits

    # Read first codeword
    codeword = reader.read(current_code_bits)
    if codeword is None or codeword == EOF_CODE:
        reader.close()
        with open(output_file, 'w', encoding='utf-8') as f:
            pass  # Empty file
        return

    # Output first character
    output_text = [dictionary[codeword]]
    previous_string = dictionary[codeword]

    # LZW decompression algorithm
    while True:
        # Increase bit width if needed
        if next_code >= width_threshold and current_code_bits < max_code_bits:
            current_code_bits += 1
            width_threshold = 1 << current_code_bits

        # Read next codeword
        codeword = reader.read(current_code_bits)
        if codeword is None or codeword == EOF_CODE:
            break

        # Decode codeword
        if codeword in dictionary:
            # Code exists in dictionary
            current_string = dictionary[codeword]
        elif codeword == next_code:
            # Special case: code not yet in dictionary
            # This happens when pattern is like "aba" -> we're encoding "ab" + "a"
            # but we're reading the code for "aba" before it's added
            current_string = previous_string + previous_string[0]
        else:
            raise ValueError(f"Invalid codeword {codeword} at position {next_code}")

        # Output decoded string
        output_text.append(current_string)

        # Add new entry to dictionary if not full (freeze mode)
        if next_code < max_dict_size:
            new_entry = previous_string + current_string[0]
            dictionary[next_code] = new_entry
            next_code += 1

        previous_string = current_string

    reader.close()

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(output_text))

    print(f"Decompressed {input_file} -> {output_file}")


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='LZW compression tool with freeze policy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Compress a file with ASCII alphabet:
    python3 lzw_freeze.py compress input.txt output.lzw --alphabet ascii

  Compress with 2-letter alphabet:
    python3 lzw_freeze.py compress input.txt output.lzw --alphabet ab

  Compress with custom bit widths:
    python3 lzw_freeze.py compress input.txt output.lzw --alphabet ascii --min-bits 8 --max-bits 12

  Decompress a file:
    python3 lzw_freeze.py decompress output.lzw decoded.txt

Available alphabets:
  ascii         - Standard ASCII (128 characters: 0-127)
  extendedascii - Extended ASCII (256 characters: 0-255)
  ab            - Two-letter alphabet (just 'a' and 'b')
        """
    )

    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    subparsers.required = True

    # Compress subcommand
    compress_parser = subparsers.add_parser('compress', help='Compress a file')
    compress_parser.add_argument('input', help='Input file to compress')
    compress_parser.add_argument('output', help='Output compressed file')
    compress_parser.add_argument('--alphabet', required=True,
                                choices=list(ALPHABETS.keys()),
                                help='Alphabet to use for compression')
    compress_parser.add_argument('--min-bits', type=int, default=9,
                                help='Starting bit width for codewords (default: 9)')
    compress_parser.add_argument('--max-bits', type=int, default=16,
                                help='Maximum bit width for codewords (default: 16, max dictionary size: 2^16)')

    # Decompress subcommand
    decompress_parser = subparsers.add_parser('decompress', help='Decompress a file')
    decompress_parser.add_argument('input', help='Input compressed file')
    decompress_parser.add_argument('output', help='Output decompressed file')

    args = parser.parse_args()

    try:
        if args.mode == 'compress':
            compress(args.input, args.output, args.alphabet,
                    args.min_bits, args.max_bits)
        elif args.mode == 'decompress':
            decompress(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

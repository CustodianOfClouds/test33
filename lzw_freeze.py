#!/usr/bin/env python3
"""LZW Compression (Freeze Mode) - Dictionary freezes when full"""

import sys
import argparse

ALPHABETS = {
    'ascii': [chr(i) for i in range(128)],
    'extendedascii': [chr(i) for i in range(256)],
    'ab': ['a', 'b']
}

class BitWriter:
    def __init__(self, filename):
        self.file = open(filename, 'wb')
        self.buffer = 0
        self.n_bits = 0

    def write(self, value, num_bits):
        self.buffer = (self.buffer << num_bits) | value
        self.n_bits += num_bits
        while self.n_bits >= 8:
            self.n_bits -= 8
            self.file.write(bytes([(self.buffer >> self.n_bits) & 0xFF]))

    def close(self):
        if self.n_bits > 0:
            self.file.write(bytes([(self.buffer << (8 - self.n_bits)) & 0xFF]))
        self.file.close()

class BitReader:
    def __init__(self, filename):
        self.file = open(filename, 'rb')
        self.buffer = 0
        self.n_bits = 0

    def read(self, num_bits):
        while self.n_bits < num_bits:
            byte_data = self.file.read(1)
            if not byte_data:
                return None
            self.buffer = (self.buffer << 8) | byte_data[0]
            self.n_bits += 8
        self.n_bits -= num_bits
        return (self.buffer >> self.n_bits) & ((1 << num_bits) - 1)

    def close(self):
        self.file.close()

def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    alphabet = ALPHABETS[alphabet_name]
    valid_chars = set(alphabet)

    writer = BitWriter(output_file)
    writer.write(min_bits, 8)
    writer.write(max_bits, 8)
    writer.write(0, 8)  # freeze policy
    writer.write(len(alphabet), 16)
    for char in alphabet:
        writer.write(ord(char), 8)

    dictionary = {char: i for i, char in enumerate(alphabet)}
    next_code = len(alphabet) + 1  # +1 for EOF

    with open(input_file, 'r') as f:
        text = f.read()

    for i, char in enumerate(text):
        if char not in valid_chars:
            raise ValueError(f"Character '{char}' at position {i} not in alphabet")

    if not text:
        writer.write(len(alphabet), min_bits)  # EOF
        writer.close()
        return

    code_bits = min_bits
    max_size = 1 << max_bits
    threshold = 1 << code_bits
    current = text[0]

    for char in text[1:]:
        combined = current + char
        if combined in dictionary:
            current = combined
        else:
            writer.write(dictionary[current], code_bits)
            if next_code < max_size:
                if next_code >= threshold and code_bits < max_bits:
                    code_bits += 1
                    threshold = 1 << code_bits
                dictionary[combined] = next_code
                next_code += 1
            current = char

    writer.write(dictionary[current], code_bits)
    if next_code >= threshold and code_bits < max_bits:
        code_bits += 1
    writer.write(len(alphabet), code_bits)  # EOF
    writer.close()
    print(f"Compressed: {input_file} -> {output_file}")

def decompress(input_file, output_file):
    reader = BitReader(input_file)

    min_bits = reader.read(8)
    max_bits = reader.read(8)
    reader.read(8)  # policy (unused)
    alphabet_size = reader.read(16)
    alphabet = [chr(reader.read(8)) for _ in range(alphabet_size)]

    dictionary = {i: char for i, char in enumerate(alphabet)}
    EOF = alphabet_size
    next_code = alphabet_size + 1

    code_bits = min_bits
    max_size = 1 << max_bits
    threshold = 1 << code_bits

    codeword = reader.read(code_bits)
    if codeword is None or codeword == EOF:
        reader.close()
        open(output_file, 'w').close()
        return

    output = [dictionary[codeword]]
    prev = dictionary[codeword]

    while True:
        if next_code >= threshold and code_bits < max_bits:
            code_bits += 1
            threshold = 1 << code_bits

        codeword = reader.read(code_bits)
        if codeword is None or codeword == EOF:
            break

        if codeword in dictionary:
            current = dictionary[codeword]
        elif codeword == next_code:
            current = prev + prev[0]
        else:
            raise ValueError(f"Invalid codeword: {codeword}")

        output.append(current)
        if next_code < max_size:
            dictionary[next_code] = prev + current[0]
            next_code += 1
        prev = current

    reader.close()
    with open(output_file, 'w') as f:
        f.write(''.join(output))
    print(f"Decompressed: {input_file} -> {output_file}")

def main():
    parser = argparse.ArgumentParser(description='LZW compression (freeze mode)')
    sub = parser.add_subparsers(dest='mode', required=True)

    c = sub.add_parser('compress')
    c.add_argument('input')
    c.add_argument('output')
    c.add_argument('--alphabet', required=True, choices=list(ALPHABETS.keys()))
    c.add_argument('--min-bits', type=int, default=9)
    c.add_argument('--max-bits', type=int, default=16)

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
        sys.exit(1)

if __name__ == '__main__':
    main()

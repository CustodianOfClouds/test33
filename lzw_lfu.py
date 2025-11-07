#!/usr/bin/env python3
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
            self.file.write(bytes([self.buffer >> self.n_bits]))
            self.buffer &= (1 << self.n_bits) - 1

    def close(self):
        if self.n_bits > 0:
            self.file.write(bytes([self.buffer << (8 - self.n_bits)]))
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
        value = self.buffer >> self.n_bits
        self.buffer &= (1 << self.n_bits) - 1
        return value

    def close(self):
        self.file.close()

class LFUTracker:
    class Node:
        def __init__(self, key, freq):
            self.key = key
            self.freq = freq
            self.prev = None
            self.next = None

    class FreqList:
        def __init__(self):
            self.head = LFUTracker.Node(None, 0)
            self.tail = LFUTracker.Node(None, 0)
            self.head.next = self.tail
            self.tail.prev = self.head

        def add_to_front(self, node):
            node.next = self.head.next
            node.prev = self.head
            self.head.next.prev = node
            self.head.next = node

        def remove(self, node):
            node.prev.next = node.next
            node.next.prev = node.prev

        def is_empty(self):
            return self.head.next == self.tail

        def get_last(self):
            if self.tail.prev == self.head:
                return None
            return self.tail.prev

    def __init__(self, capacity):
        self.key_to_node = {}
        self.freq_to_list = {}
        self.min_freq = 0

    def use(self, key):
        node = self.key_to_node.get(key)
        if node is None:
            node = self.Node(key, 1)
            self.key_to_node[key] = node
            if 1 not in self.freq_to_list:
                self.freq_to_list[1] = self.FreqList()
            self.freq_to_list[1].add_to_front(node)
            self.min_freq = 1
        else:
            old_freq = node.freq
            old_list = self.freq_to_list[old_freq]
            old_list.remove(node)

            if old_freq == self.min_freq and old_list.is_empty():
                self.min_freq = old_freq + 1

            node.freq += 1
            if node.freq not in self.freq_to_list:
                self.freq_to_list[node.freq] = self.FreqList()
            self.freq_to_list[node.freq].add_to_front(node)

    def find_lfu(self):
        min_list = self.freq_to_list.get(self.min_freq)
        if min_list is None or min_list.is_empty():
            return None
        lfu_node = min_list.get_last()
        return lfu_node.key

    def remove(self, key):
        node = self.key_to_node.pop(key, None)
        if node is not None:
            freq_list = self.freq_to_list[node.freq]
            freq_list.remove(node)

    def contains(self, key):
        return key in self.key_to_node

class LFUTrackerDecoder:
    class Node:
        def __init__(self, code, freq):
            self.code = code
            self.freq = freq
            self.prev = None
            self.next = None

    class FreqList:
        def __init__(self):
            self.head = LFUTrackerDecoder.Node(-1, 0)
            self.tail = LFUTrackerDecoder.Node(-1, 0)
            self.head.next = self.tail
            self.tail.prev = self.head

        def add_to_front(self, node):
            node.next = self.head.next
            node.prev = self.head
            self.head.next.prev = node
            self.head.next = node

        def remove(self, node):
            node.prev.next = node.next
            node.next.prev = node.prev

        def is_empty(self):
            return self.head.next == self.tail

        def get_last(self):
            if self.tail.prev == self.head:
                return None
            return self.tail.prev

    def __init__(self, capacity):
        self.code_to_node = {}
        self.freq_to_list = {}
        self.min_freq = 0

    def use(self, code):
        node = self.code_to_node.get(code)
        if node is None:
            node = self.Node(code, 1)
            self.code_to_node[code] = node
            if 1 not in self.freq_to_list:
                self.freq_to_list[1] = self.FreqList()
            self.freq_to_list[1].add_to_front(node)
            self.min_freq = 1
        else:
            old_freq = node.freq
            old_list = self.freq_to_list[old_freq]
            old_list.remove(node)

            if old_freq == self.min_freq and old_list.is_empty():
                self.min_freq = old_freq + 1

            node.freq += 1
            if node.freq not in self.freq_to_list:
                self.freq_to_list[node.freq] = self.FreqList()
            self.freq_to_list[node.freq].add_to_front(node)

    def find_lfu(self):
        min_list = self.freq_to_list.get(self.min_freq)
        if min_list is None or min_list.is_empty():
            return -1
        lfu_node = min_list.get_last()
        return lfu_node.code

    def remove(self, code):
        node = self.code_to_node.pop(code, None)
        if node is not None:
            freq_list = self.freq_to_list[node.freq]
            freq_list.remove(node)

def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    alphabet = ALPHABETS[alphabet_name]
    valid_chars = set(alphabet)

    writer = BitWriter(output_file)
    writer.write(min_bits, 8)
    writer.write(max_bits, 8)
    writer.write(len(alphabet), 16)
    for char in alphabet:
        writer.write(ord(char), 8)

    dictionary = {char: i for i, char in enumerate(alphabet)}

    EOF_CODE = len(alphabet)
    next_code = len(alphabet) + 1

    code_bits = min_bits
    max_size = 1 << max_bits
    threshold = 1 << code_bits

    lfu_tracker = LFUTracker(max_size)

    with open(input_file, 'r', encoding='latin-1') as f:
        first_char = f.read(1)

        if not first_char:
            writer.write(EOF_CODE, min_bits)
            writer.close()
            return

        if first_char not in valid_chars:
            raise ValueError(f"Character '{first_char}' at position 0 not in alphabet")

        current = first_char
        pos = 1

        while True:
            char = f.read(1)
            if not char:
                break

            if char not in valid_chars:
                raise ValueError(f"Character '{char}' at position {pos} not in alphabet")
            pos += 1

            combined = current + char

            if combined in dictionary:
                current = combined
            else:
                writer.write(dictionary[current], code_bits)

                if lfu_tracker.contains(current):
                    lfu_tracker.use(current)

                if next_code < max_size:
                    if next_code >= threshold and code_bits < max_bits:
                        code_bits += 1
                        threshold <<= 1

                    if next_code == max_size - 1:
                        lfu_entry = lfu_tracker.find_lfu()
                        if lfu_entry is not None:
                            del dictionary[lfu_entry]
                            lfu_tracker.remove(lfu_entry)

                    dictionary[combined] = next_code
                    lfu_tracker.use(combined)
                    next_code += 1

                current = char

    writer.write(dictionary[current], code_bits)

    if lfu_tracker.contains(current):
        lfu_tracker.use(current)

    if next_code >= threshold and code_bits < max_bits:
        code_bits += 1

    writer.write(EOF_CODE, code_bits)
    writer.close()
    print(f"Compressed: {input_file} -> {output_file}")

def decompress(input_file, output_file):
    reader = BitReader(input_file)

    min_bits = reader.read(8)
    max_bits = reader.read(8)
    alphabet_size = reader.read(16)
    alphabet = [chr(reader.read(8)) for _ in range(alphabet_size)]

    dictionary = {i: char for i, char in enumerate(alphabet)}

    EOF_CODE = alphabet_size
    next_code = alphabet_size + 1

    code_bits = min_bits
    max_size = 1 << max_bits
    threshold = 1 << code_bits

    lfu_tracker = LFUTrackerDecoder(max_size)

    codeword = reader.read(code_bits)

    if codeword is None:
        raise ValueError("Corrupted file: unexpected end of file (no EOF marker)")

    if codeword == EOF_CODE:
        reader.close()
        open(output_file, 'w', encoding='latin-1').close()
        return

    prev = dictionary[codeword]

    with open(output_file, 'w', encoding='latin-1') as out:
        out.write(prev)

        while True:
            if next_code >= threshold and code_bits < max_bits:
                code_bits += 1
                threshold <<= 1

            codeword = reader.read(code_bits)

            if codeword is None:
                raise ValueError("Corrupted file: unexpected end of file (no EOF marker)")

            if codeword == EOF_CODE:
                break

            if codeword in dictionary:
                current = dictionary[codeword]
            elif codeword == next_code:
                current = prev + prev[0]
            else:
                raise ValueError(f"Invalid codeword: {codeword}")

            out.write(current)

            if next_code < max_size:
                if next_code == max_size - 1:
                    lfu_code = lfu_tracker.find_lfu()
                    if lfu_code != -1:
                        dictionary[lfu_code] = None
                        lfu_tracker.remove(lfu_code)

                dictionary[next_code] = prev + current[0]
                lfu_tracker.use(next_code)
                next_code += 1

            if codeword >= alphabet_size + 1:
                lfu_tracker.use(codeword)

            prev = current

    reader.close()
    print(f"Decompressed: {input_file} -> {output_file}")

def main():
    parser = argparse.ArgumentParser(description='LZW compression (LFU mode)')
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

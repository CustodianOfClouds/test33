#!/usr/bin/env python3
"""Check where encoder and decoder get out of sync"""

import subprocess

# Create test file
with open('test_sync.txt', 'w') as f:
    f.write('ab' * 40)

# Run encoder
subprocess.run([
    'python3', 'lzw_lru.py', 'compress',
    'test_sync.txt', 'test_sync.lzw',
    '--alphabet', 'ab',
    '--min-bits', '3',
    '--max-bits', '4',
    '--log'
], capture_output=True, text=True, stdout=open('enc_sync.log', 'w'))

# Run decoder  
subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'test_sync.lzw', 'test_sync_out.txt',
    '--log'
], capture_output=True, text=True, stdout=open('dec_sync.log', 'w'))

# Extract encode/decode pairs
enc_lines = open('enc_sync.log').read().split('\n')
dec_lines = open('dec_sync.log').read().split('\n')

enc_outputs = [(i, l) for i, l in enumerate(enc_lines) if '[ENCODE] Output code' in l]
dec_reads = [(i, l) for i, l in enumerate(dec_lines) if '[DECODE] Read code' in l]

print("Comparing encoder output vs decoder input:\n")
for i in range(min(len(enc_outputs), len(dec_reads))):
    enc_idx, enc_line = enc_outputs[i]
    dec_idx, dec_line = dec_reads[i]
    
    # Extract code numbers
    enc_code = enc_line.split('code ')[1].split(' ')[0]
    dec_code = dec_line.split('code ')[1].split(' ')[0]
    
    match = "✓" if enc_code == dec_code else "❌"
    print(f"{i+1:2d}. Enc={enc_code:3s} Dec={dec_code:3s} {match}")
    
    if enc_code != dec_code:
        print(f"    MISMATCH at position {i+1}!")
        print(f"    Encoder: {enc_line}")
        print(f"    Decoder: {dec_line}")
        # Show context
        print("\n    Encoder context:")
        for j in range(max(0, enc_idx-3), min(len(enc_lines), enc_idx+4)):
            print(f"      {enc_lines[j]}")
        print("\n    Decoder context:")
        for j in range(max(0, dec_idx-3), min(len(dec_lines), dec_idx+4)):
            print(f"      {dec_lines[j]}")
        break

if len(dec_reads) > len(enc_outputs):
    print(f"\n❌ Decoder read {len(dec_reads) - len(enc_outputs)} extra code(s)!")
    for i in range(len(enc_outputs), len(dec_reads)):
        print(f"    Extra: {dec_reads[i][1]}")

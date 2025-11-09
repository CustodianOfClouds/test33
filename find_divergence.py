#!/usr/bin/env python3
"""
Find where encoder and decoder dictionaries diverge
"""

import subprocess
import sys

# Create small test file
test_data = "abcdefgh" * 50  # 400 bytes
with open('test_diverge.txt', 'w') as f:
    f.write(test_data)

print("Testing with 400-byte file...")
print()

# Compress with full version (always signals)
subprocess.run([
    'python3', 'lzw_lru.py', 'compress',
    'test_diverge.txt', 'test_diverge_full.lzw',
    '--alphabet', 'extendedascii',
    '--max-bits', '9',
    '--debug'
], stdout=open('enc_full_diverge.log', 'w'), stderr=subprocess.STDOUT)

# Decompress with full version
subprocess.run([
    'python3', 'lzw_lru.py', 'decompress',
    'test_diverge_full.lzw', 'test_diverge_full_dec.txt',
    '--debug'
], stdout=open('dec_full_diverge.log', 'w'), stderr=subprocess.STDOUT)

# Compress with optimized version
subprocess.run([
    'python3', 'lzw_lru_optimized.py', 'compress',
    'test_diverge.txt', 'test_diverge_opt.lzw',
    '--alphabet', 'extendedascii',
    '--max-bits', '9',
    '--debug'
], stdout=open('enc_opt_diverge.log', 'w'), stderr=subprocess.STDOUT)

# Decompress with optimized version
subprocess.run([
    'python3', 'lzw_lru_optimized.py', 'decompress',
    'test_diverge_opt.lzw', 'test_diverge_opt_dec.txt',
    '--debug'
], stdout=open('dec_opt_diverge.log', 'w'), stderr=subprocess.STDOUT)

# Check results
result_full = subprocess.run(['diff', '-q', 'test_diverge.txt', 'test_diverge_full_dec.txt'],
                             capture_output=True)
result_opt = subprocess.run(['diff', '-q', 'test_diverge.txt', 'test_diverge_opt_dec.txt'],
                            capture_output=True)

print(f"Full version: {'PASS' if result_full.returncode == 0 else 'FAIL'}")
print(f"Optimized version: {'PASS' if result_opt.returncode == 0 else 'FAIL'}")
print()

if result_opt.returncode != 0:
    print("Optimized version failed! Analyzing logs...")
    print()

    # Compare encoder outputs
    with open('enc_full_diverge.log') as f:
        full_enc_lines = f.readlines()
    with open('enc_opt_diverge.log') as f:
        opt_enc_lines = f.readlines()

    print(f"Full encoder: {len(full_enc_lines)} log lines")
    print(f"Opt encoder: {len(opt_enc_lines)} log lines")

    # Find first difference in encoder logs
    for i, (full_line, opt_line) in enumerate(zip(full_enc_lines, opt_enc_lines)):
        if full_line != opt_line:
            print(f"\nFirst encoder difference at line {i+1}:")
            print(f"FULL: {full_line.rstrip()}")
            print(f"OPT:  {opt_line.rstrip()}")
            break

    # Compare decoder outputs
    with open('dec_full_diverge.log') as f:
        full_dec_lines = f.readlines()
    with open('dec_opt_diverge.log') as f:
        opt_dec_lines = f.readlines()

    print(f"\nFull decoder: {len(full_dec_lines)} log lines")
    print(f"Opt decoder: {len(opt_dec_lines)} log lines")

    # Find first difference in decoder logs
    for i, (full_line, opt_line) in enumerate(zip(full_dec_lines, opt_dec_lines)):
        if full_line != opt_line:
            print(f"\nFirst decoder difference at line {i+1}:")
            print(f"FULL: {full_line.rstrip()}")
            print(f"OPT:  {opt_line.rstrip()}")
            # Show a few more lines for context
            for j in range(i+1, min(i+5, len(full_dec_lines), len(opt_dec_lines))):
                print(f"FULL: {full_dec_lines[j].rstrip()}")
                print(f"OPT:  {opt_dec_lines[j].rstrip()}")
            break

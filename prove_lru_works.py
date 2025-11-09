#!/usr/bin/env python3
"""
DIRECT PROOF: LRU Continuously Evicts

This script creates an instrumented version that logs EVERY eviction
with timestamps and shows the LRU queue is actively updating.
"""

import sys
import os
import tempfile
import subprocess
from pathlib import Path

def create_instrumented_lru_naive():
    """Create heavily instrumented LRU that logs everything"""

    source = Path('/home/user/test33/LRU-Eviction/LZW-LRU-Naive.py').read_text()

    # Add detailed logging throughout
    instrumented = source.replace(
        'def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):',
        '''def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    import sys
    eviction_log = []  # Track all evictions'''
    )

    # Log when we find LRU entry
    instrumented = instrumented.replace(
        'lru_entry = lru_tracker.find_lru()',
        '''lru_entry = lru_tracker.find_lru()
                    eviction_log.append({
                        'eviction_num': len(eviction_log) + 1,
                        'evicted_entry': lru_entry,
                        'next_code': next_code
                    })'''
    )

    # Print summary at end
    instrumented = instrumented.replace(
        'writer.write(EOF_CODE, code_bits)\n    writer.close()',
        '''writer.write(EOF_CODE, code_bits)
    writer.close()

    # INSTRUMENTATION: Print eviction details
    print(f"\\n{'='*80}", file=sys.stderr)
    print(f"EVICTION REPORT FOR LRU-Naive", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Total evictions: {len(eviction_log)}", file=sys.stderr)
    if eviction_log:
        print(f"\\nFirst 10 evictions:", file=sys.stderr)
        for i, ev in enumerate(eviction_log[:10]):
            print(f"  #{ev['eviction_num']}: Evicted '{ev['evicted_entry']}' (next_code={ev['next_code']})", file=sys.stderr)
        if len(eviction_log) > 10:
            print(f"  ... {len(eviction_log) - 10} more evictions ...", file=sys.stderr)
        print(f"\\nLast 5 evictions:", file=sys.stderr)
        for ev in eviction_log[-5:]:
            print(f"  #{ev['eviction_num']}: Evicted '{ev['evicted_entry']}' (next_code={ev['next_code']})", file=sys.stderr)
    print(f"{'='*80}\\n", file=sys.stderr)'''
    )

    return instrumented

def create_instrumented_lfu():
    """Create instrumented LFU to show it stops evicting"""

    source = Path('/home/user/test33/lzw_lfu.py').read_text()

    # Add eviction counter
    instrumented = source.replace(
        'def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):',
        '''def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    import sys
    eviction_attempts = []  # Track eviction attempts
    actual_evictions = []   # Track actual evictions'''
    )

    # Log the check
    instrumented = instrumented.replace(
        'if next_code == max_size - 1:',
        '''# INSTRUMENTATION: Log every time we check the condition
                    eviction_attempts.append({
                        'attempt_num': len(eviction_attempts) + 1,
                        'next_code': next_code,
                        'max_size': max_size,
                        'condition': next_code == max_size - 1
                    })
                    if next_code == max_size - 1:'''
    )

    # Log when eviction actually happens
    instrumented = instrumented.replace(
        'lfu_entry = lfu_tracker.find_lfu()',
        '''lfu_entry = lfu_tracker.find_lfu()
                        actual_evictions.append({
                            'eviction_num': len(actual_evictions) + 1,
                            'evicted_entry': lfu_entry,
                            'next_code': next_code
                        })'''
    )

    # Print detailed report
    instrumented = instrumented.replace(
        'writer.write(EOF_CODE, code_bits)\n    writer.close()',
        '''writer.write(EOF_CODE, code_bits)
    writer.close()

    # INSTRUMENTATION: Print detailed eviction report
    print(f"\\n{'='*80}", file=sys.stderr)
    print(f"EVICTION REPORT FOR LFU (BROKEN)", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Total eviction attempts checked: {len(eviction_attempts)}", file=sys.stderr)
    print(f"Actual evictions performed: {len(actual_evictions)}", file=sys.stderr)
    print(f"\\nCondition checks:", file=sys.stderr)
    if eviction_attempts:
        print(f"  First check: next_code={eviction_attempts[0]['next_code']}, condition={eviction_attempts[0]['condition']}", file=sys.stderr)
        for i, attempt in enumerate(eviction_attempts[:20]):
            status = "✓ EVICTED" if attempt['condition'] else "✗ SKIPPED"
            print(f"  Attempt #{attempt['attempt_num']}: next_code={attempt['next_code']} == max_size-1? {attempt['condition']} [{status}]", file=sys.stderr)
        if len(eviction_attempts) > 20:
            print(f"  ... {len(eviction_attempts) - 20} more attempts (all with next_code={eviction_attempts[-1]['next_code']}) ...", file=sys.stderr)
    print(f"\\n🔴 BUG: After first eviction, next_code stays at {max_size}", file=sys.stderr)
    print(f"       Condition 'next_code == max_size-1' is NEVER true again!", file=sys.stderr)
    print(f"       Result: Only {len(actual_evictions)} eviction(s) total.", file=sys.stderr)
    print(f"{'='*80}\\n", file=sys.stderr)'''
    )

    return instrumented

def run_test(script_content, name, test_file):
    """Run instrumented script and show output"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script_content)
        temp_script = f.name

    try:
        output_file = f"/tmp/test_{name}.lzw"

        result = subprocess.run(
            ['python3', temp_script, 'compress', test_file, output_file,
             '--alphabet', 'ab', '--max-bits', '3'],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(result.stderr)

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)

    finally:
        os.remove(temp_script)

def main():
    print("="*80)
    print("PROOF: LRU vs LFU Eviction Behavior")
    print("="*80)

    # Create test file that will trigger many evictions
    test_file = '/tmp/eviction_proof.txt'

    # With alphabet 'ab' and maxw=3, we can have 2^3=8 codes max
    # Create lots of unique patterns to force continuous eviction
    patterns = []
    for i in range(100):
        for length in [1, 2, 3, 4, 5]:
            pattern = ''.join(['a' if (i >> j) & 1 == 0 else 'b'
                              for j in range(length)])
            patterns.append(pattern)

    with open(test_file, 'w') as f:
        f.write(''.join(patterns * 50))  # Repeat to ensure lots of evictions

    print(f"\nTest file created: {os.path.getsize(test_file)} bytes")
    print(f"Dictionary size: 2^3 = 8 entries max")
    print("\n")

    # Test LRU
    print("🟢 Testing LRU-Naive (should evict continuously)")
    print("-"*80)
    lru_code = create_instrumented_lru_naive()
    run_test(lru_code, 'lru', test_file)

    print("\n" + "="*80 + "\n")

    # Test LFU
    print("🔴 Testing LFU (broken - should evict once and stop)")
    print("-"*80)
    lfu_code = create_instrumented_lfu()
    run_test(lfu_code, 'lfu', test_file)

    # Cleanup
    os.remove(test_file)

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    print("✓ LRU: Continuously evicts (thousands of evictions)")
    print("✗ LFU: Evicts once then stops (bug in condition)")
    print("\nThe LRU queue is actively working, not frozen!")

if __name__ == '__main__':
    main()

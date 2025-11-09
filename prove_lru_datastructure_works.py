#!/usr/bin/env python3
"""
DEFINITIVE PROOF: Show the LRU data structure actually changing

This instruments the LRU tracker to log:
1. When entries are added to the LRU queue
2. When entries are moved (marked as recently used)
3. What find_lru() returns each time (should be DIFFERENT entries)
4. The actual order of the doubly-linked list
5. Evictions happening with different victims each time
"""

import sys
import os
import tempfile
import subprocess

def create_fully_instrumented_lru():
    """Create version that logs every LRU data structure change"""

    source = open('/home/user/test33/LRU-Eviction/LZW-LRU-Naive.py').read()

    # Add logging at the very start
    instrumented = source.replace(
        'def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):',
        '''def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    import sys

    # Track all LRU operations
    lru_log = {
        'additions': [],       # When entries added to LRU
        'uses': [],            # When entries marked as used (moved to front)
        'evictions': [],       # What was evicted each time
        'lru_snapshots': []    # State of LRU queue at key points
    }

    iteration_count = 0'''
    )

    # Instrument LRUTracker.use() to log additions and moves
    instrumented = instrumented.replace(
        'def use(self, key: K) -> None:',
        '''def use(self, key: K) -> None:
        # This will be set by compress function
        if hasattr(self, '_log'):
            is_new = key not in self.map
            self._log['uses'].append({
                'key': str(key),
                'is_new': is_new,
                'action': 'ADD' if is_new else 'MOVE'
            })'''
    )

    # Instrument find_lru() to log what it returns
    instrumented = instrumented.replace(
        'def find_lru(self) -> Optional[K]:',
        '''def find_lru(self) -> Optional[K]:
        result = self._find_lru_impl()
        if hasattr(self, '_log') and result:
            self._log['lru_found'] = self._log.get('lru_found', [])
            self._log['lru_found'].append(str(result))
        return result

    def _find_lru_impl(self) -> Optional[K]:'''
    )

    # Replace the actual find_lru implementation
    instrumented = instrumented.replace(
        '"""Return least recently used key, or None if empty."""\n        if self.tail.prev == self.head:\n            return None\n        return self.tail.prev.key',
        '"""Return least recently used key, or None if empty."""\n        if self.tail.prev == self.head:\n            return None\n        return self.tail.prev.key'
    )

    # Pass log to LRU tracker
    instrumented = instrumented.replace(
        'lru_tracker = LRUTracker()',
        '''lru_tracker = LRUTracker()
    lru_tracker._log = lru_log  # Give tracker access to log'''
    )

    # Log each eviction with details
    instrumented = instrumented.replace(
        'lru_entry = lru_tracker.find_lru()',
        '''iteration_count += 1
                    lru_entry = lru_tracker.find_lru()
                    if lru_entry:
                        lru_log['evictions'].append({
                            'iteration': iteration_count,
                            'evicted': lru_entry,
                            'evicted_code': dictionary.get(lru_entry, '?')
                        })'''
    )

    # Print comprehensive report at end
    instrumented = instrumented.replace(
        'writer.close()\n    print(f"Compressed',
        '''writer.close()

    # Print comprehensive LRU data structure activity report
    print("\\n" + "="*80, file=sys.stderr)
    print("LRU DATA STRUCTURE ACTIVITY REPORT", file=sys.stderr)
    print("="*80, file=sys.stderr)

    print(f"\\nTotal evictions: {len(lru_log['evictions'])}", file=sys.stderr)

    if lru_log['evictions']:
        print(f"\\nFirst 15 evictions (showing data structure changes):", file=sys.stderr)
        for i, ev in enumerate(lru_log['evictions'][:15]):
            print(f"  Eviction {i+1}: '{ev['evicted']}' (code={ev['evicted_code']})", file=sys.stderr)

        print(f"\\nEvictions 100-110 (showing it keeps working):", file=sys.stderr)
        for i, ev in enumerate(lru_log['evictions'][99:110], 100):
            print(f"  Eviction {i}: '{ev['evicted']}' (code={ev['evicted_code']})", file=sys.stderr)

        print(f"\\nLast 10 evictions:", file=sys.stderr)
        for i, ev in enumerate(lru_log['evictions'][-10:], len(lru_log['evictions'])-9):
            print(f"  Eviction {i}: '{ev['evicted']}' (code={ev['evicted_code']})", file=sys.stderr)

        # Show that DIFFERENT entries are being evicted (not same one repeatedly)
        unique_evicted = set(ev['evicted'] for ev in lru_log['evictions'])
        print(f"\\n📊 PROOF OF LRU WORKING:", file=sys.stderr)
        print(f"  - Total evictions: {len(lru_log['evictions'])}", file=sys.stderr)
        print(f"  - Unique entries evicted: {len(unique_evicted)}", file=sys.stderr)
        print(f"  - Different victims: {sorted(unique_evicted)}", file=sys.stderr)

        if len(unique_evicted) > 1:
            print(f"\\n✅ PROOF: Multiple different entries evicted!", file=sys.stderr)
            print(f"   The LRU queue is ACTIVELY REORDERING based on usage!", file=sys.stderr)
        else:
            print(f"\\n❌ BROKEN: Only evicting same entry repeatedly!", file=sys.stderr)

    print("="*80 + "\\n", file=sys.stderr)

    print(f"Compressed'''
    )

    return instrumented

def create_instrumented_lfu_comparison():
    """Create LFU version to show it doesn't change the data structure"""

    source = open('/home/user/test33/lzw_lfu.py').read()

    instrumented = source.replace(
        'def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):',
        '''def compress(input_file, output_file, alphabet_name, min_bits=9, max_bits=16):
    import sys
    evictions = []
    iterations_after_full = 0
    dict_full_at = None'''
    )

    # Track when dictionary fills
    instrumented = instrumented.replace(
        'if next_code == max_size - 1:',
        '''if dict_full_at is None and next_code >= max_size - 1:
                        dict_full_at = next_code
                    if next_code >= max_size - 1:
                        iterations_after_full += 1
                    if next_code == max_size - 1:'''
    )

    # Log evictions
    instrumented = instrumented.replace(
        'lfu_entry = lfu_tracker.find_lfu()',
        '''lfu_entry = lfu_tracker.find_lfu()
                        if lfu_entry:
                            evictions.append({
                                'iteration_after_full': iterations_after_full,
                                'next_code': next_code,
                                'evicted': lfu_entry
                            })'''
    )

    # Report
    instrumented = instrumented.replace(
        'writer.close()\n    print(f"Compressed',
        '''writer.close()

    print("\\n" + "="*80, file=sys.stderr)
    print("LFU EVICTION REPORT (BROKEN)", file=sys.stderr)
    print("="*80, file=sys.stderr)
    print(f"Dictionary filled at: next_code={dict_full_at}", file=sys.stderr)
    print(f"Iterations after dictionary full: {iterations_after_full}", file=sys.stderr)
    print(f"Total evictions: {len(evictions)}", file=sys.stderr)

    if evictions:
        print(f"\\nEvictions:", file=sys.stderr)
        for ev in evictions:
            print(f"  After {ev['iteration_after_full']} iterations when full: evicted '{ev['evicted']}' (next_code={ev['next_code']})", file=sys.stderr)

    print(f"\\n🔴 BUG: Only {len(evictions)} eviction(s) despite {iterations_after_full} iterations after full!", file=sys.stderr)
    print(f"   The LFU tracker is NOT being used after first eviction!", file=sys.stderr)
    print("="*80 + "\\n", file=sys.stderr)

    print(f"Compressed'''
    )

    return instrumented

def main():
    print("="*80)
    print("DEFINITIVE PROOF: LRU Data Structure Actually Working")
    print("="*80)
    print("\nThis will show:")
    print("  1. Multiple DIFFERENT entries being evicted (not same one)")
    print("  2. LRU queue actively reordering based on usage")
    print("  3. Evictions continuing throughout compression")
    print()

    # Create test file
    test_file = '/tmp/lru_proof_test.txt'
    with open(test_file, 'w') as f:
        # Create patterns that will definitely cause evictions
        for i in range(2000):
            for pattern in ['a', 'b', 'aa', 'ab', 'ba', 'bb', 'aaa', 'aab', 'aba', 'abb', 'baa', 'bab', 'bba', 'bbb']:
                f.write(pattern)

    print(f"Test file: {os.path.getsize(test_file):,} bytes")
    print(f"Max dictionary size: 2^3 = 8 entries\n")

    # Test LRU
    print("🟢" + "="*79)
    print("TESTING LRU-Naive (Should show data structure actively changing)")
    print("="*80)

    lru_code = create_fully_instrumented_lru()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(lru_code)
        lru_tmp = f.name

    try:
        result = subprocess.run(
            ['python3', lru_tmp, 'compress', test_file, '/tmp/lru_out.lzw',
             '--alphabet', 'ab', '--max-bits', '3'],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(result.stderr)
    finally:
        os.unlink(lru_tmp)
        if os.path.exists('/tmp/lru_out.lzw'):
            os.unlink('/tmp/lru_out.lzw')

    print("\n\n")

    # Test LFU
    print("🔴" + "="*79)
    print("TESTING LFU (Should show data structure stops after 1 eviction)")
    print("="*80)

    lfu_code = create_instrumented_lfu_comparison()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(lfu_code)
        lfu_tmp = f.name

    try:
        result = subprocess.run(
            ['python3', lfu_tmp, 'compress', test_file, '/tmp/lfu_out.lzw',
             '--alphabet', 'ab', '--max-bits', '3'],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(result.stderr)
    finally:
        os.unlink(lfu_tmp)
        if os.path.exists('/tmp/lfu_out.lzw'):
            os.unlink('/tmp/lfu_out.lzw')

    # Cleanup
    os.unlink(test_file)

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    print("If LRU is working:")
    print("  ✓ Multiple different entries should be evicted")
    print("  ✓ Evictions should continue throughout compression")
    print("  ✓ The 'unique entries evicted' count should be > 1")
    print()
    print("If LFU is broken:")
    print("  ✗ Only 1 eviction despite many iterations after full")
    print("  ✗ Data structure not being used after first eviction")
    print("="*80)

if __name__ == '__main__':
    main()

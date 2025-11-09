#!/usr/bin/env python3
"""
VERIFY: Evictions are actually the LEAST RECENTLY USED entry

This shows:
1. The order of the LRU queue (from most to least recently used)
2. What entry gets evicted
3. That it's always the LAST entry in the queue (the LRU)
"""

import tempfile
import subprocess
import os

def create_instrumented_lru_with_queue_display():
    """Instrument LRU to show queue order and prove it evicts from the tail"""

    with open('/home/user/test33/LRU-Eviction/LZW-LRU-Naive.py') as f:
        code = f.read()

    # Add method to LRUTracker to show queue order
    instrumented = code.replace(
        'def _remove_node(self, node: \'LRUTracker.Node\') -> None:',
        '''def get_queue_order(self) -> list:
        """Get queue from MRU to LRU (head to tail)"""
        result = []
        current = self.head.next
        while current != self.tail:
            result.append(str(current.key))
            current = current.next
        return result

    def _remove_node(self, node: \'LRUTracker.Node\') -> None:'''
    )

    # Add logging when we evict
    instrumented = instrumented.replace(
        'lru_entry = lru_tracker.find_lru()',
        '''lru_entry = lru_tracker.find_lru()

                    # Show queue state before eviction
                    if lru_entry:
                        queue_order = lru_tracker.get_queue_order()
                        import sys
                        sys.stderr.write(f"\\nBefore eviction:\\n")
                        sys.stderr.write(f"  Queue (MRU→LRU): {' → '.join(queue_order)}\\n")
                        sys.stderr.write(f"  Will evict: '{lru_entry}'\\n")

                        # Verify it's actually the last one
                        if queue_order and queue_order[-1] == lru_entry:
                            sys.stderr.write(f"  ✅ CORRECT: '{lru_entry}' is at the END (least recently used)\\n")
                        else:
                            sys.stderr.write(f"  ❌ ERROR: '{lru_entry}' is NOT the LRU!\\n")

                        sys.stderr.flush()

                        # Count evictions
                        global _evict_count
                        _evict_count = globals().get('_evict_count', 0) + 1
                        if _evict_count >= 20:  # Only show first 20
                            sys.stderr.write(f"\\n... (stopping display after 20 evictions) ...\\n")
                            sys.exit(0)'''
    )

    return instrumented

def main():
    print("="*80)
    print("VERIFY: LRU Eviction is Actually Least Recently Used")
    print("="*80)
    print("\nThis will show:")
    print("  1. The order of entries in the LRU queue")
    print("  2. Which entry gets evicted")
    print("  3. Proof that it's the LAST entry (least recently used)")
    print()
    print("Note: Showing first 20 evictions for clarity")
    print("="*80)

    # Create instrumented version
    code = create_instrumented_lru_with_queue_display()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp_file = f.name

    # Create test file
    test_file = '/tmp/lru_verify.txt'
    with open(test_file, 'w') as f:
        # Create patterns that will trigger evictions
        for i in range(100):
            for pattern in ['a', 'b', 'aa', 'ab', 'ba', 'bb', 'aaa', 'bbb']:
                f.write(pattern)

    print(f"\nTest file: {os.path.getsize(test_file):,} bytes")
    print(f"Dictionary size: 8 entries (maxw=3)")
    print()

    # Run
    result = subprocess.run(
        ['python3', tmp_file, 'compress', test_file, '/tmp/out.lzw',
         '--alphabet', 'ab', '--max-bits', '3'],
        capture_output=True,
        text=True,
        timeout=30
    )

    print(result.stderr)

    # Cleanup
    os.unlink(tmp_file)
    os.unlink(test_file)
    if os.path.exists('/tmp/out.lzw'):
        os.unlink('/tmp/out.lzw')

    print()
    print("="*80)
    print("CONCLUSION")
    print("="*80)
    print("If the evicted entry is always the LAST in the queue,")
    print("then the LRU implementation is CORRECTLY evicting the")
    print("least recently used entry (not random)!")
    print("="*80)

if __name__ == '__main__':
    main()

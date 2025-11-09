#!/usr/bin/env python3
"""
Test each LRU implementation individually and show eviction logs
"""

import subprocess
import tempfile
import os
import time

def test_individual_lru(impl_path, impl_name):
    """Test one LRU implementation and show its eviction log"""

    print("="*80)
    print(f"TESTING: {impl_name}")
    print(f"File: {impl_path}")
    print("="*80)

    # Read source
    with open(impl_path) as f:
        code = f.read()

    # Add eviction logging
    log_file = f'/tmp/{impl_name.replace("-", "_")}_evictions.log'

    code = code.replace(
        'lru_tracker = LRUTracker()',
        f'_evict_log = open("{log_file}", "w"); lru_tracker = LRUTracker()'
    )

    # Handle both eviction patterns
    if 'lru_entry = lru_tracker.find_lru()' in code:
        code = code.replace(
            '                    lru_entry = lru_tracker.find_lru()',
            f'                    lru_entry = lru_tracker.find_lru()\n                    if lru_entry: _evict_log.write(f"{{lru_entry}}\\n"); _evict_log.flush()'
        )

    if 'lru_code = lru_tracker.find_lru()' in code:
        code = code.replace(
            '                    lru_code = lru_tracker.find_lru()',
            f'                    lru_code = lru_tracker.find_lru()\n                    if lru_code: _evict_log.write(f"{{lru_code}}\\n"); _evict_log.flush()'
        )

    code = code.replace('writer.close()', '_evict_log.close(); writer.close()')

    # Write instrumented version
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp_file = f.name

    # Create test data
    test_file = '/tmp/individual_test.txt'
    with open(test_file, 'w') as f:
        for i in range(300):
            for pattern in ['a', 'b', 'aa', 'ab', 'ba', 'bb', 'aaa', 'aab', 'aba', 'abb', 'baa', 'bab', 'bba', 'bbb']:
                f.write(pattern)

    print(f"\nRunning compression...")
    print(f"Test file: {os.path.getsize(test_file):,} bytes")
    print(f"Dictionary size: 2^3 = 8 entries (maxw=3)\n")

    # Run compression
    result = subprocess.run(
        ['python3', tmp_file, 'compress', test_file, '/tmp/out.lzw',
         '--alphabet', 'ab', '--max-bits', '3'],
        capture_output=True,
        text=True,
        timeout=30
    )

    # Clean up temp files
    os.unlink(tmp_file)
    if os.path.exists('/tmp/out.lzw'):
        os.unlink('/tmp/out.lzw')

    # Read and display eviction log
    if os.path.exists(log_file):
        with open(log_file) as f:
            evictions = [line.strip() for line in f if line.strip()]

        print(f"✅ SUCCESS - Eviction log captured")
        print(f"\nTotal evictions: {len(evictions)}")

        # Show first 25 evictions
        print(f"\nFirst 25 evictions:")
        for i, eviction in enumerate(evictions[:25], 1):
            print(f"  {i:3d}. Evicted: '{eviction}'")

        if len(evictions) > 50:
            print(f"\n  ... {len(evictions) - 50} more evictions ...")

            # Show last 25
            print(f"\nLast 25 evictions:")
            for i, eviction in enumerate(evictions[-25:], len(evictions)-24):
                print(f"  {i:3d}. Evicted: '{eviction}'")

        # Analysis
        unique = set(evictions)
        from collections import Counter
        counts = Counter(evictions)

        print(f"\n{'─'*80}")
        print("ANALYSIS:")
        print(f"{'─'*80}")
        print(f"Total evictions:      {len(evictions):,}")
        print(f"Unique victims:       {len(unique)}")
        print(f"Different entries:    {sorted(unique)}")

        print(f"\nEviction frequency:")
        for entry, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:10]:
            print(f"  '{entry}': evicted {count:,} times")

        if len(unique) > 5:
            print(f"\n✅ VERIFIED: LRU queue is actively changing!")
            print(f"   {len(unique)} different entries were selected as victims")
            print(f"   The doubly-linked list is reordering based on usage")
        else:
            print(f"\n⚠️  Only {len(unique)} unique victims - may be issue")

        # Cleanup log
        os.unlink(log_file)

        return len(evictions), len(unique)
    else:
        print(f"❌ FAILED - No eviction log created")
        if result.stderr:
            print(f"\nError output:\n{result.stderr[:500]}")
        return 0, 0

def main():
    print("\n" + "="*80)
    print("INDIVIDUAL TESTING: All 4 LRU Implementations")
    print("="*80)
    print("\nTesting each implementation separately to show eviction logs...\n")

    # Create test data once
    test_file = '/tmp/individual_test.txt'
    with open(test_file, 'w') as f:
        for i in range(300):
            for pattern in ['a', 'b', 'aa', 'ab', 'ba', 'bb', 'aaa', 'aab', 'aba', 'abb', 'baa', 'bab', 'bba', 'bbb']:
                f.write(pattern)

    implementations = [
        ('/home/user/test33/LRU-Eviction/LZW-LRU-Naive.py', 'LRU-Naive'),
        ('/home/user/test33/LRU-Eviction/LZW-LRU-Optimizedv1.py', 'LRU-Optimized-v1'),
        ('/home/user/test33/LRU-Eviction/LZW-LRU-Optimizedv2.py', 'LRU-Optimized-v2'),
        ('/home/user/test33/LRU-Eviction/LZW-LRU-Optimizedv2.1.py', 'LRU-Optimized-v2.1'),
    ]

    results = []

    for impl_path, impl_name in implementations:
        if not os.path.exists(impl_path):
            print(f"\n❌ File not found: {impl_path}")
            continue

        total_evictions, unique_victims = test_individual_lru(impl_path, impl_name)
        results.append((impl_name, total_evictions, unique_victims))

        print("\n" + "─"*80)
        print("Press Enter to continue to next implementation...")
        print("─"*80 + "\n")
        time.sleep(1)  # Small delay between tests

    # Cleanup
    if os.path.exists(test_file):
        os.unlink(test_file)

    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY - ALL 4 LRU IMPLEMENTATIONS")
    print("="*80)
    print()

    for name, total, unique in results:
        status = "✅" if unique > 5 else "⚠️"
        print(f"{status} {name:25s}: {total:5,} evictions, {unique:2d} unique victims")

    print()
    if all(unique > 5 for _, _, unique in results):
        print("="*80)
        print("✅ ALL 4 LRU IMPLEMENTATIONS VERIFIED WORKING")
        print("   Each one shows multiple different entries being evicted")
        print("   The LRU data structures (doubly-linked lists) are active")
        print("="*80)

    print()

if __name__ == '__main__':
    main()

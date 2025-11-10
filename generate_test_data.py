#!/usr/bin/env python3
"""Generate test data files for benchmarking."""

import random
import os

def generate_ab_repetitive(output_file, num_repetitions=250000):
    """Generate a file with repetitive 'ab' pattern."""
    print(f"Generating {output_file} with {num_repetitions} 'ab' repetitions...")
    with open(output_file, 'w') as f:
        f.write('ab' * num_repetitions)
    size = os.path.getsize(output_file)
    print(f"  Created: {size:,} bytes ({size / 1024:.2f} KB)")

def generate_ab_random(output_file, size_bytes=500000):
    """Generate a file with random 'a' and 'b' characters."""
    print(f"Generating {output_file} with {size_bytes} random a/b characters...")
    with open(output_file, 'w') as f:
        for _ in range(size_bytes):
            f.write(random.choice('ab'))
    actual_size = os.path.getsize(output_file)
    print(f"  Created: {actual_size:,} bytes ({actual_size / 1024:.2f} KB)")

def main():
    """Generate all test data files."""
    os.makedirs('test_data', exist_ok=True)

    # Generate repetitive ab pattern (250k repetitions = 500KB)
    generate_ab_repetitive('test_data/ab_repeat_250k.txt', num_repetitions=250000)

    # Generate random ab pattern (500KB)
    generate_ab_random('test_data/ab_random_500k.txt', size_bytes=500000)

    print("\nTest data generation complete!")

if __name__ == '__main__':
    main()

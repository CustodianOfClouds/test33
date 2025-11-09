#!/usr/bin/env python3
"""Compare decoder internal states between full and optimized versions."""

import re
import sys

def parse_decoder_state(log_file):
    """Extract decoder state at each step."""
    states = []
    current_state = {}
    
    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Track READ operations
            if '[DEC #' in line and 'READ code=' in line:
                step_match = re.search(r'\[DEC #(\d+)\]', line)
                code_match = re.search(r'READ code=(\d+)', line)
                value_match = re.search(r"-> '([^']*)'", line)
                
                if step_match and code_match:
                    step = int(step_match.group(1))
                    code = int(code_match.group(1))
                    value = value_match.group(1) if value_match else "?"
                    
                    current_state = {
                        'step': step,
                        'action': 'READ',
                        'code': code,
                        'value': value,
                        'special': 'special case' in line
                    }
                    states.append(current_state.copy())
            
            # Track ADDED operations
            elif 'ADDED code=' in line:
                code_match = re.search(r'ADDED code=(\d+)', line)
                value_match = re.search(r"-> '([^']*)'", line)
                
                if code_match and value_match:
                    states.append({
                        'step': current_state.get('step', -1),
                        'action': 'ADDED',
                        'code': int(code_match.group(1)),
                        'value': value_match.group(1)
                    })
            
            # Track EVICTING operations
            elif 'EVICTING code=' in line:
                code_match = re.search(r'EVICTING code=(\d+)', line)
                value_match = re.search(r"-> '([^']*)'", line)
                
                if code_match and value_match:
                    states.append({
                        'step': current_state.get('step', -1),
                        'action': 'EVICTING',
                        'code': int(code_match.group(1)),
                        'value': value_match.group(1)
                    })
            
            # Track signal reception
            elif 'EVICT_SIGNAL received' in line:
                states.append({
                    'step': current_state.get('step', -1),
                    'action': 'SIGNAL',
                    'code': -1,
                    'value': 'signal'
                })
            
            # Track signal details
            elif 'Signal: code=' in line:
                code_match = re.search(r'Signal: code=(\d+)', line)
                value_match = re.search(r"-> '([^']*)'", line)
                
                if code_match and value_match:
                    if states and states[-1]['action'] == 'SIGNAL':
                        states[-1]['code'] = int(code_match.group(1))
                        states[-1]['value'] = value_match.group(1)
    
    return states

def compare_states(full_states, opt_states):
    """Compare states and find first divergence."""
    print("=" * 100)
    print(f"{'Step':<6} {'Action':<10} {'Full Code':<10} {'Full Value':<20} {'Opt Code':<10} {'Opt Value':<20} {'Match'}")
    print("=" * 100)
    
    max_len = max(len(full_states), len(opt_states))
    first_mismatch = None
    
    for i in range(max_len):
        if i >= len(full_states):
            o = opt_states[i]
            print(f"{'N/A':<6} {o['action']:<10} {'N/A':<10} {'N/A':<20} {o['code']:<10} {o['value']:<20} ✗ (opt has extra)")
            if first_mismatch is None:
                first_mismatch = i
            continue
        
        if i >= len(opt_states):
            f = full_states[i]
            print(f"{f.get('step', 'N/A'):<6} {f['action']:<10} {f['code']:<10} {f['value']:<20} {'N/A':<10} {'N/A':<20} ✗ (full has extra)")
            if first_mismatch is None:
                first_mismatch = i
            continue
        
        f = full_states[i]
        o = opt_states[i]
        
        match = (f['action'] == o['action'] and 
                f['code'] == o['code'] and 
                f['value'] == o['value'])
        
        status = "✓" if match else "✗"
        
        print(f"{f.get('step', o.get('step', 'N/A')):<6} {f['action']:<10} {f['code']:<10} {f['value']:<20} {o['code']:<10} {o['value']:<20} {status}")
        
        if not match and first_mismatch is None:
            first_mismatch = i
            print(f"\n{'':6} ^^^ FIRST MISMATCH at index {i}")
            print(f"{'':6} Full: {f}")
            print(f"{'':6} Opt:  {o}\n")
    
    print("=" * 100)
    print(f"Full states: {len(full_states)}, Optimized states: {len(opt_states)}")
    if first_mismatch is not None:
        print(f"First mismatch at index: {first_mismatch}")
    else:
        print("No mismatches found!")
    
    return first_mismatch

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: compare_decoders.py <full_log> <opt_log>")
        sys.exit(1)
    
    full_log = sys.argv[1]
    opt_log = sys.argv[2]
    
    print(f"Parsing {full_log}...")
    full_states = parse_decoder_state(full_log)
    
    print(f"Parsing {opt_log}...")
    opt_states = parse_decoder_state(opt_log)
    
    print(f"\nComparing {len(full_states)} full states with {len(opt_states)} optimized states...\n")
    
    compare_states(full_states, opt_states)

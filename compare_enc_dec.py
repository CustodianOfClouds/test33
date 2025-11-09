#!/usr/bin/env python3
"""Compare encoder outputs with decoder inputs."""

import re

def parse_encoder_outputs(log_file):
    """Extract encoder outputs."""
    outputs = []
    with open(log_file, 'r') as f:
        for line in f:
            if '[ENC #' in line and 'OUTPUT code=' in line:
                step_match = re.search(r'\[ENC #(\d+)\]', line)
                code_match = re.search(r'OUTPUT code=(\d+)', line)
                value_match = re.search(r"for '([^']*)'", line)
                
                if step_match and code_match and value_match:
                    outputs.append({
                        'step': int(step_match.group(1)),
                        'code': int(code_match.group(1)),
                        'value': value_match.group(1)
                    })
            elif 'Signal sent for code=' in line:
                code_match = re.search(r'code=(\d+)', line)
                value_match = re.search(r"-> '([^']*)'", line)
                
                if code_match and value_match:
                    outputs.append({
                        'step': -1,
                        'code': int(code_match.group(1)),
                        'value': value_match.group(1),
                        'signal': True
                    })
    return outputs

def parse_decoder_inputs(log_file):
    """Extract decoder inputs."""
    inputs = []
    with open(log_file, 'r') as f:
        for line in f:
            if '[DEC #' in line and 'READ code=' in line:
                step_match = re.search(r'\[DEC #(\d+)\]', line)
                code_match = re.search(r'READ code=(\d+)', line)
                value_match = re.search(r"-> '([^']*)'", line)
                
                if step_match and code_match and value_match:
                    inputs.append({
                        'step': int(step_match.group(1)),
                        'code': int(code_match.group(1)),
                        'value': value_match.group(1)
                    })
            elif 'Signal: code=' in line:
                code_match = re.search(r'code=(\d+)', line)
                value_match = re.search(r"-> '([^']*)'", line)
                
                if code_match and value_match:
                    inputs.append({
                        'step': -1,
                        'code': int(code_match.group(1)),
                        'value': value_match.group(1),
                        'signal': True
                    })
    return inputs

enc_outputs = parse_encoder_outputs('enc_opt.log')
dec_inputs = parse_decoder_inputs('dec_opt.log')

print(f"Encoder outputs: {len(enc_outputs)}")
print(f"Decoder inputs: {len(dec_inputs)}")
print()

print(f"{'Step':<6} {'Enc Code':<10} {'Enc Value':<20} {'Dec Code':<10} {'Dec Value':<20} {'Match'}")
print("=" * 90)

for i in range(min(len(enc_outputs), len(dec_inputs))):
    e = enc_outputs[i]
    d = dec_inputs[i]
    
    match = (e['code'] == d['code'] and e['value'] == d['value'])
    status = "✓" if match else "✗"
    
    e_step = f"{e['step']}" if e['step'] != -1 else "SIG"
    d_step = f"{d['step']}" if d['step'] != -1 else "SIG"
    
    print(f"{e_step:<6} {e['code']:<10} {e['value']:<20} {d['code']:<10} {d['value']:<20} {status}")
    
    if not match:
        print(f"\n  ^^^ MISMATCH at index {i}")
        print(f"  Encoder: {e}")
        print(f"  Decoder: {d}\n")
        break

print("\nShowing next few operations from encoder:")
for i in range(i, min(i+10, len(enc_outputs))):
    e = enc_outputs[i]
    sig = " (SIGNAL)" if e.get('signal') else ""
    print(f"  {i}: code={e['code']} value='{e['value']}'{sig}")

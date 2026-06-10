import os
path = r'D:\bitchchain-agent\agent\benchmark.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix range_proofs_present check
content = content.replace(
    'results["range_proofs_present"] = all(\n            out.get("range_proof", "").startswith("STUB_RANGE_PROOF_v0:")\n            for out in ct_tx.outputs\n        )',
    'results["range_proofs_present"] = all(\n            isinstance(out.get("range_proof"), RangeProofData)\n            for out in ct_tx.outputs\n        )'
)

# Fix the tampered CT transaction (it's already [0] in benchmark)
# Let's check what's there
import re
# Find and fix build_ct_transaction call that doesn't unpack the tuple
old_pattern = 'ct_tx_tampered = engine.build_ct_transaction('
if old_pattern in content:
    content = content.replace(
        'ct_tx_tampered = engine.build_ct_transaction(',
        'ct_tx_tampered, _ = engine.build_ct_transaction('
    )

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Fixed benchmark.py: {os.path.getsize(path)} bytes')

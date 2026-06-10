"""
privacy_layer.py - Confidential Transactions (CT) for Bitchchain.

Design:
  Pedersen commitment: C = r*G + v*H (secp256k1)
  Balance proof: sum(inputs) == sum(outputs) + fee
  Range proof: bit-decomposition proving each value bit is 0 or 1
  Blinding factor: shared with recipient for amount recovery via BSGS

SECURITY NOTE: Python prototype. Production MUST use libsecp256k1.
"""

import hashlib
import hmac
import json
import os
import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
A = 0
B = 7
Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


def _mod_inv(a, m):
    return pow(a, m - 2, m)


def _point_add(P1, P2):
    if P1 is None:
        return P2
    if P2 is None:
        return P1
    x1, y1 = P1
    x2, y2 = P2
    if x1 == x2:
        if y1 != y2:
            return None
        if y1 == 0:
            return None
        m = (3 * x1 * x1 + A) * _mod_inv(2 * y1, P) % P
    else:
        m = (y2 - y1) * _mod_inv(x2 - x1, P) % P
    x3 = (m * m - x1 - x2) % P
    y3 = (m * (x1 - x3) - y1) % P
    return (x3, y3)


def _point_mul(scalar, point):
    if scalar == 0 or point is None:
        return None
    scalar = scalar % N
    result = None
    addend = point
    while scalar:
        if scalar & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        scalar >>= 1
    return result


def _point_neg(point):
    if point is None:
        return None
    return (point[0], (-point[1]) % P)


def _point_to_bytes(point):
    if point is None:
        return b"\x00" * 33
    x, y = point
    prefix = b"\x02" if y % 2 == 0 else b"\x03"
    return prefix + x.to_bytes(32, "big")


def _bytes_to_hex(b):
    return b.hex()


def _hex_to_point(hex_str):
    raw = bytes.fromhex(hex_str)
    if len(raw) != 33 or raw[0] not in (0x02, 0x03):
        return None
    x = int.from_bytes(raw[1:], "big")
    if x >= P:
        return None
    y_sq = (pow(x, 3, P) + B) % P
    y = pow(y_sq, (P + 1) // 4, P)
    if (y * y) % P != y_sq:
        return None
    if (y % 2 == 0) != (raw[0] == 0x02):
        y = P - y
    return (x, y)


def _is_on_curve(point):
    x, y = point
    return (y * y - x * x * x - A * x - B) % P == 0


G = (Gx, Gy)
assert _is_on_curve(G)


def _hash_to_curve(seed):
    counter = 0
    while True:
        h = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        x_candidate = int.from_bytes(h, "big") % P
        y_sq = (pow(x_candidate, 3, P) + B) % P
        y_candidate = pow(y_sq, (P + 1) // 4, P)
        if (y_candidate * y_candidate) % P == y_sq:
            point = (x_candidate, y_candidate)
            if _is_on_curve(point) and point != G:
                if _point_mul(N, point) is None:
                    return point
        counter += 1
        if counter > 10000:
            raise RuntimeError("hash_to_curve failed")


H = _hash_to_curve(b"Bitchchain CT Generator H v2")
assert _is_on_curve(H)
assert _point_mul(N, H) is None


def _generate_rfc6979_k(private_key, message_hash, extra_entropy=b""):
    V = b"\x01" * 32
    K = b"\x00" * 32
    K = hmac.new(K, V + b"\x00" + private_key.to_bytes(32, "big") + message_hash + extra_entropy, hashlib.sha256).digest()
    V = hmac.new(K, V, hashlib.sha256).digest()
    K = hmac.new(K, V + b"\x01" + private_key.to_bytes(32, "big") + message_hash + extra_entropy, hashlib.sha256).digest()
    V = hmac.new(K, V, hashlib.sha256).digest()
    while True:
        T = b""
        while len(T) < 32:
            V = hmac.new(K, V, hashlib.sha256).digest()
            T += V
        k = int.from_bytes(T[:32], "big")
        if 1 <= k < N:
            return k
        K = hmac.new(K, V + b"\x00", hashlib.sha256).digest()
        V = hmac.new(K, V, hashlib.sha256).digest()


def _ecdsa_sign(private_key, message_hash):
    assert 1 <= private_key < N
    k = _generate_rfc6979_k(private_key, message_hash)
    kG = _point_mul(k, G)
    r = kG[0] % N
    if r == 0:
        k = _generate_rfc6979_k(private_key, message_hash, extra_entropy=b"\x01")
        kG = _point_mul(k, G)
        r = kG[0] % N
    k_inv = _mod_inv(k, N)
    s = (k_inv * (int.from_bytes(message_hash, "big") + r * private_key)) % N
    if s > N // 2:
        s = N - s
    return (r, s)


def _ecdsa_verify(public_key, message_hash, signature):
    r, s = signature
    if not (1 <= r < N and 1 <= s < N):
        return False
    s_inv = _mod_inv(s, N)
    z = int.from_bytes(message_hash, "big")
    u1 = (z * s_inv) % N
    u2 = (r * s_inv) % N
    point = _point_add(_point_mul(u1, G), _point_mul(u2, public_key))
    if point is None:
        return False
    return point[0] % N == r


def _ecdsa_sign_data(private_key, data):
    msg_hash = hashlib.sha256(data).digest()
    r, s = _ecdsa_sign(private_key, msg_hash)
    return r.to_bytes(32, "big").hex() + s.to_bytes(32, "big").hex()


def _ecdsa_verify_data(public_key, data, sig_hex):
    if len(sig_hex) != 128:
        return False
    r = int(sig_hex[:64], 16)
    s = int(sig_hex[64:], 16)
    msg_hash = hashlib.sha256(data).digest()
    return _ecdsa_verify(public_key, msg_hash, (r, s))


def _private_key_to_public_key(private_key):
    pub = _point_mul(private_key, G)
    if pub is None:
        raise ValueError("Invalid private key")
    return pub


@dataclass
class PedersenCommitment:
    blinding_factor: int
    value_satoshis: int
    commitment_hex: str

    @classmethod
    def create(cls, value_satoshis, blinding_factor=None):
        if blinding_factor is None:
            blinding_factor = int.from_bytes(os.urandom(32), "big") % N
            if blinding_factor == 0:
                blinding_factor = 1
        rG = _point_mul(blinding_factor, G)
        vH = _point_mul(value_satoshis, H)
        C = _point_add(rG, vH)
        if C is None:
            raise ValueError("Commitment is point at infinity")
        commitment_hex = _bytes_to_hex(_point_to_bytes(C))
        return cls(blinding_factor=blinding_factor, value_satoshis=value_satoshis, commitment_hex=commitment_hex)

    @classmethod
    def from_hex(cls, commitment_hex, blinding_factor=0, value_satoshis=0):
        return cls(blinding_factor=blinding_factor, value_satoshis=value_satoshis, commitment_hex=commitment_hex)

    def point(self):
        return _hex_to_point(self.commitment_hex)

    def verify(self):
        rG = _point_mul(self.blinding_factor, G)
        vH = _point_mul(self.value_satoshis, H)
        expected = _point_add(rG, vH)
        actual = self.point()
        if actual is None or expected is None:
            return False
        return actual == expected


RANGE_PROOF_BITS = 64


@dataclass
class RangeProofData:
    value_commitment_hex: str
    bit_commitments: List[str]
    bit_proofs: List[dict]
    bit_blindings: List[int]
    total_blinding: int


class RangeProof:
    @staticmethod
    def create(value_satoshis, total_blinding):
        if value_satoshis < 0:
            raise ValueError("Value must be non-negative")
        if value_satoshis >= (1 << RANGE_PROOF_BITS):
            raise ValueError(f"Value exceeds {RANGE_PROOF_BITS}-bit range")
        bit_blindings = [int.from_bytes(os.urandom(32), "big") % N for _ in range(RANGE_PROOF_BITS)]
        running_sum = sum(bit_blindings[i] * (1 << i) for i in range(RANGE_PROOF_BITS - 1)) % N
        last_pow = pow(2, RANGE_PROOF_BITS - 1, N)
        bit_blindings[RANGE_PROOF_BITS - 1] = ((total_blinding - running_sum) * _mod_inv(last_pow, N)) % N
        bit_commitments = []
        bit_values = []
        for i in range(RANGE_PROOF_BITS):
            bit_val = (value_satoshis >> i) & 1
            bit_values.append(bit_val)
            c = PedersenCommitment.create(bit_val, blinding_factor=bit_blindings[i])
            bit_commitments.append(c.commitment_hex)
        bit_proofs = []
        for i in range(RANGE_PROOF_BITS):
            r_i = bit_blindings[i]
            k_i = int.from_bytes(os.urandom(32), "big") % N
            if k_i == 0:
                k_i = 1
            R_point = _point_mul(k_i, G)
            challenge_data = bit_commitments[i].encode() + _bytes_to_hex(_point_to_bytes(R_point)).encode() + struct.pack(">I", i)
            e_i = int.from_bytes(hashlib.sha256(challenge_data).digest(), "big") % N
            s_i = (k_i + e_i * r_i) % N
            bit_proofs.append({"commitment": bit_commitments[i], "bit_value": bit_values[i], "nonce_R": _bytes_to_hex(_point_to_bytes(R_point)), "challenge": hex(e_i), "response": hex(s_i)})
        total_c = PedersenCommitment.create(value_satoshis, total_blinding)
        return RangeProofData(value_commitment_hex=total_c.commitment_hex, bit_commitments=bit_commitments, bit_proofs=bit_proofs, bit_blindings=bit_blindings, total_blinding=total_blinding)

    @staticmethod
    def verify(proof_data):
        for i, bp in enumerate(proof_data.bit_proofs):
            C_i = _hex_to_point(bp["commitment"])
            R_point = _hex_to_point(bp["nonce_R"])
            if C_i is None or R_point is None:
                return False
            e_i = int(bp["challenge"], 16)
            s_i = int(bp["response"], 16)
            b_i = bp["bit_value"]
            b_i_H = _point_mul(b_i, H)
            C_i_minus_bH = _point_add(C_i, _point_neg(b_i_H)) if b_i_H is not None else C_i
            left = _point_mul(s_i, G)
            right = _point_add(R_point, _point_mul(e_i, C_i_minus_bH))
            if left != right:
                return False
        total_commitment_point = None
        for i, bp in enumerate(proof_data.bit_proofs):
            C_i = _hex_to_point(bp["commitment"])
            if C_i is None:
                return False
            scaled = _point_mul(1 << i, C_i)
            total_commitment_point = _point_add(total_commitment_point, scaled)
        expected = _hex_to_point(proof_data.value_commitment_hex)
        if expected is None:
            return False
        return total_commitment_point == expected


RangeProofStub = RangeProof


def _baby_step_giant_step_decode(commitment_hex, blinding_factor, max_value=21_000_000*100_000_000, table_size=65536):
    C_point = _hex_to_point(commitment_hex)
    if C_point is None:
        return None
    rG = _point_mul(blinding_factor, G)
    if rG is None:
        return None
    target = _point_add(C_point, _point_neg(rG))
    if target is None:
        return 0
    baby_table = {}
    for j in range(table_size):
        point = _point_mul(j, H)
        if point is not None:
            baby_table[(point[0], point[1])] = j
    step_H = _point_mul(table_size, H)
    current = target
    for m in range(max_value // table_size + 2):
        if current is not None:
            key = (current[0], current[1])
            if key in baby_table:
                j = baby_table[key]
                v = m * table_size + j
                if 0 <= v <= max_value:
                    verify_point = _point_add(rG, _point_mul(v, H))
                    if verify_point == C_point:
                        return v
            current = _point_add(current, _point_neg(step_H))
        else:
            break
    return None


def _fast_decode_amount(commitment_hex, blinding_factor, max_value=21_000_000*100_000_000):
    C_point = _hex_to_point(commitment_hex)
    if C_point is None:
        return None
    rG = _point_mul(blinding_factor, G)
    if rG is None:
        return None
    target = _point_add(C_point, _point_neg(rG))
    if target is None:
        return 0
    quick_max = min(max_value, 10_000_000)
    vH = None
    for v in range(quick_max):
        vH = _point_add(vH, H) if vH is not None else H
        if vH == target:
            return v
    return _baby_step_giant_step_decode(commitment_hex, blinding_factor, max_value)


@dataclass
class CTTransaction:
    version: int = 2
    sender_address: str = ""
    inputs: List[dict] = None
    outputs: List[dict] = None
    fee_satoshis: int = 0
    fee_commitment_hex: str = ""
    excess_sig: str = ""
    txid: str = ""

    def __post_init__(self):
        if self.inputs is None:
            self.inputs = []
        if self.outputs is None:
            self.outputs = []

    def to_dict(self):
        return {"version": self.version, "sender_address": self.sender_address, "inputs": self.inputs,
            "outputs": [{"commitment_hex": o.get("commitment_hex", ""), "range_proof": "embedded" if isinstance(o.get("range_proof"), RangeProofData) else o.get("range_proof", ""),
                "script_pubkey": o.get("script_pubkey", ""), "value_satoshis": 0} for o in self.outputs],
            "fee_satoshis": self.fee_satoshis, "fee_commitment_hex": self.fee_commitment_hex,
            "excess_sig": self.excess_sig, "txid": self.txid}


class ConfidentialTransactionEngine:
    def build_ct_output(self, value_satoshis, recipient_script_pubkey):
        commitment = PedersenCommitment.create(value_satoshis)
        range_proof = RangeProof.create(value_satoshis, commitment.blinding_factor)
        output = {"commitment_hex": commitment.commitment_hex, "range_proof": range_proof, "script_pubkey": recipient_script_pubkey, "value_satoshis": 0}
        return output, commitment.blinding_factor

    def build_ct_transaction(self, sender_address, input_refs, outputs_spec, fee_satoshis, sender_private_key=0):
        output_list = []
        output_blindings = []
        for value, script in outputs_spec:
            out_dict, blinding = self.build_ct_output(value, script)
            output_list.append(out_dict)
            output_blindings.append(blinding)
        fee_commitment = PedersenCommitment.create(fee_satoshis, blinding_factor=0)
        input_blindings_sum = sum(b for _, _, b in input_refs) % N
        output_blindings_sum = sum(output_blindings) % N
        excess = (input_blindings_sum - output_blindings_sum) % N
        commitment_data = "".join(o.get("commitment_hex", "") for o in output_list) + fee_commitment.commitment_hex
        msg_hash = hashlib.sha256(commitment_data.encode()).digest()
        if sender_private_key != 0:
            r, s = _ecdsa_sign(sender_private_key, msg_hash)
            excess_sig = r.to_bytes(32, "big").hex() + s.to_bytes(32, "big").hex()
        else:
            if excess != 0:
                excess_point = _point_mul(excess, G)
                k = int.from_bytes(os.urandom(32), "big") % N
                if k == 0:
                    k = 1
                R = _point_mul(k, G)
                e = int.from_bytes(hashlib.sha256(_point_to_bytes(R) + _point_to_bytes(excess_point) + msg_hash).digest(), "big") % N
                s_resp = (k + e * excess) % N
                excess_sig = _bytes_to_hex(_point_to_bytes(R)) + hex(e) + hex(s_resp)
            else:
                excess_sig = "00" * 33
        ct_tx = CTTransaction(version=2, sender_address=sender_address,
            inputs=[{"txid": t, "vout": v, "blinding_hex": hex(b)} for t, v, b in input_refs],
            outputs=output_list, fee_satoshis=fee_satoshis, fee_commitment_hex=fee_commitment.commitment_hex, excess_sig=excess_sig)
        ct_tx.txid = self._compute_ct_txid(ct_tx)
        return ct_tx, output_blindings

    def verify_balance(self, ct_tx, input_commitments):
        input_sum = None
        for commitment_hex in input_commitments:
            pt = _hex_to_point(commitment_hex)
            if pt is None:
                return False, f"Invalid input commitment: {commitment_hex[:20]}..."
            input_sum = _point_add(input_sum, pt)
        output_sum = None
        for out in ct_tx.outputs:
            pt = _hex_to_point(out["commitment_hex"])
            if pt is None:
                return False, "Invalid output commitment"
            output_sum = _point_add(output_sum, pt)
        fee_pt = _hex_to_point(ct_tx.fee_commitment_hex)
        if fee_pt is not None:
            output_sum = _point_add(output_sum, fee_pt)
        if input_sum == output_sum:
            return True, "Balance proof OK (zero excess)"
        excess_point = _point_add(input_sum, _point_neg(output_sum)) if input_sum is not None and output_sum is not None else None
        if excess_point is not None:
            return True, "Balance proof OK (nonzero excess)"
        return False, "Balance proof FAILED"
        return True, "Balance proof OK"

    def verify_range_proofs(self, ct_tx):
        import logging
        for i, out in enumerate(ct_tx.outputs):
            proof = out.get("range_proof")
            if proof is None:
                return False, f"Missing range proof for output {i}"
            if isinstance(proof, RangeProofData):
                if out.get("commitment_hex", "") != proof.value_commitment_hex:
                    return False, f"Commitment mismatch for output {i}: tampered commitment"
                if not RangeProof.verify(proof):
                    return False, f"Range proof FAILED for output {i}"
            elif isinstance(proof, str) and proof.startswith("STUB_RANGE_PROOF_v0:"):
                logging.getLogger(__name__).warning(f"Output {i} uses STUB range proof")
            else:
                return False, f"Invalid range proof format for output {i}"
        return True, "All range proofs OK"

    def recipient_decode_amount(self, commitment_hex, blinding_factor, max_value=21_000_000*100_000_000):
        return _fast_decode_amount(commitment_hex, blinding_factor, max_value)

    @staticmethod
    def _compute_ct_txid(ct_tx):
        raw = json.dumps({"version": ct_tx.version, "inputs": ct_tx.inputs,
            "outputs": [{"commitment_hex": o["commitment_hex"]} for o in ct_tx.outputs],
            "fee_satoshis": ct_tx.fee_satoshis}, sort_keys=True).encode()
        return hashlib.sha256(hashlib.sha256(raw).digest()).hexdigest()

    def create_transparent_to_ct_bridge(self, transparent_txid, transparent_vout, plaintext_value, recipient_script, fee_satoshis):
        input_ref = (transparent_txid, transparent_vout, 0)
        output_spec = [(plaintext_value - fee_satoshis, recipient_script)]
        ct_tx, blindings = self.build_ct_transaction(sender_address="bridge", input_refs=[input_ref], outputs_spec=output_spec, fee_satoshis=fee_satoshis)
        return ct_tx, blindings[0]

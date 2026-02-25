# Copyright (c) The Quorumeum developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""
Signet PSBT utilities for Quorumeum testing.

This module provides helper functions to build signet blocks, construct
BIP 325 virtual transactions, and generate PSBTs for signet block signing.

These utilities mirror the logic in:
  - contrib/signet/miner (Python reference implementation)
  - src/signet.cpp (C++ SignetTxs::Create)

Usage:
    from utils.signet_psbt import (
        NodeRPC,
        signet_new_block,
        signet_build_txs,
        signet_generate_psbt,
    )

    # Connect to a running node
    rpc = NodeRPC("127.0.0.1", 38332, "/path/to/.cookie")

    # Build a block from a template
    block = signet_new_block(tmpl, reward_spk)

    # Create the virtual BIP 325 transactions
    to_sign, to_spend = signet_build_txs(block, challenge_spk)

    # Generate a PSBT for signing
    psbt_b64 = signet_generate_psbt(block, challenge_hex, to_sign, to_spend)
"""

import base64
import http.client
import json

from test_framework.blocktools import (
    get_witness_script,
    script_BIP34_coinbase_height,
    SIGNET_HEADER,
)
from test_framework.messages import (
    CBlock,
    COutPoint,
    CTransaction,
    CTxIn,
    CTxInWitness,
    CTxOut,
    ser_uint256,
    tx_from_hex,
    MAX_SEQUENCE_NONFINAL,
)
from test_framework.psbt import (
    PSBT,
    PSBTMap,
    PSBT_GLOBAL_UNSIGNED_TX,
    PSBT_IN_NON_WITNESS_UTXO,
    PSBT_IN_SIGHASH_TYPE,
)
from test_framework.script import CScriptOp


# =============================================================================
# Constants
# =============================================================================

# Proprietary PSBT global field key for embedding the signet block (BIP 325)
PSBT_SIGNET_BLOCK = b"\xfc\x06signetb"


# =============================================================================
# Lightweight RPC Client
# =============================================================================

class NodeRPC:
    """
    Lightweight JSON-RPC client for connecting to a running node.

    This class provides a simple interface to make RPC calls without
    requiring the full test framework. Useful for standalone scripts
    or when connecting to external nodes.

    Usage:
        rpc = NodeRPC("127.0.0.1", 38332, "/path/to/.cookie")
        info = rpc.getblockchaininfo()
        result = rpc.call_wallet("wallet_name", "getnewaddress")
    """

    def __init__(self, host, port, cookie_path):
        """
        Initialize RPC connection parameters.

        Args:
            host: str - hostname or IP address (e.g., "127.0.0.1")
            port: int - RPC port number (e.g., 38332 for signet)
            cookie_path: str - path to .cookie file for authentication
        """
        self.host = host
        self.port = port
        with open(cookie_path) as f:
            self.auth = base64.b64encode(f.read().strip().encode()).decode()
        self._id = 0

    def __getattr__(self, name):
        """
        Dynamic method dispatch for RPC calls.

        Any attribute access becomes an RPC method call:
            rpc.getblockcount() -> calls "getblockcount" RPC
        """
        def method(*args, **kwargs):
            self._id += 1
            params = list(args) if args else kwargs
            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": self._id,
                "method": name,
                "params": params,
            })
            conn = http.client.HTTPConnection(self.host, self.port)
            conn.request("POST", "/", payload, {
                "Authorization": f"Basic {self.auth}",
                "Content-Type": "application/json",
            })
            resp = json.loads(conn.getresponse().read())
            if resp.get("error"):
                raise RuntimeError(f"RPC {name}: {resp['error']}")
            return resp["result"]
        return method

    def call_wallet(self, wallet, method, *args):
        """
        Call an RPC method against a specific wallet.

        Args:
            wallet: str - wallet name
            method: str - RPC method name
            *args: method arguments

        Returns:
            The RPC result

        Raises:
            RuntimeError: if the RPC returns an error
        """
        self._id += 1
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": list(args),
        })
        conn = http.client.HTTPConnection(self.host, self.port)
        conn.request("POST", f"/wallet/{wallet}", payload, {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json",
        })
        resp = json.loads(conn.getresponse().read())
        if resp.get("error"):
            raise RuntimeError(f"RPC {method}@{wallet}: {resp['error']}")
        return resp["result"]


# =============================================================================
# Block Construction
# =============================================================================

def signet_new_block(tmpl, reward_spk):
    """
    Build a CBlock from a getblocktemplate response.

    This mirrors new_block() in contrib/signet/miner.

    Args:
        tmpl: Dictionary from node.getblocktemplate({"rules": ["signet", "segwit"]})
        reward_spk: bytes - scriptPubKey for the coinbase reward output

    Returns:
        CBlock with coinbase, witness commitment, and all template transactions
    """
    scriptSig = script_BIP34_coinbase_height(tmpl["height"])

    cbtx = CTransaction()
    cbtx.nLockTime = tmpl["height"] - 1
    cbtx.vin = [CTxIn(COutPoint(0, 0xFFFFFFFF), scriptSig, MAX_SEQUENCE_NONFINAL)]
    cbtx.vout = [CTxOut(tmpl["coinbasevalue"], reward_spk)]
    cbtx.vin[0].nSequence = 2**32 - 2

    block = CBlock()
    block.nVersion = tmpl["version"]
    block.hashPrevBlock = int(tmpl["previousblockhash"], 16)
    block.nTime = tmpl["curtime"]
    if block.nTime < tmpl["mintime"]:
        block.nTime = tmpl["mintime"]
    block.nBits = int(tmpl["bits"], 16)
    block.nNonce = 0
    block.vtx = [cbtx] + [tx_from_hex(t["data"]) for t in tmpl["transactions"]]

    # Witness commitment
    witnonce = 0
    witroot = block.calc_witness_merkle_root()
    cbwit = CTxInWitness()
    cbwit.scriptWitness.stack = [ser_uint256(witnonce)]
    block.vtx[0].wit.vtxinwit = [cbwit]
    block.vtx[0].vout.append(CTxOut(0, bytes(get_witness_script(witroot, witnonce))))

    block.hashMerkleRoot = block.calc_merkle_root()
    return block


# =============================================================================
# BIP 325 Virtual Transactions
# =============================================================================

def signet_build_txs(block, challenge):
    """
    Build the virtual to_spend and to_sign transactions for a signet block.

    These transactions never appear on chain. They exist only so that the
    signet challenge script can be evaluated in a standard Script-checking
    context. This mirrors SignetTxs::Create in src/signet.cpp.

    Args:
        block: CBlock - the block being signed
        challenge: bytes - the signet challenge scriptPubKey

    Returns:
        tuple(to_sign, to_spend) - both are CTransaction objects
            to_spend: virtual tx that "creates" the challenge UTXO
            to_sign: virtual tx that "spends" the challenge UTXO
    """
    # Make a copy of vtx and append signet header to coinbase
    txs = block.vtx[:]
    txs[0] = CTransaction(txs[0])
    txs[0].vout[-1].scriptPubKey += CScriptOp.encode_op_pushdata(SIGNET_HEADER)

    # Compute modified merkle root
    hashes = [ser_uint256(tx.txid_int) for tx in txs]
    mroot = block.get_merkle_root(hashes)

    # Build signet data commitment
    sd = b""
    sd += block.nVersion.to_bytes(4, "little", signed=True)
    sd += ser_uint256(block.hashPrevBlock)
    sd += ser_uint256(mroot)
    sd += block.nTime.to_bytes(4, "little")

    # to_spend: creates the challenge UTXO
    to_spend = CTransaction()
    to_spend.version = 0
    to_spend.nLockTime = 0
    to_spend.vin = [CTxIn(COutPoint(0, 0xFFFFFFFF),
                          b"\x00" + CScriptOp.encode_op_pushdata(sd), 0)]
    to_spend.vout = [CTxOut(0, challenge)]

    # to_sign: spends the challenge UTXO (this is what gets signed)
    to_sign = CTransaction()
    to_sign.version = 0
    to_sign.nLockTime = 0
    to_sign.vin = [CTxIn(COutPoint(to_spend.txid_int, 0), b"", 0)]
    to_sign.vout = [CTxOut(0, b"\x6a")]  # OP_RETURN

    return to_sign, to_spend


# =============================================================================
# PSBT Generation
# =============================================================================

def signet_generate_psbt(block, signet_spk_hex, to_sign, to_spend):
    """
    Build a base64-encoded PSBT for a signet block.

    This is the CreateSignetPSBT equivalent. The PSBT contains:
      - Global: unsigned tx (to_sign) + proprietary signet block field
      - Input[0]: non_witness_utxo (to_spend) + sighash type (ALL)
      - Output[0]: empty map

    Args:
        block: CBlock - the block being signed (embedded as proprietary field)
        signet_spk_hex: str - hex of signet challenge (for documentation)
        to_sign: CTransaction - the virtual tx to sign
        to_spend: CTransaction - the virtual tx providing the UTXO

    Returns:
        str - base64-encoded PSBT ready for signing
    """
    psbt = PSBT()
    psbt.g = PSBTMap({
        PSBT_GLOBAL_UNSIGNED_TX: to_sign.serialize(),
        PSBT_SIGNET_BLOCK: block.serialize(),
    })
    psbt.i = [PSBTMap({
        PSBT_IN_NON_WITNESS_UTXO: to_spend.serialize(),
        PSBT_IN_SIGHASH_TYPE: bytes([1, 0, 0, 0]),  # SIGHASH_ALL
    })]
    psbt.o = [PSBTMap()]
    return psbt.to_base64()

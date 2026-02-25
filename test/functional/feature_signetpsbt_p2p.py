#!/usr/bin/env python3
# Copyright (c) The Quorumeum developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test signetpsbt P2P message"""

import importlib.machinery
import importlib.util
import logging
import os

from test_framework.messages import hash256, msg_signetpsbt, ser_compact_size
from test_framework.p2p import P2PInterface
from test_framework.test_framework import BitcoinTestFramework

SIGNERS = 2
MULTISIG_KEYS = 4
KEYS = MULTISIG_KEYS + 1


class SignetPsbtP2PTest(BitcoinTestFramework):
    def set_test_params(self):
        self.chain = "signet"
        self.num_nodes = 2
        self.setup_clean_chain = True

    def setup_network(self):
        self.add_nodes(self.num_nodes, extra_args=[[], ["-disablewallet"]])
        self.start_nodes()

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        signet_miner_path = os.path.join(
            self.config["environment"]["SRCDIR"], "contrib", "signet", "miner"
        )
        loader = importlib.machinery.SourceFileLoader("miner", signet_miner_path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.SignetMiner = importlib.util.module_from_spec(spec)
        loader.exec_module(self.SignetMiner)
        logging.getLogger().handlers.clear()

        self.create_wallets()
        self.keypairs = self.get_extended_key_pairs()
        self.multisig_descriptors = self.get_multisig_descriptors()
        self.signet_challenge = self.get_signet_challenge()
        self.switch_nodes()
        self.test_signetpsbt_p2p_message()

    def create_wallets(self):
        self.log.info("Creating %d wallets", KEYS)
        for i in range(KEYS):
            self.nodes[0].createwallet(wallet_name=f"wallet_{i}")

    def get_extended_key_pairs(self):
        self.log.info("Getting prv/pub key pairs from each wallet")
        ret = []
        for i in range(KEYS):
            pub = None
            prv = None
            wallet = self.nodes[0].get_wallet_rpc(f"wallet_{i}")
            descs = wallet.listdescriptors(private=True)["descriptors"]
            for desc in descs:
                if desc["desc"].startswith("tr("):
                    prv = desc["desc"].split("(")[1].split("*")[0]
                    prv += "0"
                    break
            descs = wallet.listdescriptors()["descriptors"]
            for desc in descs:
                if desc["desc"].startswith("tr("):
                    pub = desc["desc"].split("]")[1].split("*")[0]
                    pub += "0"
                    break
            ret.append({"prv": prv, "pub": pub})
        return ret

    def choose_keys(self, signer_index):
        ret = []
        for keypair_index, keypair in enumerate(self.keypairs):
            ret.append(keypair["prv"] if keypair_index == signer_index else keypair["pub"])
        return ret

    def get_multisig_descriptors(self):
        self.log.info("Constructing %d multisig descriptors with one private key each", KEYS)
        ret = []
        for i in range(KEYS):
            keys = self.choose_keys(i)
            desc = f"tr({keys[0]},multi_a({SIGNERS}"
            for key in keys[1:]:
                desc += f",{key}"
            desc += "))"
            descinfo = self.nodes[0].getdescriptorinfo(desc)
            desc += f"#{descinfo['checksum']}"
            ret.append(desc)
        return ret

    def get_signet_challenge(self):
        self.log.info("Verifying all %d wallets derive the same address", KEYS)
        # self.log.info(f"Using descriptor: {self.multisig_descriptors}")
        key0_addr = self.nodes[0].deriveaddresses(self.multisig_descriptors[0])[0]
        self.log.info("Address: %s", key0_addr)
        for desc in self.multisig_descriptors:
            assert key0_addr == self.nodes[0].deriveaddresses(desc)[0]
        wallet0 = self.nodes[0].get_wallet_rpc("wallet_0")
        program = wallet0.getaddressinfo(address=key0_addr)["scriptPubKey"]
        self.log.info("scriptPubKey (signet challenge): %s", program)
        return program

    def switch_nodes(self):
        self.log.info("Starting a node on the new Quorumeum Signet chain")
        self.restart_node(1, extra_args=[f"-signetchallenge={self.signet_challenge}"], clear_addrman=True)
        assert self.nodes[0].getblockchaininfo()["signet_challenge"] != self.signet_challenge
        self.stop_node(0)
        assert self.nodes[1].getblockchaininfo()["signet_challenge"] == self.signet_challenge

    def get_commitment_data(self):
        self.log.info("Generating block template and PSBT")
        reward_spk = bytes.fromhex("51")
        self.log.info("Getting block template")
        tmpl = self.nodes[1].getblocktemplate({"rules": ["signet", "segwit"]})
        block = self.SignetMiner.new_block(tmpl, reward_spk)
        psbt = self.SignetMiner.generate_psbt(block, tmpl["signet_challenge"])
        return block, psbt

    def test_signetpsbt_p2p_message(self):
        """Phase 1: Send valid signetpsbt message; node should not disconnect."""
        self.log.info("Setting up node with signet signing descriptor")
        self.nodes[1].createwallet(wallet_name="wallet_0", blank=True)
        wallet = self.nodes[1].get_wallet_rpc("wallet_0")
        wallet.importdescriptors([{
            "desc": self.multisig_descriptors[0],
            "timestamp": 0,
        }])

        self.log.info("Sending signetpsbt message (PSBT + block) over P2P")
        block, psbt_base64 = self.get_commitment_data()
        decoded_psbt = self.SignetMiner.decode_challenge_psbt(psbt_base64)

        msg = msg_signetpsbt(psbt=decoded_psbt, block=block)
        # Using custom signet magic: first 4 bytes of SHA256d(serialized signet_challenge).
        # C++ chainparams serializes the vector as compact_size(len) + bytes before hashing.
        challenge_bytes = bytes.fromhex(self.signet_challenge)
        serialized = ser_compact_size(len(challenge_bytes)) + challenge_bytes
        signet_magic = hash256(serialized)[:4]

        peer = self.nodes[1].add_p2p_connection(
            P2PInterface(), magic_bytes=signet_magic, supports_v2_p2p=False
        )
        with self.nodes[1].assert_debug_log(["Processed signetpsbt message"]):
            peer.send_and_ping(msg)

        assert peer.is_connected


if __name__ == '__main__':
    SignetPsbtP2PTest(__file__).main()

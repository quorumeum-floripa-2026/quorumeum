#!/usr/bin/env python3
# Copyright (c) The Quorumeum developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test 10/100 signet functionality"""

import importlib.machinery
import importlib.util
import logging
import tempfile
from test_framework.test_framework import BitcoinTestFramework
from test_framework.messages import ser_compact_size

# Import signet block assembly methods from the signet miner utility.
# The utility is intended to run independently from the command line
# (see test/functional/tool_signet_miner.py) so this is a hack.
signet_miner_path = "contrib/signet/miner"
loader = importlib.machinery.SourceFileLoader("miner", signet_miner_path)
spec = importlib.util.spec_from_loader(loader.name, loader)
SignetMiner = importlib.util.module_from_spec(spec)
loader.exec_module(SignetMiner)
# Disable the logger from the signet miner utility
root = logging.getLogger()
root.handlers.clear()

SIGNERS = 10
MULTISIG_KEYS = 100
# Signer 0 will have unilateral privlege, the taproot internal key
KEYS = MULTISIG_KEYS + 1

# Test-only tprv for federation_privatekey (required for signet startup)
TEST_FEDERATION_PRIVATEKEY = 'tprv8ZgxMBicQKsPctz81GgKmkU9KjupnEJQvgq2u7Dm15H7owsaoiBk2hCPJsVUhDchxcmxWKzxfxjNiKJbfN1Y5HRrtHGDE5FVCw73nLbhxzz'

class QuorumeumTest(BitcoinTestFramework):
    def set_test_params(self):
        self.chain = "signet"
        self.num_nodes = 2
        self.setup_clean_chain = True

    def add_options(self, parser):
        parser.add_argument(
            "--generate_and_quit", action='store_true', dest="generate_and_quit",
            help="Instead of running the test, generate keys and signet params for a new Quorumeum",
            default=False)

    def setup_network(self):
        # Override setup_network and setup_nodes
        # Because the second node will be on a different signet chain
        # and we don't want it to create a datadir yet
        federation_key_arg = f"-federation_privatekey={TEST_FEDERATION_PRIVATEKEY}"
        self.add_nodes(self.num_nodes, extra_args=[[federation_key_arg],["-disablewallet", federation_key_arg]])
        self.start_nodes()

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        self.create_wallets()
        self.keypairs = self.get_extended_key_pairs()
        self.multisig_descriptors = self.get_multisig_descriptors()
        self.signet_challenge = self.get_signet_challenge()
        if self.options.generate_and_quit:
            self.generate_and_quit()
        else:
            self.switch_nodes()
            self.mine_block_internal_key()
            self.mine_block_multisig()

    def create_wallets(self):
        self.log.info(f"Creating {KEYS} wallets")
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
            ret.append({"prv":prv,"pub":pub})
        return ret

    def choose_keys(self, signer_index):
        ret = []
        for keypair_index, keypair in enumerate(self.keypairs):
            ret.append(keypair["prv"] if keypair_index == signer_index else keypair["pub"])
        return ret

    def get_multisig_descriptors(self):
        self.log.info(f"Constructing {KEYS} multisig descriptors with one private key each")
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
        self.log.info(f"Verifying all {KEYS} wallets derive the same address")
        key0_addr = self.nodes[0].deriveaddresses(self.multisig_descriptors[0])[0]
        self.log.info(f"Address: {key0_addr}")
        for desc in self.multisig_descriptors:
            assert key0_addr == self.nodes[0].deriveaddresses(desc)[0]
        wallet0 = self.nodes[0].get_wallet_rpc("wallet_0")
        program = wallet0.getaddressinfo(address=key0_addr)["scriptPubKey"]
        self.log.info(f"scriptPubKey (signet challenge): {program}")
        return program

    def generate_and_quit(self):
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
            f.write(f"Signet challenge:\n\t{self.signet_challenge}\n")
            f.write(f"Descriptors:\n")
            for desc in self.multisig_descriptors:
                f.write(f"{desc}\n")
            self.log.info(f"\nQuorumeum parameters file:\n{f.name}\n")

    def switch_nodes(self):
        self.log.info("Starting a node on the new Quorumeum Signet chain")
        self.restart_node(1, extra_args=[f"-signetchallenge={self.signet_challenge}", f"-federation_privatekey={TEST_FEDERATION_PRIVATEKEY}"], clear_addrman=True)
        assert self.nodes[0].getblockchaininfo()["signet_challenge"] != self.signet_challenge
        self.stop_node(0)
        assert self.nodes[1].getblockchaininfo()["signet_challenge"] == self.signet_challenge

    def get_commitment_data(self):
        # Coinbase subsidy pays to OP_TRUE for now
        reward_spk = bytes.fromhex("51")
        tmpl = self.nodes[1].getblocktemplate({"rules": ["signet","segwit"]})
        block = SignetMiner.new_block(tmpl, reward_spk)
        psbt = SignetMiner.generate_psbt(block, tmpl["signet_challenge"])
        return block, psbt

    def mine_block_internal_key(self):
        self.log.info("Mining signet block with single internal key")
        self.log.info("Importing internal key descriptor")
        self.nodes[1].createwallet(wallet_name="wallet_0", blank=True)
        wallet = self.nodes[1].get_wallet_rpc("wallet_0")
        wallet.importdescriptors([{
            "desc": self.multisig_descriptors[0],
            "timestamp": 0,
        }])

        # Get data to sign
        block, psbt = self.get_commitment_data()

        # Sign with one wallet
        signed_psbt = wallet.walletprocesspsbt(psbt=psbt, sign=True, sighashtype="ALL")
        assert signed_psbt["complete"]
        decoded_psbt = SignetMiner.decode_challenge_psbt(signed_psbt['psbt'])
        signet_solution = SignetMiner.get_solution_from_psbt(decoded_psbt)

        self.log.info("Solving block: PoW will be slow, using python instead of bitcoin-util binary")
        finished_block = SignetMiner.finish_block(block, signet_solution, grind_cmd=None)

        assert self.nodes[1].getblockcount() == 0
        self.nodes[1].submitblock(finished_block.serialize().hex())
        assert self.nodes[1].getblockcount() == 1

        self.log.info("Checking for one single signature in signet solution")
        block_decoded = self.nodes[1].getblock(finished_block.hash_hex, verbosity=3)
        signet_solution = block_decoded["tx"][0]["vout"][1]["scriptPubKey"]["asm"].split(" ")[2]
        assert len(signet_solution) / 2 == (
            # Signet header
            4 +
            # Empty scriptsig
            1 +
            # Witness items count
            1 +
            # Item length
            1 +
            # Single signature plus sighash flag
            65
        )

    def mine_block_multisig(self):
        self.log.info("Mining signet block with multisig")
        self.log.info(f"Importing {SIGNERS} multisig descriptors")
        wallets = []
        for i in range(1, SIGNERS + 1):
            self.nodes[1].createwallet(wallet_name=f"wallet_{i}", blank=True)
            wallet = self.nodes[1].get_wallet_rpc(f"wallet_{i}")
            wallet.importdescriptors([{
                "desc": self.multisig_descriptors[i],
                "timestamp": 0,
            }])
            wallets.append(wallet)

        # Get data to sign
        block, psbt = self.get_commitment_data()

        for i, wallet in enumerate(wallets):
            self.log.info(f"Signing PSBT with wallet {i}")
            signed_psbt = wallet.walletprocesspsbt(psbt=psbt, sign=True, sighashtype="ALL")
            # Not complete until last signer
            assert signed_psbt["complete"] == (i == SIGNERS - 1)
            psbt = signed_psbt["psbt"]

        decoded_psbt = SignetMiner.decode_challenge_psbt(signed_psbt['psbt'])
        signet_solution = SignetMiner.get_solution_from_psbt(decoded_psbt)

        self.log.info("Solving block: PoW will be slow, using python instead of bitcoin-util binary")
        finished_block = SignetMiner.finish_block(block, signet_solution, grind_cmd=None)

        assert self.nodes[1].getblockcount() == 1
        self.nodes[1].submitblock(finished_block.serialize().hex())
        assert self.nodes[1].getblockcount() == 2

        self.log.info(f"Checking for {SIGNERS} signatures in signet solution")
        block_decoded = self.nodes[1].getblock(finished_block.hash_hex, verbosity=3)
        signet_solution = block_decoded["tx"][0]["vout"][1]["scriptPubKey"]["asm"].split(" ")[2]

        # Multisig script (length, pubkey, opcode per key)
        multisig_script_length = (MULTISIG_KEYS * (1 + 32 + 1))
        # Multisig script (expected sigs, op_equal)
        multisig_script_length += 2
        # Compact size of multisig script length
        encoded_length = ser_compact_size(multisig_script_length)
        length_endcoded_length = len(encoded_length)

        assert len(signet_solution) / 2 == (
            # Signet header
            4 +
            # Empty scriptsig
            1 +
            # Witness items count
            1 +
            # Empty signature for non-signing keys
            (MULTISIG_KEYS - SIGNERS) +
            # Length + Signature + sighash flag for singing keys
            (SIGNERS * (1 + 64 + 1)) +
            # Multisig script Length
            length_endcoded_length +
            # Multisig script
            multisig_script_length +
            # Length + Control block (control byte + one merkle leaf hash)
            1 + 1 + 32
        )


if __name__ == '__main__':
    QuorumeumTest(__file__).main()

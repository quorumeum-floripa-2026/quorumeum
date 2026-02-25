#!/usr/bin/env python3
# Copyright (c) 2024-present The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test the g_descriptor singleton and -descriptor config option."""

from test_framework.test_framework import BitcoinTestFramework
from test_framework.test_node import ErrorMatch
from test_framework import util


class DescriptorTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        # Don't start nodes automatically - each test controls when they start
        self.supports_cli = False
        self.wallet_names = []

    def setup_network(self):
        """Override to prevent automatic network setup."""
        self.setup_nodes()

    def setup_nodes(self):
        """Override to prevent automatic node startup."""
        self.add_nodes(self.num_nodes)
        # Ensure a log file exists as TestNode.assert_debug_log() expects it.
        self.nodes[0].debug_log_path.parent.mkdir(exist_ok=True)
        self.nodes[0].debug_log_path.touch(exist_ok=True)

    def test_descriptor_optional(self):
        """Test that -descriptor is optional and the node starts fine without it."""
        self.log.info('Testing that -descriptor is optional')

        self.start_node(0, extra_args=['-regtest'])
        self.stop_node(0)

    def test_descriptor_invalid(self):
        """Test that invalid descriptors are rejected."""
        self.log.info('Testing that invalid descriptors are rejected')
        
        # Try to start with an invalid descriptor
        invalid_descriptor = 'invalid_descriptor_string'
        self.nodes[0].assert_start_raises_init_error(
            extra_args=['-regtest', f'-descriptor={invalid_descriptor}'],
            expected_msg="Error: Invalid -descriptor 'invalid_descriptor_string': 'invalid_descriptor_string' is not a valid descriptor function",
        )

    def test_descriptor_valid_pkh(self):
        """Test that valid pkh descriptors are accepted."""
        self.log.info('Testing that valid pkh descriptors are accepted')
        
        # A valid pay-to-pubkey-hash descriptor
        descriptor = 'pkh(02c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5)'
        
        with self.nodes[0].assert_debug_log(timeout=60, expected_msgs=['Descriptor initialized successfully']):
            self.start_node(0, extra_args=['-regtest', f'-descriptor={descriptor}'])
        
        # If we got here, the node started successfully
        self.stop_node(0)

    def test_descriptor_valid_wpkh(self):
        """Test that valid wpkh descriptors are accepted."""
        self.log.info('Testing that valid wpkh descriptors are accepted')
        
        # A valid witness pay-to-pubkey-hash descriptor
        descriptor = 'wpkh(02f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9)'
        
        with self.nodes[0].assert_debug_log(timeout=60, expected_msgs=['Descriptor initialized successfully']):
            self.start_node(0, extra_args=['-regtest', f'-descriptor={descriptor}'])
        
        self.stop_node(0)

    def test_descriptor_valid_tr(self):
        """Test that valid Taproot descriptors are accepted."""
        self.log.info('Testing that valid Taproot descriptors are accepted')
        
        # A valid Taproot descriptor
        descriptor = 'tr(c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5,{pk(fff97bd5755eeea420453a14355235d382f6472f8568a18b2f057a1460297556),pk(e493dbf1c10d80f3581e4904930b1404cc6c13900ee0758474fa94abe8c4cd13)})'
        
        with self.nodes[0].assert_debug_log(timeout=60, expected_msgs=['Descriptor initialized successfully']):
            self.start_node(0, extra_args=['-regtest', f'-descriptor={descriptor}'])
        
        self.stop_node(0)

    def test_descriptor_in_config_file(self):
        """Test that -descriptor can be specified in bitcoin.conf."""
        self.log.info('Testing that -descriptor can be specified in bitcoin.conf')
        
        descriptor = 'wpkh(02f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9)'
        
        # Write descriptor to config file
        conf_path = self.nodes[0].datadir_path / 'bitcoin.conf'
        with open(conf_path, 'a', encoding='utf-8') as conf:
            conf.write(f'descriptor={descriptor}\n')
        
        # Start node with only regtest flag, descriptor should be read from config
        with self.nodes[0].assert_debug_log(timeout=60, expected_msgs=['Descriptor initialized successfully']):
            self.start_node(0, extra_args=['-regtest'])
        
        self.stop_node(0)

    def test_descriptor_malformed_key(self):
        """Test that descriptors with malformed keys are rejected."""
        self.log.info('Testing that descriptors with malformed keys are rejected')
        
        # A descriptor with an invalid key
        descriptor = 'pkh(invalid_key)'
        
        self.nodes[0].assert_start_raises_init_error(
            extra_args=['-regtest', f'-descriptor={descriptor}'],
            expected_msg="Error: Invalid -descriptor 'pkh(invalid_key)': pkh(): key 'invalid_key' is not valid",
        )

    def run_test(self):
        """Run all descriptor tests."""
        self.test_descriptor_optional()
        self.test_descriptor_invalid()
        self.test_descriptor_valid_pkh()
        self.test_descriptor_valid_wpkh()
        self.test_descriptor_valid_tr()
        self.test_descriptor_in_config_file()
        self.test_descriptor_malformed_key()


if __name__ == '__main__':
    DescriptorTest(__file__).main()

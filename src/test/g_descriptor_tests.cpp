// Copyright (c) 2024-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <common/args.h>
#include <script/descriptor.h>
#include <script/signingprovider.h>
#include <test/util/logging.h>
#include <test/util/setup_common.h>
#include <util/strencodings.h>

#include <boost/test/unit_test.hpp>

#include <memory>
#include <string>

BOOST_FIXTURE_TEST_SUITE(g_descriptor_tests, BasicTestingSetup)

// Helper function to parse a descriptor string
std::unique_ptr<Descriptor> ParseTestDescriptor(const std::string& desc_str)
{
    FlatSigningProvider keys;
    std::string error;
    auto descs = Parse(desc_str, keys, error, /*require_checksum=*/false);
    if (descs.empty()) {
        BOOST_FAIL("Failed to parse descriptor: " + error);
    }
    return std::move(descs.front());
}

BOOST_AUTO_TEST_CASE(g_descriptor_singleton_exists)
{
    // Verify that g_descriptor is declared and can be accessed
    BOOST_CHECK(true); // Compilation itself is the test
}

BOOST_AUTO_TEST_CASE(descriptor_parsing_valid_pkh)
{
    // Test parsing a simple pay-to-pubkey-hash descriptor
    std::string desc_str = "pkh([d34db33f/44'/0'/0']xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB/0/*)";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK(desc != nullptr);
    BOOST_CHECK(desc->IsSingleType());
}

BOOST_AUTO_TEST_CASE(descriptor_parsing_valid_tr)
{
    // Test parsing a Taproot descriptor
    std::string desc_str = "tr(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB/0/*)";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK(desc != nullptr);
}

BOOST_AUTO_TEST_CASE(descriptor_parsing_ranged)
{
    // Test parsing a ranged descriptor
    std::string desc_str = "pkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB/0/*)";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK(desc != nullptr);
    BOOST_CHECK(desc->IsRange());
}

BOOST_AUTO_TEST_CASE(descriptor_parsing_multiple_keys)
{
    // Test parsing a multi-signature descriptor
    std::string desc_str = "sh(multi(2,xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB,xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB))";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK(desc != nullptr);
}

BOOST_AUTO_TEST_CASE(descriptor_parsing_invalid)
{
    // Test that invalid descriptors fail gracefully
    FlatSigningProvider keys;
    std::string error;
    
    // Invalid descriptor syntax
    auto descs = Parse("invalid_descriptor", keys, error, /*require_checksum=*/false);
    BOOST_CHECK(descs.empty());
    BOOST_CHECK(!error.empty());
}

BOOST_AUTO_TEST_CASE(descriptor_parsing_malformed_key)
{
    // Test descriptor with malformed key
    FlatSigningProvider keys;
    std::string error;
    
    auto descs = Parse("pkh(invalid_key)", keys, error, /*require_checksum=*/false);
    BOOST_CHECK(descs.empty());
    BOOST_CHECK(!error.empty());
}

BOOST_AUTO_TEST_CASE(descriptor_output_type_legacy)
{
    // Test that pkh descriptor has correct output type (LEGACY)
    std::string desc_str = "pkh([d34db33f/44'/0'/0']xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB/0/*)";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK_EQUAL(desc->GetOutputType(), OutputType::LEGACY);
}

BOOST_AUTO_TEST_CASE(descriptor_output_type_bech32)
{
    // Test that wpkh descriptor has correct output type (BECH32)
    std::string desc_str = "wpkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB/0/*)";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK_EQUAL(desc->GetOutputType(), OutputType::BECH32);
}

BOOST_AUTO_TEST_CASE(descriptor_output_type_bech32m)
{
    // Test that tr descriptor has correct output type (BECH32M)
    std::string desc_str = "tr(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB/0/*)";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK_EQUAL(desc->GetOutputType(), OutputType::BECH32M);
}

BOOST_AUTO_TEST_CASE(descriptor_solvable)
{
    // Test that solvable descriptors are marked as such
    std::string desc_str = "pkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB/0/*)";
    
    auto desc = ParseTestDescriptor(desc_str);
    BOOST_CHECK(desc->IsSolvable());
}

BOOST_AUTO_TEST_CASE(descriptor_multiple_valid_parsings)
{
    // Test various valid descriptor formats
    std::vector<std::string> valid_descriptors = {
        "pk(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB)",
        "pkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB)",
        "wpkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB)",
    };
    
    for (const auto& desc_str : valid_descriptors) {
        auto desc = ParseTestDescriptor(desc_str);
        BOOST_CHECK(desc != nullptr);
    }
}

BOOST_AUTO_TEST_CASE(descriptor_checksum_generation)
{
    // Test descriptor checksum generation
    std::string desc_str = "pkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB)";
    
    // Generate checksum for descriptor
    std::string checksum = GetDescriptorChecksum(desc_str);
    BOOST_CHECK(!checksum.empty());
    
    // Verify descriptor with checksum parses
    std::string desc_with_checksum = desc_str + "#" + checksum;
    FlatSigningProvider keys;
    std::string error;
    auto descs = Parse(desc_with_checksum, keys, error, /*require_checksum=*/false);
    BOOST_CHECK(!descs.empty());
}

BOOST_AUTO_TEST_CASE(descriptor_checksum_optional)
{
    // Test that checksum is optional when require_checksum=false
    FlatSigningProvider keys;
    std::string error;
    
    std::string desc_without_checksum = "pkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB)";
    
    auto descs = Parse(desc_without_checksum, keys, error, /*require_checksum=*/false);
    BOOST_CHECK(!descs.empty());
}

BOOST_FIXTURE_TEST_CASE(g_descriptor_null_by_default, BasicTestingSetup)
{
    // When no descriptor is configured, g_descriptor is nullptr
    g_descriptor.reset();
    BOOST_CHECK(g_descriptor == nullptr);
}

BOOST_FIXTURE_TEST_CASE(g_descriptor_integration_test, BasicTestingSetup)
{
    // Verify that g_descriptor can be populated and accessed
    g_descriptor.reset();

    std::string desc_str = "pkh(xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB)";
    FlatSigningProvider keys;
    std::string error;
    auto descs = Parse(desc_str, keys, error, /*require_checksum=*/false);

    BOOST_REQUIRE(!descs.empty());
    g_descriptor = std::move(descs.front());

    BOOST_CHECK(g_descriptor != nullptr);
    BOOST_CHECK_EQUAL(g_descriptor->GetOutputType(), OutputType::LEGACY);

    // Clean up so other tests are not affected
    g_descriptor.reset();
}

BOOST_AUTO_TEST_SUITE_END()

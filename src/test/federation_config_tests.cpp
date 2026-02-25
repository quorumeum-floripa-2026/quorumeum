// Copyright (c) The Quorumeum developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <common/args.h>
#include <key_io.h>
#include <test/util/setup_common.h>

#include <boost/test/unit_test.hpp>

namespace federation_config_tests {

struct FederationTestSetup : public BasicTestingSetup {
    FederationTestSetup() : BasicTestingSetup(ChainType::SIGNET) {}
};

BOOST_FIXTURE_TEST_SUITE(federation_config_tests, FederationTestSetup)

BOOST_AUTO_TEST_CASE(federation_privatekey_is_registered_sensitive)
{
    auto flags = gArgs.GetArgFlags("-federation_privatekey");
    BOOST_REQUIRE(flags.has_value());
    BOOST_CHECK(*flags & ArgsManager::SENSITIVE);
}

BOOST_AUTO_TEST_CASE(federation_privatekey_valid_tprv_decodes)
{
    const std::string valid_tprv = "tprv8ZgxMBicQKsPctz81GgKmkU9KjupnEJQvgq2u7Dm15H7owsaoiBk2hCPJsVUhDchxcmxWKzxfxjNiKJbfN1Y5HRrtHGDE5FVCw73nLbhxzz";
    CExtKey extkey = DecodeExtKey(valid_tprv);
    BOOST_CHECK(extkey.key.IsValid());
}

BOOST_AUTO_TEST_CASE(federation_privatekey_invalid_string_fails_decode)
{
    CExtKey extkey = DecodeExtKey("notavalidkey");
    BOOST_CHECK(!extkey.key.IsValid());
}

BOOST_AUTO_TEST_SUITE_END()

} // namespace federation_config_tests

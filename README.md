# Quorumeum

![quorumeum-logo](doc/logo.png)

## Quorumeum is a federated Bitcoin clone where each block must be signed by 10 out of 100 signing members.

### But there's one problem: We haven't written any code yet.

Quorumeum is group project for a team of developers interested in learning about
the Bitcoin Core workflow in a hackathon environment of "moving fast and breaking things".
In addition to writing code, the group is challenged with project planning,
code review and testing, and community collaboration.

# Project Goal

No consensus changes are necessary. Quorumeum is simply a fork of Bitcoin Core
at the [v30.2 release tag](https://github.com/bitcoin/bitcoin/releases/tag/v30.2),
running on a custom [signet](https://github.com/bitcoin/bips/blob/master/bip-0325.mediawiki) chain.
The signet challenge is a [taproot witness program](https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki)
that commits to a single internal key held by the program administrator, and
a [tapscript](https://github.com/bitcoin/bips/blob/master/bip-0342.mediawiki)
that requires 10 signatures out of 100 public keys for validation.

Before the project begins, the program administrator will generate 101 key pairs,
and compute 101 [taproot descriptors](https://github.com/bitcoin/bips/blob/master/bip-0386.mediawiki)
including their key and the 10-of-100 [tapscript multisig operator](https://github.com/bitcoin/bips/blob/master/bip-0387.mediawiki).
Each of these 101 descriptors will contain one unique private key and 100 public keys.
The first descriptor with the internal private key is kept by the administrator
and the rest are distributed to group participants.

By design, all 101 descriptors will derive the exact same witness program,
and this will be the official Quorumeum signet challenge.

The administrator will start a public listening node configured with this
signet challenge, and provide its IP address to group participants so everyone
can connect together. The administrator may use their internal key to generate
some initial blocks.

### There is only one success condition: New blocks are continuously and automatically being added to the chain, without human intervention, and relying only on Quorumeum full nodes and the peer-to-peer protocol.

# Specification

A required component of this project is the addition of a new P2P message to the
protocol called `signetpsbt`, which transports two data structures:

1. A [PSBT](https://github.com/bitcoin/bips/blob/master/bip-0370.mediawiki)
with [taproot fields](https://github.com/bitcoin/bips/blob/master/bip-0371.mediawiki)
to collect signatures required to satisfy the signet challenge multisig.

2. A serialized [block template](https://bitcoincore.org/en/doc/30.0.0/rpc/mining/getblocktemplate/)
whose `block_data` as specified in BIP 325 matches the commitment in the PSBT.

**The exact wire format of this message must be designed by group participants in
the first stage of the project.**

> [!TIP]
> The use of PSBTs for signet mining is explained (and implemented in Python)
> in [contrib/signet/README.md](contrib/signet/README.md)

> [!TIP]
> The sharing of block templates via p2p was proposed and implemented in the Delving Bitcoin post
> [Sharing block templates](https://delvingbitcoin.org/t/sharing-block-templates/1906)

> [!TIP]
> The last time a new P2P message was added to the protocol was `sendtxrcncl` in
> [p2p: Erlay support signaling (#23443)](https://github.com/bitcoin/bitcoin/pull/23443)

## Protocol

When the timestamp in the current chain tip block header is at least 1 minute old,
any node with a Quorumeum signet challenge private key does the following:

1. Generate a block template
2. Compute the two "virtual transactions" as defined by BIP 325
3. Create and sign a PSBT of the second `to_sign` transaction
4. Relay the PSBT and block template using the new `signetpsbt` p2p message

A node receiving this message does the following:

1. Validate the block template
2. Verify that the PSBT commits to the block template according to BIP 325
3. Verify all current signatures in the PSBT
4. If the PSBT does not have enough signatures to meet the multisig threshold AND
this node has a Quorumeum multisig private key AND it has not signed the PSBT yet,
it computes a signature and adds it to the PSBT, updating the message.
5. If the PSBT has enough signatures to meet the multisig threshold:
    1. Grind the block header nonce until the proof of work is satisfied
    2. Relay the finished block to peers
6. Otherwise:
    1. Continue to relay the PSBT without further adjustment to peers

# Workflow

This repository will be added to a brand new organization on GitHub just for this
project. All group members will be added to the organization as owners. Participants
will be responsible for planning, authoring, reviewing, and merging code when appropriate
to accomplish the goal.

The protocol requires an integration of initialization options, networking, mining, and the wallet.
The project is more likely to succeed by the deadline if these areas of the code are
assigned to smaller teams within the group.

The repository has been configured with a vastly reduced CI testing workflow
(compared to Bitcoin Core) to speed up the process. Many unit and functional
tests have been disabled, as well as various sanitizers and target deployment platforms.
Any of this can be re-enabled at the discretion of the participants. Of course
new tests should be added as part of the development and review process.

> [!TIP]
> One new functional test has already been added as a proof of concept:
> [`feature_quorumeum.py`](test/functional/feature_quorumeum.py). This script
> illustrates how Quorumeum can be implemented using only Python, the RPC interface,
> and a single node with all private keys.

# Cheating

If any group participants share their private keys or attempt to accomplish
the goal of the project using out-of-band communication or centralization
of signing keys, the administrator will shut down the project, post their
disappointment on social media, go drink a beer, and cry.

# Use of LLMs

Every line of code and review comment you submit anywhere in the Bitcoin ecosystem
should be evaluated by the question _"would I trust my life savings with this?"_
or even better _"would I trust two trillion dollars worth of global wealth with this?"_

When other Bitcoin developers agree with you, your reputation increases. When they
disagree with you, your reputation decreases.

So. Go ahead and use LLMs to do your work. But if you would not trust that work
with $2,000,000,000,000 of your own money, you can expect your career in Bitcoin
software development to be insignificant.

# Build and run in a container

```bash
git clone https://github.com/quorumeum-floripa-2026/quorumeum
cd quorumeum
./control.sh build
./control.sh up
./control.sh down
```

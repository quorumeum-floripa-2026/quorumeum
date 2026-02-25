#!/usr/bin/env bash
####################
set -e
####################
####################
setup_tor(){
	mkdir -p /data/tor
	grep 'bitcoin' /etc/tor/torrc 2>&1 1>/dev/null \
	|| cat << EOF >> /etc/tor/torrc
HiddenServiceDir /data/tor/bitcoin
HiddenServicePort 38333 127.0.0.1:38333
EOF
	tor 1>/dev/null || return 0 & 
	while ! [ -e "/data/tor/bitcoin/hostname" ]; do
		sleep 1
	done
	printf "My onion host: $(cat /data/tor/bitcoin/hostname):38333\n"
	sleep 5
}
setup_bitcoind(){
	/app/scripts/setup-bitcoind.sh
	bitcoind -conf=/data/.bitcoin/bitcoin.conf
}
run() {
	setup_tor
	setup_bitcoind
}
####################
run

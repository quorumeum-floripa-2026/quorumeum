#!/usr/bin/env bash
####################
set -e
####################
####################
build_bitcoind(){
	cd /build
	rm -rf /build/build
	printf '\nStarting bitcoin build, time to drink a coffee!\n'
	sleep 5
	cmake -B build -DBUILD_TESTS=OFF -DWITH_ZMQ=ON
	cd build
	local ncores="$(($(lscpu | grep 'per cluster' | awk '{print $4}')-1))"
	if [ 1 -gt "${ncores}" ]; then
		ncores=1
	fi
	printf "Detected ${ncores} cpu cores\n"
	make -j ${ncores} 2>&1
	printf 'Build finished successfully!\n'
}
finish() {
	mkdir -p /bitcoin/bin
	mv \
		/build/build/bin/bitcoin \
		/build/build/bin/bitcoin-cli \
		/build/build/bin/bitcoin-node \
		/build/build/bin/bitcoind \
		/bitcoin/bin/
	rm -rf /build
}
build(){
	build_bitcoind
	finish
}
####################
build

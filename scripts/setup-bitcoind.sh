#!/usr/bin/env bash
####################
set -e
####################
mkdirs(){
	mkdir ${HOME}/.bitcoin
}
set_config(){
	cp /data/.bitcoin/bitcoin.conf ${HOME}/.bitcoin/bitcoin.conf
}
setup(){
	mkdirs
	set_config
}
####################
setup

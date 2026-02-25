#!/usr/bin/env bash
####################
set -e
####################
readonly HELP_MSG='usage: < build | up | down | onion-addr >'
readonly RELDIR="$(dirname ${0})"
####################
eprintln(){
	! [ -z "${1}" ] || eprintln 'eprintln err: undefined message'
	printf "${1}\n" 1>&2
	return 1
}
set_scripts_permissions(){
	chmod +x scripts/*.sh 1>/dev/null 2>&1 || true
}
check_env() {
	[ -e "${RELDIR}/.env" ] || eprintln 'please copy .env.example to .env'
	source "${RELDIR}/.env"
	! [ -z "${SIGNETCHALLENGE}" ] || eprintln 'undefined env SIGNETCHALLENGE'
	! [ -z "${ADDNODE}" ] || eprintln 'undefined env ADDNODE'
	! [ -z "${FEDERATION_MULTISIG}" ] || eprintln 'undefined env FEDERATION_MULTISIG'
	! [ -z "${FEDERATION_PRIVATEKEY}" ] || eprintln 'undefined env FEDERATION_PRIVATEKEY'
}
mkdirs(){
	mkdir -p ${RELDIR}/data/.bitcoin
}
build_bitcoin_conf(){
	[ -e "${RELDIR}/data/.bitcoin/bitcoin.conf" ] \
	|| cat << EOF > "${RELDIR}/data/.bitcoin/bitcoin.conf"
signet=1

[signet]
signetchallenge=${SIGNETCHALLENGE}
bind=0.0.0.0
addnode=${ADDNODE}	
proxy=127.0.0.1:9050
datadir=/data/.bitcoin
federation_multisig=${FEDERATION_MULTISIG}
federation_privatekey=${FEDERATION_PRIVATEKEY}
EOF
}
set_container_engine(){
	if which podman 1>/dev/null; then
		CE='podman'
		return 0
	fi
	if which docker 1>/dev/null; then
		CE='docker'
		return 0
	fi
	eprintln "please install podman or docker (podman is preferred)"
}
common(){
	check_env
	set_scripts_permissions
	mkdirs
	build_bitcoin_conf
	set_container_engine
}
build(){
	${CE} build \
		-f Dockerfile \
		--tag="${IMG_NAME:-bitcoin}" \
		${RELDIR}
}
up(){
	${CE} run --rm \
		-p=${BITCOIN_P2P_PORT:-38333}:38333 \
		-p=${BITCOIN_RPC_PORT:-38332}:38332 \
		--env-file="${RELDIR}/.env" \
		-v=${RELDIR}:/app \
		-v="${RELDIR}/data:/data" \
		--name="${CT_NAME:-bitcoin}" \
		"${IMG_NAME:-bitcoin}" &
}
down(){
	${CE} exec ${CT_NAME:-bitcoin} /app/scripts/shutdown.sh || true
	${CE} stop ${CT_NAME:-bitcoin} 1>/dev/null 2>&1 || true
}
bitcoin-cli(){
	! [ -z "${1}" ] || eprintln 'expected: <command>'
	${CE} exec ${CT_NAME:-bitcoin} bitcoin-cli ${1}
}
onion_addr() {
	printf "$(cat ${RELDIR}/data/tor/bitcoin/hostname):${BITCOIN_P2P_PORT:-38333}\n"
}
####################
common
case ${1} in
	build) build ;;
	up) up ;;
	down) down ;;
	bitcoin-cli) bitcoin-cli "${2}" ;;
	onion-addr) onion_addr ;;
	*) eprintln "${HELP_MSG}" ;;
esac

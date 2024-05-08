#!/usr/bin/env python3
##############################################
# Particle.network multi w3 proxy. Creates a local web3 instance for every supported particle network. This way
# existing applications do not need to be modified at all. Simply specify http:127.0.0.1:port as your HTTPProvider
##############################################
#
import argparse
import json
import logging
import os
import pprint
from functools import partial
from io import DEFAULT_BUFFER_SIZE

import dotenv
import h11
import httpx
import trio
from trio import SocketListener
from web3 import AsyncWeb3
from web3.providers import AsyncBaseProvider
from web3.types import RPCEndpoint

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()


class ParticleSupported:
    supported_networks = [
        (1, "ethereum"),
        (43114, "avalanche"),
        (56, "bsc"),
        (137, "polygon"),
        (10, "optimism"),
        (42161, "arbitrum"),
        (42170, "nova"),
        (8453, "base"),
        (534352, "scroll"),
        (324, "zksync"),
        (1101, "polygonzkevm"),
        (1284, "moonbeam"),
        (1285, "moonriver"),
        (1313161554, "aurora"),
        (1030, "confluxespace"),
        (22776, "mapprotocol"),
        (728126428, "tron"),
        (42220, "celo"),
        (25, "cronos"),
        (250, "fantom"),
        (100, "gnosis"),
        (1666600000, "harmony"),
        (128, "heco"),
        (321, "kcc"),
        (8217, "klaytn"),
        (1088, "metis"),
        (42262, "oasisemerald"),
        (66, "okc"),
        (321, "platon"),
        (108, "thundercore"),
    ]

    @property
    def networks(self) -> list[tuple[int, str]]:
        return self.supported_networks

    @property
    def chain_ids(self) -> list[int]:
        return [network[0] for network in self.networks]

    def is_supported_cid(self, cid: int) -> bool:
        return self.chain_ids.__contains__(cid)

    def validate_cid_list(self, cids: list[int]) -> list[tuple[int, str]]:
        ret = []
        if cids == [0]:
            cids = self.chain_ids
        for x, c in enumerate(cids):
            if not self.is_supported_cid(c):
                print('[!] ChainId %s not supported' % c)
            else:
                ret.append((c, self.cid_to_chain_name(c)))
        return ret

    def chain_name_to_cid(self, name: str) -> int:
        for c in self.networks:
            if c[1].lower() == name:
                return c[0]
        raise UnsupportedParticleChainName(name)

    def cid_to_chain_name(self, cid: int) -> str | bool:
        for c in self.networks:
            if c[0] == cid:
                return c[1]
        return False


class ParticleAuthRequired(Exception):
    pass


class NoChainSpecified(Exception):
    pass


class UnsupportedParticleChainName(Exception):
    pass


class ParticleWeb3Provider(AsyncBaseProvider):
    def __init__(self, chain_id: int = 0, chain_name: str = None, _project_id: str = None, _project_server_key: str = None):
        self._project_id = _project_id
        if self._project_id is None:
            self._project_id = os.environ.get('PROJECT_ID')
        self._project_server_key = _project_server_key
        if self._project_server_key is None:
            self._project_server_key = os.environ.get('PROJECT_SERVER_KEY')
        self.particle_networks = ParticleSupported()
        if self._project_id is None or self._project_server_key is None:
            raise ParticleAuthRequired("Set PROJECT_ID and PROJECT_SERVER_KEY in .env or specify credentials.")
        if chain_id == 0:
            if chain_name is not None:
                self.chain_id = self.particle_networks.chain_name_to_cid(chain_name)
                assert self.chain_id > 0
            else:
                raise NoChainSpecified("Must either specify a chain nam string or chain id integer.")
        else:
            self.chain_id = chain_id
        self.base_url = "https://rpc.particle.network/evm-chain"
        self.headers = {"Content-Type": "application/json"}
        self.auth = httpx.BasicAuth(self._project_id, self._project_server_key)
        self.client = httpx.AsyncClient(
            auth=self.auth,
            headers=self.headers,
            timeout=60,
            limits=httpx.Limits(max_connections=100),
        )

    async def make_request(self, method: RPCEndpoint, params):
        # Prepare the request payload, ensuring chainId could be included in params if necessary
        payload = {
            "jsonrpc": "2.0",
            "chainId": self.chain_id,
            "method": method,
            "params": params,
            "id": 1,  # Static ID for simplicity, could be made dynamic
        }
        # Send the request
        response = await self.client.post(self.base_url, json=payload)
        response.raise_for_status()  # Ensure to check for HTTP errors
        return response.json()


def create_web3_instance(chain_id) -> AsyncWeb3:
    provider = ParticleWeb3Provider(chain_id)
    return AsyncWeb3(provider)


async def handle_proxy_request(_port: int, w3_instance: AsyncWeb3):
    async with trio. open_nursery() as nursery:
        listeners.append(await nursery.start(trio.serve_tcp, partial(proxy_request_handler, w3_instance), _port))


async def read_req(stream, bufmaxsz=DEFAULT_BUFFER_SIZE, maxreqsz=16384):
    h11_conn = h11.Connection(our_role=h11.SERVER)
    total_bytes_read = 0
    ret = bytes(b"")
    while (h11_nextevt := h11_conn.next_event()) == h11.NEED_DATA:
        bytes_read = await stream.receive_some(bufmaxsz)
        total_bytes_read += len(bytes_read)
        ret += bytes_read
        assert total_bytes_read < maxreqsz, f'Request did not fit in {maxreqsz} bytes'
        h11_conn.receive_data(bytes_read)
    assert isinstance(h11_nextevt, h11.Request), f'{h11_nextevt=} is not a h11.Request'
    return ret

async def proxy_request_handler(w3_instance, request_stream):
    with trio.move_on_after(30):  # timeout for idle connection
        try:
            request = await read_req(request_stream)
            request = request.decode().split('\r\n\r\n')[1]
            json_request = json.loads(request)
            logger.info('Received: %s', json_request)

            response_json = await w3_instance.provider.make_request(json_request['method'], json_request['params'])
            response_data = json.dumps(response_json).encode()

            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(response_data)}\r\n"
                "Connection: close\r\n\r\n"
            )
            await request_stream.send_all(response_headers.encode() + response_data)

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            error_message = "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nServer Error"
            await request_stream.send_all(error_message.encode())


async def start_proxies(start_port: int = 8545, chains: list[int] = 0):
    ps = ParticleSupported()

    chains = ps.validate_cid_list(chains)
    print('Starting ... %s' %  chains)
    next_port = start_port
    c = 0
    async with trio.open_nursery() as nursery:
        for chain_id, chain, in chains:
            _cid = 0
            print('[+] Starting %s w3 proxy on port %s' % (chain, next_port))
            w3 = create_web3_instance(chain_id)
            _cid = await w3.eth.chain_id
            print('[~] Testing connection: Chain: %s, CID: %s' % (chain, _cid))
            nursery.start_soon(handle_proxy_request, next_port, w3, name=str('chain_%s_proxy_on_port_%s' % (chain, port)))
            next_port += 1
            c += 1
    logger.info('Started %s proxies' % c)

if __name__ == "__main__":
    args = argparse.ArgumentParser()
    subparsers = args.add_subparsers(dest='command')
    serve = subparsers.add_parser('serve', help='Start the proxies.')
    serve.add_argument('chains', default=0, type=int, nargs='+', help='The chain ids to create proxies '
                                                                     'for. Default is all particle supported networks.')
    serve.add_argument('-p', '--port', type=int, default=8545, help='Start listening on this port'
                                                                   'and increment for each cid.')
    list_chains = subparsers.add_parser('chains', help='List all supported chains')
    args = args.parse_args()
    if args.command == 'chains':
        pprint.pp(ParticleSupported().supported_networks)
        exit(0)
    elif args.command == 'serve':
        print('[+] Chains: %s' % args.chains)
        listeners: list[SocketListener] = []
        port = args.port
        dotenv.load_dotenv()
        project_id = os.environ.get("PROJECT_ID")
        project_server_key = os.environ.get("PROJECT_SERVER_KEY")
        trio.run(start_proxies, port, args.chains)
    else:
        print('run --help')




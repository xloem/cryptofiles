import base64
import dataclasses
import decimal
import json
import os
import requests

class CryptoFilesException(Exception):
    pass

class CryptoFiles:
    def __init__(self, datadir='~/.datacoin', rpcurl='127.0.0.1:11777', rpcuser=None, rpcpassword=None, rpcport=None):
        if '://' in rpcurl:
            dummy, rpcurl = rpcurl.split('://', 1)
        if '/' in rpcurl:
            rpcurl, dummy = rpcurl.split('/', 1)
        if '@' in rpcurl:
            if rpcuser is not None:
                raise CryptoFilesException('user specified in rpcurl and parameter list')
            rpcuser, rpcurl = rpcurl.split('@', 1)
            if ':' in rpcuser:
                if rpcpassword is not None:
                    raise CryptoFilesException('password specified in rpcurl and parameter list')
                rpcuser, rpcpassword = rpcuser.split(':', 1)
        if ':' in rpcurl:
            if rpcport is not None:
                raise CryptoFilesException('port specified in rpcurl and parameter list')
            rpcurl, rpcport = rpcurl.split(':', 1)
        rpcurl = 'http://{}:{}'.format(rpcurl, rpcport)
        if rpcpassword is None and rpcuser is None:
            datadir = os.path.expanduser(datadir)
            cookiefn = os.path.join(datadir, '.cookie')
            if os.path.exists(cookiefn):
                with open(cookiefn) as cookiefile:
                    rpcuser, rpcpassword = cookiefile.read().split(':', 1)
        self.rpcurl = rpcurl
        self.rpcuser = rpcuser
        self.rpcpassword = rpcpassword
        self.__session = None
        self.genesis_hash, self.genesis_txid = next(self.allblocktxids())

    def rpc(self, apiname, *params):
        if self.__session is None:
            self.__session = requests.Session()
            self.__idcount = 0
        self.__idcount += 1
        result = self.__session.post(
            self.rpcurl,
            auth=(self.rpcuser, self.rpcpassword),
            json={'version': '1.1', 'method': apiname, 'params': params, 'id': self.__idcount}
        ).text
        result = json.loads(result, parse_float=decimal.Decimal)
        if result["error"] is not None:
            raise CryptoFilesException(result['error'])
        if 'result' not in result:
            raise CryptoFilesException({'code': -343, 'message': 'missing JSON-RPC result'})
        return result['result']

    def blockhashes(self, startblock = 0):
        if type(startblock) is str:
            startblock = self.rpc('getblock', startblock)['height']
        height = startblock
        while height <= self.rpc('getblockcount'):
            hash = self.rpc('getblockhash', height)
            yield hash
            height += 1
    def blocktxids(self, blockhash):
        return (
            txid
            for txid in self.rpc('getblock', blockhash)['tx']
        )
    def allblocktxids(self, startblock = 0):
        return (
            (blockhash, txid)
            for blockhash in self.blockhashes(startblock)
            for txid in self.blocktxids(blockhash)
        )

    def __api_exists(self, name):
        helpst = self.rpc('help', name)
        if 'unknown command' not in helpst:
            if helpst[:len(name)] == name:
                return True
        else:
            return False
        # just a way to note unexpected responses with adding small new kinds of errors yet.  please normalise errors.
        raise CryptoFilesException({'code': -9999, 'message': helpst})

    def __default_if_genesis_error(self, default, apiname, txid, *params):
        if txid != self.genesis_txid:
            result = self.rpc(apiname, txid, *params)
            return result
        try:
            return self.rpc(apiname, txid, *params)
        except CryptoFilesException as e:
            return default

    @staticmethod
    def __error_to_return(api, *params, **kwparams):
        try:
            return api(*params, **kwparams)
        except Exception as error:
            return error

    def has_getdata(self):
        return self.__api_exists('getdata')

    def allgetdata(self, startblock = 0):
        if not self.has_getdata():
            return []
        return (
            ChainData(
                self,
                self.__error_to_return(base64.b64decode, data, None, True),
                txid,
                blockhash,
                'getdata'
            )
            for data, txid, blockhash in (
                (self.__default_if_genesis_error('', 'getdata', txid), txid, blockhash)
                for blockhash, txid in self.allblocktxids(startblock)
            )
            if len(data)
        )

@dataclasses.dataclass
class ChainData:
    chain : CryptoFiles
    data : bytes
    txid : str
    blockhash : str
    type : str
        
class Datacoin(CryptoFiles):
    def __init__(self, datadir='~/.datacoin', rpcurl='127.0.0.1:11777', rpcuser=None, rpcpassword=None, rpcport=None):
        super().__init__(datadir, rpcurl, rpcuser, rpcpassword, rpcport)
        
class BitcoinSV(CryptoFiles):
    def __init__(self, datadir='~/.bitcoin.sv', rpcurl='127.0.0.1:8332', rpcuser=None, rpcpassword=None, rpcport=None):
        super().__init__(datadir, rpcurl, rpcuser, rpcpassword, rpcport)

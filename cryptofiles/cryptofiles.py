import base64
import dataclasses
import decimal
import json
import os
import requests
import typing

class CryptoFilesException(Exception):
    pass

class CryptoFiles:
    def __init__(self, datadir='~/.datacoin', rpcurl='127.0.0.1:11777', rpcuser=None, rpcpassword=None, rpcport=None):
        self._localparams = (datadir, rpcurl, rpcuser, rpcpassword, rpcport)
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
        self.chain_name, self.genesis_hash, self.genesis_txid = None, None, None

    def identifiers(self):
        if self.chain_name is None:
            self.genesis_hash, self.genesis_txid = next(self.allblocktxids())
            self.chain_name = self.rpc('getnetworkinfo')['subversion'][1:-1].split(':',1)[0]
        return (
            self.chain_name,
            self.genesis_hash,
            self.genesis_txid
        )

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
            error = result['error']
        elif 'result' not in result:
            error = {'code': -343, 'message': 'missing JSON-RPC result'}
        else:
            error = None
        if error is not None:
            raise CryptoFilesException(error['message'], error, apiname, *params)
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
        if txid != self.identifiers()[2]:
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
    filename : str = None
    contenttype : str = None
    parsed : typing.Any = None
    
    def __init__(self, chain : CryptoFiles, data : bytes, txid : str, blockhash : str, type : str):
        self.chain = chain
        self.data = data
        self.txid = txid
        self.blockhash = blockhash
        self.type = type
        self.parsed = None

        try:
            self.parsed = DatacoinEnvelope(self)
        except Exception as e:
            pass

import os
import sqlite3
class Database:
    def __init__(self, path, *chains):
        os.makedirs(path)
        self.db = sqlite3.connect(os.path.join(path, 'cryptofiles.db'))
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS chains
                 (id INT PRIMARY KEY, name text, genesis text, params text,
                  CONSTRAINT UC_chains UNIQUE (name, genesis));
        ''')
        self.db.commit()
        self.chains = {}
        for chain in chains:
            self.connect_chain(chain)
        for id, name, genesis, params in self.db.execute('SELECT * FROM chains'):
            if id in self.chains or params is None:
                continue
            chain = CryptoFiles(*params)
            chainname, chaingenesis, chaintxid = chain.identifiers()
            if name == chainname and genesis == chaingenesis:
                self.chains[id] = chain
            else:
                self.db.execute('REPLACE INTO chains (params) VALUES (NULL) WHERE id = ?', id)
        self.db.commit()
    def connect_chain(self, chain):
        name, genesis_blockhash, genesis_txid = chain.identifiers()
        self.db.execute(
            'REPLACE INTO chains (name, genesis, params) VALUES (?,?,?)',
            name,
            genesis_blockchash,
            json.dumps(chain._localparams)
        )
        self.chains[self.db.last_insert_rowid()] = chain
        self.db.commit()
        


import bz2
import hashlib
import lzma
import warnings
from . import envelope_pb2
@dataclasses.dataclass
class DatacoinEnvelope:
    data : bytes
    ids : typing.List[str]
    def __init__(self, chaindata):
        self.envelope = envelope_pb2.Envelope()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.envelope.ParseFromString(chaindata.data)
        if not self.envelope.IsInitialized():
            raise CryptoFilesException('complete datacoin envelope data not found')
        # TotalParts, PartNumber
        # PublicKey is file owner, may be different from transaction publisher, only on 1st part
        # Signature proves PublicKey made file
        # PrevDataHash is hash of first part that this file replaces, the value signed in the previous signature
    @property
    def data(self):
        if self.envelope.Compression == self.envelope.CompressionMethod.Bzip2:
            return bz2.decompress(self.envelope.Data)
        elif self.envelope.Compression == self.envelope.CompressionMethod.Xz:
            return lzma.decompress(self.envelope.Data)
        else:
            return self.envelope.Data
    @property
    def ids(self):
        # envelope files are addressed by content hash, the value that is signed with the signmessage call.
        return [hashlib.sha256(
            bytes(self.envelope.FileName +
            self.envelope.ContentType +
            str(self.envelope.Compression) +
            self.envelope.PublicKey +
            str(self.envelope.PartNumber) +
            str(self.envelope.TotalParts) +
            self.envelope.PrevTxId +
            self.envelope.PrevDataHash +
            str(self.envelope.DateTime) +
            str(self.envelope.version), 'utf-8') +
            self.envelope.Data
        ).hexdigest()]
    def verify(self, chain : CryptoFiles):
        # returns True or False
        return chain.rpc('verifymessage', self.envelope.PublicKey, base64.b64encode(self.envelope.Signature), self.id())
    def sign(self, chain : CryptoFiles):
        sig = chain.rpc('signmessage', self.envelope.PublicKey, self.id())
        self.envelope.Signature = base64.b64decode(sig)

            
class Datacoin(CryptoFiles):
    def __init__(self, datadir='~/.datacoin', rpcurl='127.0.0.1:11777', rpcuser=None, rpcpassword=None, rpcport=None):
        super().__init__(datadir, rpcurl, rpcuser, rpcpassword, rpcport)
        
class BitcoinSV(CryptoFiles):
    def __init__(self, datadir='~/.bitcoin.sv', rpcurl='127.0.0.1:8332', rpcuser=None, rpcpassword=None, rpcport=None):
        super().__init__(datadir, rpcurl, rpcuser, rpcpassword, rpcport)

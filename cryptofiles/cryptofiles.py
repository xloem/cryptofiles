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

    def blockhashes(self, startblock = 0, include = True):
        if type(startblock) is str:
            startblock = self.rpc('getblock', startblock)['height']
        if not include:
            startblock += 1
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
    def allblocktxids(self, startblock = 0, include = True):
        return (
            (blockhash, txid)
            for blockhash in self.blockhashes(startblock, include)
            for txid in self.blocktxids(blockhash)
        )

    def blockdatatype(self, datatype, block):
        if datatype == 'getdata':
            return self.blockgetdata(block)
        else:
            return []

    def blockgetdata(self, blockhash):
        if not self.has_getdata():
            return []
        if type(blockhash) is int:
            blockhash = next(self.blockhashes(blockhash, True))
        return (
            ChainData(
                self,
                self.__error_to_return(base64.b64decode, data, None, True),
                txid,
                blockhash,
                'getdata'
            )
            for data, txid in (
                (self.__default_if_genesis_error('', 'getdata', txid), txid)
                for txid in self.blocktxids(blockhash)
            )
            if len(data)
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

    DATATYPES = ['getdata']
    IDTYPES = ['datacoin-envelope-0', 'datacoin-envelope-2']
    VERSION = 1

    def datatypes(self):
        result = []
        if self.has_getdata():
            result.append('getdata')
        return result

    def has_getdata(self):
        return self.__api_exists('getdata')

    def has_senddata(self):
        return self.__api_exists('senddata')

    def alldatatype(self, datatype, startblock = 0, include = True):
        return (
            chaindata
            for blockhash in self.blockhashes(startblock, include)
            for chaindata in self.blockdatatype(datatype, blockhash)
        )

@dataclasses.dataclass
class ChainData:
    chain : CryptoFiles
    data : bytes
    txid : str
    blockhash : str
    type : str
    #filename : str = None
    contenttype : str = None
    parsed : typing.Any = None

    def __init__(self, chain : CryptoFiles, data : bytes, txid : str, blockhash : str, type : str):
        self.chain = chain
        self.data = data
        self.txid = txid
        self.blockhash = blockhash
        self.type = type
        self.parsed = None

        for Format in (DatacoinEnvelope, BZ2):
            try:
                self.parsed = Format(self)
            except Exception as e:
                pass

import os
import sqlite3
import threading
class Database:
    def __init__(self, path, *chains):
        os.makedirs(path, exist_ok=True)
        self.filename = os.path.join(path, 'cryptofiles.db')
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS `chains`
                    (id INT PRIMARY KEY, name TEXT, genesis TEXT, params TEXT, version INT,
                     CONSTRAINT UC_chains UNIQUE (name, genesis)
                    );
                CREATE TABLE IF NOT EXISTS `index`
                    (id TEXT, chain INT, block TEXT, txid TEXT, filename TEXT, idtype TEXT, datatype TEXT,
                     CONSTRAINT PK_index PRIMARY KEY (id, chain)
                    );
            ''')
        self.chains = {}
        self.threads = {}
        for chain in chains:
            self.connect_chain(chain)
        with self.connection() as db:
            for id, name, genesis, params, version in db.execute('SELECT * FROM chains'):
                if id in self.chains or params is None:
                    continue
                chain = CryptoFiles(*json.loads(params))
                chainname, chaingenesis, chaintxid = chain.identifiers()
                if name == chainname and genesis == chaingenesis:
                    self.connect_chain(chain)
                else:
                    db.execute('REPLACE INTO `chains` (params) VALUES (NULL) WHERE id = ?', id)
    def connection(self):
        return sqlite3.connect(self.filename)
    def connect_chain(self, chain):
        name, genesis_blockhash, genesis_txid = chain.identifiers()
        with self.connection() as db:
            result = db.execute(
                'SELECT id, params, version FROM `chains` WHERE name = ? AND genesis = ?',
                (name, genesis_blockhash)
            ).fetchone()
            if result is None:
                cursor = db.cursor()
                cursor.execute(
                    'INSERT INTO `chains` (name, genesis, params, version) VALUES (?,?,?,?)',
                    (name, genesis_blockhash, json.dumps(chain._localparams), chain.VERSION)
                )
                dbid = cursor.lastrowid
                dbversion = chain.VERSION
            else:
                dbid, dbparams, dbversion = result
                if dbparams != json.dumps(chain._localparams):
                    db.execute(
                        'UPDATE `chains` SET params = ? WHERE id = ?',
                        (json.dumps(chain._localparams), dbid)
                    )
        self.chains[dbid] = {
            'threads': {},
            'chain': chain
        }
        for datatype in chain.DATATYPES:
            thread = threading.Thread(target=self._run(dbid, datatype))
            self.chains[dbid]['threads'][datatype] = thread
            thread.start()
    def _run(self, dbid, datatype):
        def run():
            chain = self.chains[dbid]['chain']
            startpos = -1
            with self.connection() as db:
                last = db.execute('SELECT block FROM `index` WHERE chain = ? AND datatype = ? ORDER BY id DESC LIMIT 1', (dbid, datatype)).fetchone()
            if last is not None:
                startpos = last
            # change to each block, 1 transaction
            for blockhash in chain.blockhashes(startpos, False):
                values = []
                for data in chain.blockdatatype(datatype, blockhash):
                    filename = None
                    if data.parsed is not None:
                        filename = data.parsed.filename
                    values.append([data.txid, dbid, data.blockhash, data.txid,  filename, 'txid', datatype])
                    if data.parsed is not None:
                        for name, value in data.parsed.ids.items():
                            values.append([value, dbid, data.blockhash, data.txid, filename, name, datatype])
                if len(values):
                    for value in values:
                        print(value)
                    with self.connection() as db:
                            db.executemany('INSERT INTO `index` (id, chain, block, txid, filename, idtype, datatype) VALUES (?,?,?,?,?,?,?)', values)
        return run
        


import bz2
import hashlib
import lzma
import warnings

@dataclasses.dataclass
class BZ2:
    data : bytes
    ids : typing.Iterable[str] = ()
    filename : str = None
    def __init__(self, chaindata):
        self.chaindata = chaindata
        data = self.data
    @property
    def data(self):
        return bz2.decompress(self.chaindata.data)

from . import envelope_pb2
@dataclasses.dataclass
class DatacoinEnvelope:
    data : bytes
    ids : typing.List[str]
    filename : str
    def __init__(self, chaindata):
        self.chaindata = chaindata
        envelope = self._envelope
    @property
    def _envelope(self):
        envelope = envelope_pb2.Envelope()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            envelope.ParseFromString(self.chaindata.data)
        if not envelope.IsInitialized():
            raise CryptoFilesException('complete datacoin envelope data not found')
        # TotalParts, PartNumber
        # PublicKey is file owner, may be different from transaction publisher, only on 1st part
        # Signature proves PublicKey made file
        # PrevDataHash is hash of first part that this file replaces, the value signed in the previous signature
        return envelope
    @property
    def data(self):
        envelope = self._envelope
        if envelope.Compression == envelope.CompressionMethod.Bzip2:
            return bz2.decompress(envelope.Data)
        elif envelope.Compression == envelope.CompressionMethod.Xz:
            return lzma.decompress(envelope.Data)
        else:
            return envelope.Data
    @property
    def filename(self):
        return self._envelope.FileName
    @property
    def ids(self):
        # envelope files are addressed by content hash, the value that is signed with the signmessage call.
        result = {}
        envelope = self._envelope
        if envelope.version == 2:
            result['datacoin-envelope-2'] = hashlib.sha256(
                bytes(envelope.FileName +
                envelope.ContentType +
                str(envelope.Compression) +
                envelope.PublicKey +
                str(envelope.PartNumber) +
                str(envelope.TotalParts) +
                envelope.PrevTxId +
                envelope.PrevDataHash +
                str(envelope.DateTime) +
                str(envelope.version), 'utf-8') +
                envelope.Data
            ).hexdigest()
        # the older envelope format just hashed the data, not the envelope
        result['datacoin-envelope-0'] = hashlib.sha256(envelope.Data).hexdigest()
        return result
    def verify(self, chain : CryptoFiles):
        # returns True or False
        envelope = self._envelope
        return chain.rpc('verifymessage', envelope.PublicKey, base64.b64encode(envelope.Signature), self.id())
    def sign(self, chain : CryptoFiles):
        envelope = self._envelope
        sig = chain.rpc('signmessage', envelope.PublicKey, self.id())
        envelope.Signature = base64.b64decode(sig)

            
class Datacoin(CryptoFiles):
    def __init__(self, datadir='~/.datacoin', rpcurl='127.0.0.1:11777', rpcuser=None, rpcpassword=None, rpcport=None):
        super().__init__(datadir, rpcurl, rpcuser, rpcpassword, rpcport)
        
class BitcoinSV(CryptoFiles):
    def __init__(self, datadir='~/.bitcoin.sv', rpcurl='127.0.0.1:8332', rpcuser=None, rpcpassword=None, rpcport=None):
        super().__init__(datadir, rpcurl, rpcuser, rpcpassword, rpcport)


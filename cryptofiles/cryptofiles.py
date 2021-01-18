from bitcoin_requests import BitcoinRPC
import os

class DatacoinException(Exception):
    pass

class CryptoFiles:
    def __init__(self, datadir='~/.datacoin', rpcurl='127.0.0.1:11777', rpcuser=None, rpcpassword=None, rpcport=None):
        if '://' in rpcurl:
            dummy, rpcurl = rpcurl.split('://', 1)
        if '/' in rpcurl:
            rpcurl, dummy = rpcurl.split('/', 1)
        if '@' in rpcurl:
            if rpcuser is not None:
                raise DatacoinException('user specified in rpcurl and parameter list')
            rpcuser, rpcurl = rpcurl.split('@', 1)
            if ':' in rpcuser:
                if rpcpassword is not None:
                    raise DatacoinException('password specified in rpcurl and parameter list')
                rpcuser, rpcpassword = rpcuser.split(':', 1)
        if ':' in rpcurl:
            if rpcport is not None:
                raise DatacoinException('port specified in rpcurl and parameter list')
            rpcurl, rpcport = rpcurl.split(':', 1)
        rpcurl = 'http://{}:{}'.format(rpcurl, rpcport)
        if rpcpassword is None and rpcuser is None:
            datadir = os.path.expanduser(datadir)
            cookiefn = os.path.join(datadir, '.cookie')
            if os.path.exists(cookiefn):
                with open(cookiefn) as cookiefile:
                    rpcuser, rpcpassword = cookiefile.read().split(':', 1)
        self.rpc = BitcoinRPC(rpcurl, rpcuser, rpcpassword)
    def blockhashes(self):
        height = 0
        while height <= self.rpc.getblockcount():
            yield self.rpc.getblockhash(height)
            height += 1
    def alltxids(self):
        return (
            txid
            for hash in self.blockhashes()
            for txid in self.rpc.getblock(hash)['tx']
        )

    def has_getdata(self):
        raise NotImplementedError()

    def files(self):
        for hash in self.blockhashes():
            print(self.rpc.getblock(hash))
            raise Exception()
            
        

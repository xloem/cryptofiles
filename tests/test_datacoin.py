def index(iterable, index):
    count = 0
    for item in iterable:
        if count == index:
            return item
        count += 1
    assert not 'iterable length less than index'

def range(iterable, start, end):
    count = 0
    result = []
    for item in iterable:
        if count == end:
            break
        if count >= start:
            result.append(item)
        count += 1
    assert len(result) == end - start
    assert count == end
    return result

def test_utils():
    import cryptofiles
    cf = cryptofiles.CryptoFiles('~/.datacoin')
    utils = cryptofiles.CryptoFiles
    assert index(utils.blockhashes(cf), 0) == '1d724e874ee9ea571563239bde095911f128db47c7612fb1968c08c9f95cabe8'
    assert range(utils.allblocktxids(cf), 0, 3) == [
        ('1d724e874ee9ea571563239bde095911f128db47c7612fb1968c08c9f95cabe8','fe5d7082c24c53362f6b82211913d536677aaffafde0dcec6ff7b348ff6265f8'),
        ('8912ffe4f689c346ebfd9d45de018c917bb3b130b33bc957a358a72f9350ac7e','9b4ee2109e25abbdbff569d7b85eb6c6da05493cec9faa0126e58c53d9b9f2b4'),
        ('6707721be51fce9637422db3b9a736cd728d629bbf94c4ff4f9832468270ed47','1b6938cdb4fb29540caf1dd89454a07ff76477d76f50207ffb3102a1224b8442')
    ]
    firstgetdata = index(utils.allgetdata(cf, 18580), 0)
    assert firstgetdata.data == b'Hello Data\n'
    assert firstgetdata.txid == '39d542f56622d57a09f4e6bc05ce1abbb63e24430e71c26c03d3781a33afb302'
    assert firstgetdata.blockhash == '4c6dac1ec6c5131994a47d5a020adf2ef968222be88cc4a761ff283658c4af92'

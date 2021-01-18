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
    assert range(utils.alltxids(cf), 0, 3) == [
        'fe5d7082c24c53362f6b82211913d536677aaffafde0dcec6ff7b348ff6265f8',
        '9b4ee2109e25abbdbff569d7b85eb6c6da05493cec9faa0126e58c53d9b9f2b4',
        '1b6938cdb4fb29540caf1dd89454a07ff76477d76f50207ffb3102a1224b8442'
    ]

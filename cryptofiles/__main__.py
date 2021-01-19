from cryptofiles import *

db = Database('.')
for Chain in (Datacoin, BitcoinSV):
    try:
        db.connect_chain(Chain())
    except Exception as e:
        raise e
        print(e)
input()

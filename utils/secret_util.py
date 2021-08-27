import pytz
import base64
import traceback
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from datetime import datetime

public_key_path = r'Configs/public.pem'


class SignHTTP():
    def __init__(self):
        self.public_key = RSA.import_key(open(public_key_path).read())
        self.now_timestamp = datetime.now(pytz.timezone('UTC')).timestamp()
        self.max_timedelta_x = 60

    def verify_sign(self, body):
        sign = body.get('sign')
        nonce = body.get('nonce')
        message = body.get('message')
        _time = body.get('_time')
        if not sign or not nonce:
            print('no sign or no nonce.')
            return False
        sign = sign.encode()
        nonce = nonce.encode()
        signer = SHA.new(nonce)
        signer.update(message.encode())
        signer.update(str(_time).encode())
        try:
            pkcs1_15.new(self.public_key).verify(signer, base64.b64decode(sign))
            if self.now_timestamp - _time > self.max_timedelta_x:
                print('_time {} is out of date with now_timestamp'.format(_time, self.now_timestamp))
                return False
            return True
        except ValueError:
            print(traceback.format_exc())
            return False

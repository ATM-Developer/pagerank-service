import base64
import traceback
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from datetime import datetime, timezone, timedelta

public_key_path = r'Configs/public.pem'


# 给请求添加签名 和 验证签名
class SignHTTP():
    def __init__(self):
        self.public_key = RSA.import_key(open(public_key_path).read())  # 公钥
        self.now_timestamp = (datetime.now(timezone.utc) + timedelta(hours=8)).timestamp()
        self.max_timedelta_x = 60

    # 验证签名
    def verify_sign(self, body):
        """

        :param body: 请求主体
        :return:
        """
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
            now_bj_timestamp = self.now_timestamp
            if now_bj_timestamp - _time > self.max_timedelta_x:
                print('_time {} now_timestamp {} cha > 30'.format(_time, now_bj_timestamp))
                return False
            return True
        except ValueError:
            print(traceback.format_exc())
            return False

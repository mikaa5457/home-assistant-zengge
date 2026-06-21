"""Zengge connect API"""
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import binascii
import logging
import hashlib
import urllib
import uuid
import time
import aiohttp

MAGICHUE_COUNTRY_SERVERS = [{'nationName': 'Australian', 'nationCode': 'AU', 'serverApi': 'oameshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'oa.meshbroker.magichue.net'}, {'nationName': 'Avalon', 'nationCode': 'AL', 'serverApi': 'ttmeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'tt.meshbroker.magichue.net'}, {'nationName': 'China', 'nationCode': 'CN', 'serverApi': 'cnmeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'cn.meshbroker.magichue.net'}, {'nationName': 'England', 'nationCode': 'GB', 'serverApi': 'eumeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'eu.meshbroker.magichue.net'}, {'nationName': 'Espana', 'nationCode': 'ES', 'serverApi': 'eumeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'eu.meshbroker.magichue.net'}, {'nationName': 'France', 'nationCode': 'FR', 'serverApi': 'eumeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'eu.meshbroker.magichue.net'}, {'nationName': 'Germany', 'nationCode': 'DE', 'serverApi': 'eumeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'eu.meshbroker.magichue.net'}, {'nationName': 'Italy', 'nationCode': 'IT', 'serverApi': 'eumeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'eu.meshbroker.magichue.net'}, {'nationName': 'Japan', 'nationCode': 'JP', 'serverApi': 'dymeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'dy.meshbroker.magichue.net'}, {'nationName': 'Russia', 'nationCode': 'RU', 'serverApi': 'eumeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'eu.meshbroker.magichue.net'}, {'nationName': 'United States', 'nationCode': 'US', 'serverApi': 'usmeshcloud.magichue.net:8081/MeshClouds/', 'brokerApi': 'us.meshbroker.magichue.net'}]

MAGICHUE_USER_LOGIN_ENDPOINT = "apixp/User001/LoginForUser/ZG"
MAGICHUE_GET_MESH_ENDPOINT = 'apixp/MeshData/GetMyMeshPlaceItems/ZG?userId='
MAGICHUE_GET_MESH_DEVICES_ENDPOINT = 'apixp/MeshData/GetMyMeshDeviceItems/ZG?placeUniID=&userId='

_LOGGER = logging.getLogger(__name__)

def get_country_server(country):
    for item in MAGICHUE_COUNTRY_SERVERS:
        if item['nationCode'] == country:
            return item['serverApi']
    return MAGICHUE_COUNTRY_SERVERS[10]['serverApi']


class ZenggeConnect:

    def __init__(self, username: str, password: str, country: str, installation_id: str = None):
        self._username = username
        self._password = password
        self._country = country
        self._md5password = hashlib.md5(password.encode()).hexdigest()
        self._user_id = None
        self._auth_token = None
        self._device_secret = None
        self._mesh = None
        self._installation_id = installation_id or str(uuid.uuid4())

        server_api = get_country_server(country)
        self._connect_url = "http://" + server_api
        _LOGGER.info("Zengge server set to: %s - %s", country, server_api)

    def generate_timestampcheckcode(self):
        SECRET_KEY = "0FC154F9C01DFA9656524A0EFABC994F"
        timestamp = str(int(time.time()*1000))
        value = ("ZG" + timestamp).encode()
        backend = default_backend()
        key = (SECRET_KEY).encode()
        encryptor = Cipher(algorithms.AES(key), modes.ECB(), backend).encryptor()
        padder = padding.PKCS7(algorithms.AES(key).block_size).padder()
        padded_data = padder.update(value) + padder.finalize()
        encrypted_text = encryptor.update(padded_data) + encryptor.finalize()
        checkcode = binascii.hexlify(encrypted_text).decode()
        return timestamp, checkcode

    async def login(self):
        timestampcheckcode = self.generate_timestampcheckcode()
        timestamp = timestampcheckcode[0]
        checkcode = timestampcheckcode[1]
        payload = dict(userID=self._username, password=self._md5password, appSys='Android', timestamp=timestamp, appVer='', checkcode=checkcode)

        headers = {
            'User-Agent': 'HaoDeng/1.5.7(ANDROID,10,en-US)',
            'Accept-Language': 'en-US',
            'Accept': 'application/json',
            'token': '',
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self._connect_url + MAGICHUE_USER_LOGIN_ENDPOINT, headers=headers, json=payload) as response:
                _LOGGER.info("Zengge server response status: %s", response.status)

                if response.status != 200:
                    raise Exception('Web request failed - %s' % response.status)

                responseJSON = await response.json()

                if responseJSON['ok'] == False:
                    _LOGGER.error('Login failed - ' + responseJSON['err_msg'])
                    raise Exception('Login failed - ' + responseJSON['err_msg'])

                resultJSON = responseJSON['result']
                self._user_id = resultJSON['userId']
                self._auth_token = resultJSON['auth_token']
                self._device_secret = resultJSON['deviceSecret']

    async def credentials(self):
        if self._mesh is not None:
            return self._mesh
        if self._auth_token is not None and self._user_id is not None:
            headers = {
                'User-Agent': 'HaoDeng/1.5.7(ANDROID,10,en-US)',
                'Accept-Language': 'en-US',
                'Accept': 'application/json',
                'token': self._auth_token,
                'Content-Type': 'application/json',
                'Accept-Encoding': 'gzip'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self._connect_url + MAGICHUE_GET_MESH_ENDPOINT + urllib.parse.quote_plus(self._user_id), headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception('Loading data failed - %s' % error_text)
                    result = await response.json()
                    self._mesh = result['result'][0]
                    return self._mesh
        else:
            raise Exception('No login session detected!')

    async def devices(self):
        if self._auth_token is not None and self._user_id is not None:
            headers = {
                'User-Agent': 'HaoDeng/1.5.7(ANDROID,10,en-US)',
                'Accept-Language': 'en-US',
                'Accept': 'application/json',
                'token': self._auth_token,
                'Content-Type': 'application/json',
                'Accept-Encoding': 'gzip'
            }

            placeUniID = self._mesh['placeUniID']
            url = self._connect_url + MAGICHUE_GET_MESH_DEVICES_ENDPOINT.replace("placeUniID=", "placeUniID=" + placeUniID).replace("userId=", "userId=" + urllib.parse.quote_plus(self._user_id))

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception('Device retrieval for mesh failed - %s' % error_text)
                    responseJSON = (await response.json())['result']
                    self._mesh.update({'devices': responseJSON})
                    return responseJSON
        else:
            raise Exception('No login session detected!')

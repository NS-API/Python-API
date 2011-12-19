from xml.etree import cElementTree as ET

import httplib2


class station():
    def __init__(self, xml):
        self.name    = xml.find('{http://openov.nl/protocol/nsapi}name').text
        self.code    = xml.find('{http://openov.nl/protocol/nsapi}code').text
        self.country = xml.find('{http://openov.nl/protocol/nsapi}country').text
        self.lat     = float(xml.find('{http://openov.nl/protocol/nsapi}lat').text)
        self.lon     = float(xml.find('{http://openov.nl/protocol/nsapi}long').text)
        self.alias   = (xml.find('{http://openov.nl/protocol/nsapi}alias').text == 'true')

class stations():
    def __init__(self, username, password):
        self.http = httplib2.Http()
        self.http.follow_redirects = False
        self.http.add_credentials(username, password)

    def fetch(self):
        resp, content = self.http.request("https://webservices.ns.nl/ns-api-stations")
        if resp['status'] == '200':
            content = content.replace('\n', '').replace('\t', '').replace('   ','').replace('  ', '')
            try:
                return ET.XML(content.replace('<stations>', '<stations xmlns="http://openov.nl/protocol/nsapi">'))
            except:
                pass

    def fetchandparse(self):
        root = self.fetch()
        if root is not None:
            return [station(xmlstation) for xmlstation in root.findall('{http://openov.nl/protocol/nsapi}station')]

from xml.etree import cElementTree as ET

import dateutil.parser
import httplib2


class vertrekkendetrein():
    def __init__(self, xml):
        self.ritnummer = int(xml.find('{http://openov.nl/protocol/nsapi}RitNummer').text)
        self.vertrektijd = dateutil.parser.parse(xml.find('{http://openov.nl/protocol/nsapi}VertrekTijd').text)
        self.eindbestemming = xml.find('{http://openov.nl/protocol/nsapi}EindBestemming').text
        self.treinsoort = xml.find('{http://openov.nl/protocol/nsapi}TreinSoort').text
        self.vertrekspoor = xml.find('{http://openov.nl/protocol/nsapi}VertrekSpoor')
        self.spoorwijziging = (self.vertrekspoor.attrib['wijziging'] == 'true')
        self.vertrekspoor = self.vertrekspoor.text

class avt():
    def __init__(self, username, password):
        self.http = httplib2.Http(disable_ssl_certificate_validation=True)
        self.http.follow_redirects = False
        self.http.add_credentials(username, password)

    def fetch(self, station):
        resp, content = self.http.request("https://webservices.ns.nl/ns-api-avt?station=%s" % (station))
        if resp['status'] == '200':
            content = content.replace('\n', '').replace('\t', '').replace('   ','').replace('  ', '')
            try:
                return ET.XML(content.replace('<ActueleVertrekTijden>', '<ActueleVertrekTijden xmlns="http://openov.nl/protocol/nsapi">'))
            except:
                pass

    def fetchandparse(self, *args, **kwargs):
        root = self.fetch(*args, **kwargs)
        if root is not None:
            return [vertrekkendetrein(xmltrein) for xmltrein in root.findall('{http://openov.nl/protocol/nsapi}VertrekkendeTrein')]

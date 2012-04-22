from xml.etree import cElementTree as ET

import httplib2


class product():
    class prijs():
        def __init__(self, xml):
            self.korting = xml.attrib['korting']
            self.klasse  = int(xml.attrib['klasse'])
            self.prijs   = float(xml.text.replace(',', '.'))
    
    def __init__(self, xml):
        self.naam = xml.attrib['naam']
        self.prijzen = [self.prijs(xmlprijs) for xmlprijs in xml.findall('{http://openov.nl/protocol/nsapi}Prijs')]

class prijzen():
    def __init__(self, username, password):
        self.http = httplib2.Http(disable_ssl_certificate_validation=True)
        self.http.follow_redirects = False
        self.http.add_credentials(username, password)

    def fetch(self, from_station, to_station, via_station=None, date_time=None):
        query = 'from=%s&to=%s' % (from_station, to_station)

        if via_station is not None:
            query += '&via=%s' % (via_station)

        if date_time is not None :
            query += '&dateTime=%s' % (date_time.isoformat())

        resp, content = self.http.request("https://webservices.ns.nl/ns-api-prijzen-v2?%s" % (query))
        if resp['status'] == '200':
            content = content.replace('\n', '').replace('\t', '').replace('   ','').replace('  ', '')
            try:
                return ET.XML(content.replace('<Producten>', '<Producten xmlns="http://openov.nl/protocol/nsapi">'))
            except:
                pass

    def fetchandparse(self, *args, **kwargs):
        root = self.fetch(*args, **kwargs)
        if root is not None:
            return [product(xmlproduct) for xmlproduct in root.findall('{http://openov.nl/protocol/nsapi}Product')]

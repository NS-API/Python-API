from xml.etree import cElementTree as ET

import dateutil.parser
import httplib2

def besteffort(xml, tag):
    text = xml.find(xml.find(tag))
    if text is not None:
        if text.text == '':
            return None
        else:
            return text.text

class ongeplandestoring():
    def __init__(self, xml):
        self.id = xml.find('{http://openov.nl/protocol/nsapi}id').text
        self.traject = xml.find('{http://openov.nl/protocol/nsapi}Traject').text
        self.reden = xml.find('{http://openov.nl/protocol/nsapi}Reden').text
        self.bericht = xml.find('{http://openov.nl/protocol/nsapi}Bericht').text
        self.datum = dateutil.parser.parse(xml.find('{http://openov.nl/protocol/nsapi}VertrekTijd').text)

class geplandestoring():
    def __init__(self, xml):
        self.id = xml.find('{http://openov.nl/protocol/nsapi}id').text
        self.traject    = besteffort(xml, '{http://openov.nl/protocol/nsapi}Traject')
        self.periode    = besteffort(xml, '{http://openov.nl/protocol/nsapi}Periode')
        self.reden      = besteffort(xml, '{http://openov.nl/protocol/nsapi}Reden')
        self.advies     = besteffort(xml, '{http://openov.nl/protocol/nsapi}Advies')
        self.bericht    = besteffort(xml, '{http://openov.nl/protocol/nsapi}Bericht')
        self.oorzaak    = besteffort(xml, '{http://openov.nl/protocol/nsapi}Oorzaak')
        self.vertraging = besteffort(xml, '{http://openov.nl/protocol/nsapi}Vertraging')

class storingen():
    def __init__(self, username, password):
        self.http = httplib2.Http()
        self.http.follow_redirects = False
        self.http.add_credentials(username, password)

    def fetch(self, station=None, actual=None, unplanned=None):
        query = ''
        if station is not None:
            query += 'station=%s' % (station)
        
        if actual is not None:
            query += 'actual=%s' % (str(actual).lower())
        
        if unplanned is not None:
            query += 'unplanned=%s' % (str(unplanned).lower())

        resp, content = self.http.request("https://webservices.ns.nl/ns-api-storingen?%s" % (query))
        if resp['status'] == '200':
            content = content.replace('\n', '').replace('\t', '').replace('   ','').replace('  ', '')
            try:
                return ET.XML(content.replace('<Storingen>', '<Storingen xmlns="http://openov.nl/protocol/nsapi">'))
            except:
                pass

    def fetchandparse(self, station=None, actual=None, unplanned=None):
        root = self.fetch(station, actual, unplanned)
        if root is not None:
            ongepland = [ongeplandestoring(xmlstoring) for xmlstoring in root.findall('{http://openov.nl/protocol/nsapi}Ongepland/{http://openov.nl/protocol/nsapi}Storing')]
            gepland   = [  geplandestoring(xmlstoring) for xmlstoring in root.findall('{http://openov.nl/protocol/nsapi}Gepland/{http://openov.nl/protocol/nsapi}Storing')]

            return (ongepland + gepland)

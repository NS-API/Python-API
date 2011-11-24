from xml.etree import cElementTree as ET
from time import time, mktime, strftime, localtime
from sleekxmpp.plugins.xep_0060.stanza.pubsub_event import Event, EventItems, EventItem, EventRetract

import httplib2

class NSAPIStoringen():
    def __init__(self, username, password, xmpp=None):
        user_agent = 'nsapi_pubsub/0.1'
        self.headers = { 'User-Agent' : user_agent, \
                         'Accept-Encoding': 'gzip, deflate, compress;q=0.9', \
                         'Keep-Alive': '300', 'Connection': 'keep-alive', \
                         'Cache-Control': 'max-age=0' }
        self.h = httplib2.Http()
        self.h.follow_redirects = False
        self.h.add_credentials(username, password)

        self.xmpp = xmpp

        self.storingen = {} # storingen

    def query(self, code):
        self.fetch([code])
        if code in self.storingen:
            return self.storingen[code]['storingen']
        
        return None

    def fetch(self, codes, cache=True):
        """
        <Storingen>
          <Ongepland>
            <Storing>
              <id>prio-13345</id>
              <Traject>'s-Hertogenbosch-Nijmegen</Traject>
              <Reden>beperkingen op last van de politie</Reden>
              <Bericht></Bericht>
              <Datum>2010-12-16T11:16:00+0100</Datum>
            </Storing>
          </ongepland>
          <Gepland>
            <Storing>
              <id>2010_almo_wp_18_19dec</id>
              <Traject>Almere Oostvaarders-Weesp/Naarden-Bussum</Traject>
              <Periode>zaterdag 18 en zondag 19 december</Periode>
              <Reden>Beperkt treinverkeer, businzet en/of omreizen, extra reistijd 15-30 min.</Reden>
              <Advies>Maak gebruik van de overige treinen of de bussen: 
                reis tussen Weesp en Almere Centrum met de NS-bus in
                plaats van de trein tussen Almere Centrum en Lelystad 
                Centrum rijden vier Sprinters per uur reis tussen Almere
                Muziekwijk en Naarden-Bussum via Weesp</Advies>
              <Bericht></Bericht>
            </Storing>
          </Gepland>
        </Storingen>
        """

        now = int(time())
        for code in codes:
            if cache and code in self.storingen and self.storingen[code]['expire'] > now:
                continue

            resp, content = self.h.request("https://webservices.ns.nl/ns-api-storingen?station=%s&actueel=true&unplanned=true"%(code))
            if resp['status'] == '200':
                root = ET.XML(content.replace('\n', '').replace('\t', '').replace('    ', ''))
                self.storingen[code] = {}
                self.storingen[code]['expire'] = now + 600
                self.storingen[code]['storingen'] = {}
                self.storingen[code]['storingen']['gepland'] = {}
                self.storingen[code]['storingen']['actueel'] = {}

                for elem in root.findall('.//Gepland/Storing'):
                    id = elem.find('.//id')
                    if id is not None:
                        self.storingen[code]['storingen']['gepland'][id.text] = elem
                   
                for elem in root.findall('.//Ongepland'):
                    id = elem.find('.//id')
                    if id is not None:
                        self.storingen[code]['storingen']['actueel'][id.text] = elem
 
if __name__ == '__main__':
    from secret import username, password
    import sys
    storingen = NSAPIStoringen(username, password)
    print storingen.query(sys.argv[1])

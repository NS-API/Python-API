from xml.etree import cElementTree as ET

import time
import dateutil.parser
import httplib2


class reismogelijkheid():
    class verstoring():
        def __init__(self, xml):
            self.id = xml.find('{http://openov.nl/protocol/nsapi}Id').text
            self.ernstig = (xml.find('{http://openov.nl/protocol/nsapi}Ernstig').text == 'true')
            self.text = xml.find('{http://openov.nl/protocol/nsapi}Text').text
    
    class reisdeel():
        class reisstop():
            def __init__(self, xml):
                self.naam = xml.find('{http://openov.nl/protocol/nsapi}Naam').text
                self.tijd = dateutil.parser.parse(xml.find('{http://openov.nl/protocol/nsapi}Tijd').text)

                self.spoor = xml.find('{http://openov.nl/protocol/nsapi}Spoor')
                self.spoorwijziging = None

                if self.spoor is not None:
                    self.spoorwijziging = (self.spoor.attrib['wijziging'] == 'true')
                    self.spoor = self.spoor.text

        def __init__(self, xml):
            self.vervoertype = xml.find('{http://openov.nl/protocol/nsapi}VervoerType').text
            self.ritnummer = xml.find('{http://openov.nl/protocol/nsapi}RitNummer').text
            self.reissoort = xml.attrib['reisSoort']
            self.reisstops = [self.reisstop(xmlstop) for xmlstop in xml.findall('{http://openov.nl/protocol/nsapi}ReisStop')]

    def __init__(self, xml):
        self.aantaloverstappen = xml.find('{http://openov.nl/protocol/nsapi}AantalOverstappen')
        if self.aantaloverstappen is not None:
            self.aantaloverstappen = self.aantaloverstappen.text

        self.gepland = {}
        self.gepland['reistijd']     = time.strptime(xml.find('{http://openov.nl/protocol/nsapi}GeplandeReisTijd').text, '%H:%M')
        self.gepland['aankomsttijd'] = dateutil.parser.parse(xml.find('{http://openov.nl/protocol/nsapi}GeplandeAankomstTijd').text)
        self.gepland['vertrektijd']  = dateutil.parser.parse(xml.find('{http://openov.nl/protocol/nsapi}GeplandeVertrekTijd').text)
        
        self.actueel = {}
        self.actueel['reistijd']     = time.strptime(xml.find('{http://openov.nl/protocol/nsapi}ActueleReisTijd').text, '%H:%M')
        self.actueel['aankomsttijd'] = dateutil.parser.parse(xml.find('{http://openov.nl/protocol/nsapi}ActueleAankomstTijd').text)
        self.actueel['vertrektijd']  = dateutil.parser.parse(xml.find('{http://openov.nl/protocol/nsapi}ActueleVertrekTijd').text)

        self.reisdelen = [self.reisdeel(xmldeel) for xmldeel in xml.findall('{http://openov.nl/protocol/nsapi}ReisDeel')]

        self.melding = xml.find('{http://openov.nl/protocol/nsapi}Melding')
        if self.melding is not None:
            self.melding = self.verstoring(self.melding)

        self.aankomstvertraging = xml.find('{http://openov.nl/protocol/nsapi}AankomstVertraging')
        if self.aankomstvertraging is not None:
            self.aankomstvertraging = self.aankomstvertraging.text


class treinplanner():
    def __init__(self, username, password):
        self.http = httplib2.Http()
        self.http.follow_redirects = False
        self.http.add_credentials(username, password)

    def fetch(self, from_station, to_station, via_station=None, previous_advices=5, next_advices=5, date_time=None, departure=True, hsl_allowed=True, year_card=False):
        query = 'fromStation=%s&toStation=%s' % (from_station, to_station)

        if via_station is not None:
            query += '&viaStation=%s' % (via_station)

        if previous_advices < 5:
            query += '&previousAdvices=%d' % (previous_advices)

        if next_advices < 5:
            query += '&nextAdvices=%d' % (next_advices)
        
        if date_time is not None :
            query += '&dateTime=%s' % (date_time.isoformat())

        if departure == False:
            query += '&departure=false'

        if hsl_allowed == False:
            query += '&hslAllowed=false'
        
        if year_card == True:
            query += '&yearCard=true'
     
        resp, content = self.http.request("https://webservices.ns.nl/ns-api-treinplanner?%s" % (query))
        if resp['status'] == '200':
            content = content.replace('\n', '').replace('\t', '').replace('   ','').replace('  ', '')
            try:
                return ET.XML(content.replace('<ReisMogelijkheden>', '<ReisMogelijkheden xmlns="http://openov.nl/protocol/nsapi">'))
            except:
                pass

    def fetchandparse(self, from_station, to_station, via_station=None, previous_advices=5, next_advices=5, date_time=None, departure=True, hsl_allowed=True, year_card=False):
        root = self.fetch(from_station, to_station, via_station, previous_advices, next_advices, date_time, departure, hsl_allowed, year_card)
        if root is not None:
            return [reismogelijkheid(xmlmogelijkheid) for xmlmogelijkheid in root.findall('{http://openov.nl/protocol/nsapi}ReisMogelijkheid')]

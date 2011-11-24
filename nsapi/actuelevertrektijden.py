from xml.etree import cElementTree as ET
from time import time, mktime, strftime, localtime
from sleekxmpp.plugins.xep_0060.stanza.pubsub_event import Event, EventItems, EventItem, EventRetract

import httplib2
import iso8601
import sqlite3

class NSAPIActueleVertrekTijden():
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

        self.conn = sqlite3.connect('subscriptions.db', check_same_thread = False)
        self.conn.isolation_level = None

        self.avt = {} # actuelevertrektijden
        self.treinen = {} # virtuele node voor lookup per rit

    def unsubscribe(self, jid, station, ritnummer, item):
        sql = "DELETE FROM sub_avt WHERE jid = ? AND station = ? AND ritnummer = ? AND item = ?;"
        c = self.conn.cursor()
        param = [jid, station, ritnummer, item]
        try:
            c.execute(sql, param)
            c.close()
            self.conn.commit()
        except sqlite3.Error, e:
            print e
            return False

        return True

    def subscribe(self, jid, station, ritnummer, item):
        sql = "INSERT INTO sub_avt (jid, station, ritnummer, item) VALUES (?, ?, ?, ?);"
        c = self.conn.cursor()
        param = [jid, station, ritnummer, item]
        try:
            c.execute(sql, param)
            c.close()
            self.conn.commit()
        except sqlite3.Error, e:
            print e
            return False


        print 'subscribe'
        return True

    def query(self, code):
        self.fetch([code])
        if code in self.avt:
            return self.avt[code]['treinen']
        
        return None

    def fetch(self, codes, cache=True):
        """
        <ActueleVertrekTijden>
        <VertrekkendeTrein>
        <VertrekTijd>2011-04-12T02:07:00+0200</VertrekTijd>
        <VertrekVertraging>PT5M</VertrekVertraging>
        <VertrekVertragingTekst>+5 min</VertrekVertragingTekst>
        <EindBestemming>Rotterdam Centraal</EindBestemming>
        <TreinSoort>Intercity</TreinSoort>
        <RouteTekst>Amsterdam C, Schiphol, Den Haag HS</RouteTekst>
        <VertrekSpoor wijziging="true">14A</VertrekSpoor>
        <Opmerkingen>
          <Opmerking>Niet instappen</Opmerking>
        </Opmerkingen>
        <RitNummer>1234</RitNummer>
        </VertrekkendeTrein>
        </ActueleVertrekTijden>
        """

        now = int(time())
        for code in codes:
            if cache and code in self.avt and self.avt[code]['expire'] > now:
                continue

            resp, content = self.h.request("https://webservices.ns.nl/ns-api-avt?station=%s"%(code))
            if resp['status'] == '200':
                old = None
                if code in self.avt:
                    # pass by reference
                    old = self.avt[code]
                
                root = ET.XML(content.replace('\n', '').replace('\t', ''))

                if root.tag == 'error':
                    print ET.tostring(root)
                    continue

                unixtimes = set()

                for elem in root.findall('.//VertrekTijd'):
                    unixtime = int(mktime(iso8601.parse_date(elem.text.replace('+0200', '+CEST')).utctimetuple())-3600) # Daylight saving
                    unixtimes.add(unixtime)
                    elem.attrib['unixtime'] = str(unixtime)

                if len(unixtimes) == 0:
                    print ET.tostring(root)
                    continue

                first = min(unixtimes)
                last = max(unixtimes) 
                
                new = {}
                new['treinen'] = {}

                if len(root.findall('.//VertrekVertraging')) > 0 or len(root.findall('.//Opmerking')) > 0:
                    new['expire'] = now + 300 # Wanneer er vertragingen zijn of andere onzin, is het station misschien interessant
                elif first > (now + 7200):
                    new['expire'] = first - 3600 # Wanneer de eerst volgende trein pas ergens over twee uur is, kijk over een uurtje maar eens
                elif first > (now + 3600):
                    new['expire'] = now + 1200 # Wanneer de eerst volgend trein pas over een uur is, kijk over twintig minuten maar eens
                elif (last - now) < 4000:
                    new['expire'] = min(first, now + 600)
                else:
                    new['expire'] = now + 600 # In alle andere gevallen, over tien minuten aan de beurt

                for elem in root.findall('.//VertrekkendeTrein'):
                    ritnummer = elem.find('.//RitNummer').text
                    new['treinen'][ritnummer] = elem
                    if ritnummer not in self.treinen:
                        abstract = ET.Element('Trein')
                        for x in ['EindBestemming', 'TreinSoort', 'RouteTekst', 'RitNummer']:
                            app = elem.find(x)
                            if app is not None:
                                abstract.append(app)
                        self.treinen[ritnummer] = {'abstract': abstract, 'stations': set([code])}
                    else:
                        self.treinen[ritnummer]['stations'].add(code)

                self.avt[code] = new

                if self.xmpp is not None and old is None or old['treinen'] is None or (old['treinen'] is not None and len(old['treinen']) == 0):
                    # Er was geen data

                    if len(new['treinen']) > 0:
                        # ...maar er is nu wel data, dus alle
                        # geregistreerde events voor dit station afvuren
                        self.trigger_rit_added(code, new['treinen'].keys())
                        self.trigger_station_added(code)
                    #else:
                    # ...er is geen data
                else:
                    # We hadden data
                    if len(new['treinen']) == 0:
                        # ...maar hebben geen data meer, dus alle
                        # geregistreerde events voor dit station afvuren
                        self.trigger_station_deleted(code, old['treinen'].keys())
                    else:
                        if self.actuelevertrektijden_trigger(code, old['treinen'], new['treinen']):
                            self.trigger_station_added(code)


    def actuelevertrektijden_trigger(self, station, old, new):
        """
            Het is een goed idee om te beginnen met vast te leggen
            wat voor events kunnen worden getriggerd, op stationsniveau.
        """
        deleted = set(old.keys()) - set(new.keys())
        added = set(new.keys()) - set(old.keys())
        maybechanged = set(new.keys()) - added

        if (len(deleted) > 0):
            # verwerk alle verwijderde data, trigger events naar afnemers van de rit, en van het station
            self.trigger_rit_deleted(station, deleted)

        for ritnummer in maybechanged:
            if self.actuelevertrektijden_vertrekkendetrein_diff(station, ritnummer, old[ritnummer], new[ritnummer]):
                added.add(ritnummer)

        if (len(added) > 0):
            # verwerk alle toegevoegde data, trigger events naar afnemers van de rit, en van het station
            self.trigger_rit_added(station, added)

        if len(deleted) > 0 or len(added) > 0:
            return True

        return False

    def actuelevertrektijden_vertrekkendetrein_diff(self, station, ritnummer, old, new):
        oldtag = set([x.tag for x in old])
        newtag = set([x.tag for x in new])

        deleted = oldtag - newtag
        added = newtag - oldtag
        maybechanged = newtag - added

        if (len(deleted) > 0):
            # verwerk alle verwijderde data, trigger events naar afnemers voor deze node, en deze rit
            self.trigger_vertrekkendetrein_item_deleted(station, ritnummer, deleted)

        for tag in maybechanged:
            if old.find(tag).text != new.find(tag).text:
                added.add(tag)

        if (len(added) > 0):
            # verwerk alle toegevoegde/gewijzigde data, trigger events naar afnemers voor deze node, en deze rit
            self.trigger_vertrekkendetrein_item_added(station, ritnummer, added)

        if len(deleted) > 0 or len(added) > 0:
            return True

        return False

    def trigger_vertrekkendetrein_item_deleted(self, station, ritnummer, deleted):
        """<event xmlns='http://jabber.org/protocol/pubsub#event'>
                <items node='stations/%(station)s/avt/%(ritnummer)s'>
                    <retract id='%(station)s_%(ritnummer)s_%(item)s'/>
                </items>
           </event>"""

        sql = """SELECT sub_avt.jid, item FROM sub_avt, subscribers
                   WHERE sub_avt.jid = subscribers.jid AND online = 1 AND
                         station = ? AND ritnummer = ? AND item IN (%s);"""%','.join(['?' for num in xrange(len(deleted))])

        c = self.conn.cursor()
        param = [station, ritnummer]
        param.extend(deleted)
        c.execute(sql, param)
        rows = c.fetchall()
        c.close()

        for row in rows:
            param = {'station': station, 'ritnummer': ritnummer, 'item': row[1]}
            event = Event()
            eventitems = EventItems()
            eventitems['node'] = 'stations/%(station)s/avt/%(ritnummer)s' % param
            eventretract = EventRetract()
            eventretract['id'] = '%(station)s_%(ritnummer)s_%(item)s' % param
            eventitems.append(eventretract)
            event.append(eventitems)
            self.xmpp.send_message(row[0], event, self.boundjid.bare)

    def trigger_rit_deleted(self, station, deleted):
        """<event xmlns='http://jabber.org/protocol/pubsub#event'>
             <items node='stations/%(station)s/avt'>
                 <retract id='%(station)s_%(ritnummer)s'/>
             </items>
           </event>"""

        sql = """SELECT sub_avt.jid, ritnummer FROM sub_avt, subscribers
                    WHERE sub_avt.jid = subscribers.jid AND online = 1 AND station = ? AND
                          ritnummer IN (%s);"""%','.join(['?' for num in xrange(len(deleted))])

        c = self.conn.cursor()
        param = [station]
        param.extend(deleted)
        c.execute(sql, param)
        rows = c.fetchall()
        c.close()

        for row in rows:
            param = {'station': station, 'ritnummer': row[1]}
            event = Event()
            eventitems = EventItems()
            eventitems['node'] = 'stations/%(station)s/avt' % param
            eventretract = EventRetract()
            eventretract['id'] = '%(station)s_%(ritnummer)s' % param
            eventitems.append(eventretract)
            event.append(eventitems)
            self.xmpp.send_message(row[0], event, self.boundjid.bare)

    def trigger_station_deleted(self, station, deleted):
        self.trigger_rit_deleted(station, deleted)
        """<event xmlns='http://jabber.org/protocol/pubsub#event'>
                <items node='stations/%(station)s/avt'>
                    %(ritten)s
                </items>
            </event>"""

        sql = """SELECT sub_avt.jid FROM sub_avt, subscribers
                  WHERE sub_avt.jid = subscribers.jid AND online = 1 AND station = ? AND
                      ritnummer = NULL;"""

        c = self.conn.cursor()
        c.execute(sql, [station])
        rows = c.fetchall()
        c.close()

        if len(rows) > 0:
            event = Event()
            eventitems = EventItems()
            eventitems['node'] = 'stations/%(station)s/avt' % {'station': station}

            for ritnummer in deleted:
                eventretract = EventRetract()
                eventretract['id'] = '%(station)s_%(ritnummer)s' % {'station': station, 'ritnummer': ritnummer}
                eventitems.append(eventretract)

            event.append(eventitems)

            for row in c:
                self.xmpp.send_message(row[0], event, self.boundjid.bare)

    def trigger_vertrekkendetrein_item_added(self, station, ritnummer, added):
        """<event xmlns='http://jabber.org/protocol/pubsub#event'>
                <items node='stations/%(station)s/avt/%(ritnummer)s'>
                     <item id='%(station)s_%(ritnummer)s_%(item)s'>
                         <%(item)s>%(content)s</%(item)s>
                     </item>
                </items>
           </events>"""


        sql = """SELECT sub_avt.jid, item FROM sub_avt, subscribers
                   WHERE sub_avt.jid = subscribers.jid AND online = 1 AND
                         station = ? AND ritnummer = ? AND item IN (%s);"""%','.join(['?' for num in xrange(len(added))])

        c = self.conn.cursor()
        param = [station, ritnummer]
        param.extend(added)
        c.execute(sql, param)
        rows = c.fetchall()
        c.close()

        for row in rows:
            param = {'station': station, 'ritnummer': ritnummer, 'item': row[1]}
            event = Event()
            eventitems = EventItems()
            eventitems['node'] = 'stations/%(station)s/avt/%(ritnummer)s' % param
            eventitem = EventItem()
            eventitem['id'] = '%(station)s_%(ritnummer)s_%(item)s' % param
            eventitem['payload'] = self.avt[station]['treinen'][ritnummer].find(item)
            eventitems.append(eventitem)
            event.append(eventitems)
            self.xmpp.send_message(row[0], event, self.boundjid.bare)

    def trigger_rit_added(self, station, added):
        """<event xmlns='http://jabber.org/protocol/pubsub#event'>
               <items node='stations/%(station)s/avt'>
                   <item id='%(station)s_%(ritnummer)s'>
                       %(content)s
                   </item>
               </items>
           </events>"""

        sql = """SELECT sub_avt.jid, ritnummer FROM sub_avt, subscribers
                    WHERE sub_avt.jid = subscribers.jid AND online = 1 AND
                        station = ? AND ritnummer IN (%s);"""%','.join(['?' for num in xrange(len(added))])
        c = self.conn.cursor()
        param = [station]
        param.extend(added)
        c.execute(sql, param)
        rows = c.fetchall()
        c.close()

        for row in rows:
            param = msg%{'station': station, 'ritnummer': row[1]}
            event = Event()
            eventitems = EventItems()
            eventitems['node'] = 'stations/%(station)s/avt' % param
            eventitem = EventItem()
            eventitem['id'] = '%(station)s_%(ritnummer)s' % param
            eventitem['payload'] = self.avt[station]['treinen'][ritnummer]
            eventitems.append(eventitem)
            event.append(eventitems)
            self.xmpp.send_message(row[0], event, self.boundjid.bare)

        c.close()

    def trigger_station_added(self, station):
        """<event xmlns='http://jabber.org/protocol/pubsub#event'>
                <items node='stations/%(station)s/avt'>
                     %(content)s
                </items>
           </events>"""

        sql = """SELECT sub_avt.jid FROM sub_avt, subscribers
                    WHERE sub_avt.jid = subscribers.jid AND online = 1 AND station = ? AND ritnummer = NULL;"""
        c = self.conn.cursor()
        c.execute(sql, [station])
        rows = c.fetchall()
        c.close()

        if len(rows) > 0:
            event = Event()
            eventitems = EventItems()
            eventitems['node'] = 'stations/%(station)s/avt' % {'station': station}

            for ritnummer in self.avt[station]['treinen'].keys():
                param = {'station': station, 'ritnummer': ritnummer}
                eventitem = EventItem()
                eventitem['id'] = '%(station)s_%(ritnummer)s' % param
                eventitem['payload'] = self.avt[station]['treinen'][ritnummer]
                eventitems.append(eventitem)

            event.append(eventitems)
            
            for row in c:
                self.xmpp.send_message(row[0], event, self.boundjid.bare)



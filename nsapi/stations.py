import httplib2
import sqlite3
from xml.etree import cElementTree as ET
from sleekxmpp.plugins.xep_0060.stanza.pubsub import Items, Item
from namespace import prefix_xmlns

class NSAPIStations():
    def __init__(self, username, password):
        user_agent = 'nsapi_pubsub/0.1'
        self.headers = { 'User-Agent' : user_agent, \
                         'Accept-Encoding': 'gzip, deflate, compress;q=0.9', \
                         'Cache-Control': 'max-age=0' }
        self.h = httplib2.Http()
        self.h.follow_redirects = False
        self.h.add_credentials(username, password)

        self.conn = sqlite3.connect('subscriptions.db', check_same_thread = False)
        self.conn.isolation_level = None

        self.stations = {}
        self.cache_get_items = Items()
        self.cache_get_items['node'] = 'stations'

    def fetch(self):
        """
        <stations>
        <station>
                <name>'s-Gravenhage</name>
                <code>gvc</code>
                <country>NL</country>
                <lat>52.081261</lat>
                <long>4.323973</long>
                <alias>true</alias>
        </station>
        </stations>
        """

        content = ''
        try:
            f = open('/tmp/ns-api-stations', 'r')
            if f:
                content = f.read()
        except:
            pass

        if len(content) == 0:
            resp, content = self.h.request("https://webservices.ns.nl/ns-api-stations")
            if resp['status'] == '200':
                f = open('/tmp/ns-api-stations', 'w')
                f.write(content)
                f.close()

        if len(content) > 0:
            root = ET.XML(content.replace('\n', '').replace('\t', ''))
            stations = root.findall('.//station')
            for station in stations:
                if station.find('country').text == 'NL':
                    code = station.find('code').text
                    if code not in self.stations:
                        self.stations[code] = station
                        
                    if code in self.stations and station.find('alias').text == 'true':
                        aliases = self.stations[code].find('aliases')
                        if aliases is None:
                            aliases = ET.Element('aliases')
                            self.stations[code].append(aliases)
                        alias = ET.SubElement(aliases, 'alias')
                        alias.text = station.find('name').text

                    station.remove(station.find('alias'))
                    
                    item = Item()
                    item['id'] = 'station_%s'%(code)
                    item['payload'] = prefix_xmlns(self.stations[code])
                    self.cache_get_items.append(item)

    def nearest(self, lat, lon, maxitems):
        c = self.conn.cursor()
        sql = "SELECT code FROM stations ORDER BY (((lat - (?))*(lat - (?)))+((long - (?))*(long - (?)))) ASC LIMIT ?;"
        c.execute(sql, [lat, lat, lon, lon, maxitems])
        rows = c.fetchall()
        c.close()
        return rows

    def store(self):
        """
            CREATE TABLE aliases (code varchar(4), alias varchar(48));
            CREATE TABLE stations (code varchar(4), name varchar(48), lat double, long double);
        """

        c = self.conn.cursor()
        sql = "DELETE FROM aliases;"
        c.execute(sql);
        sql = "DELETE FROM stations;"
        c.execute(sql);

        param = [(code, alias.text) for code in self.stations.keys() for alias in self.stations[code].findall('.//aliases/alias')]
        if len(param) > 0:
            sql = "INSERT INTO aliases (code, alias) VALUES (?, ?);"
            c.executemany(sql, param)

        param = [(code, elem.find('name').text, elem.find('lat').text, elem.find('long').text) for code, elem in self.stations.items()]
        if len(param) > 0:
            sql = "INSERT INTO stations (code, name, lat, long) VALUES (?, ?, ?, ?);"
            c.executemany(sql, param)

        c.close()
        self.conn.commit()

    def restore(self):
        self.stations = {}
        self.cache_get_items = Items()
        self.cache_get_items['node'] = 'stations'
 
        c = self.conn.cursor()
        sql = "SELECT code, name, lat, long FROM stations;"
        c.execute(sql);
        rows = c.fetchall()
        c.close()

        for row in rows:
            self.stations[row[0]] = ET.XML('<station><name>%s</name><code>%s</code><country>NL</country><lat>%s</lat><long>%s</long></station>'%(row[1], row[0], str('%.6f'%(float(row[2]))), str('%.6f'%(float(row[3])))))

        c = self.conn.cursor()
        sql = "SELECT code, alias FROM aliases;"
        c.execute(sql);
        rows = c.fetchall()
        c.close()

        for row in rows:
            code = row[0]
            aliases = self.stations[code].find('aliases')
            if aliases is None:
                aliases = ET.Element('aliases')
                self.stations[code].append(aliases)
            alias = ET.SubElement(aliases, 'alias')
            alias.text = row[1]

        for code, elem in self.stations.items():
            item = Item()
            item['id'] = 'station_%s'%(code)
            item['payload'] = prefix_xmlns(elem)
            self.cache_get_items.append(item)

if __name__ == '__main__':
    from secret import username, password
    stations = NSAPIStations(username, password)
    stations.fetch()
    stations.store()
    stations.restore()
    print stations.stations

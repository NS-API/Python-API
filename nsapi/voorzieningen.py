from urllib import urlencode
from BeautifulSoup import BeautifulSoup
import httplib2
import sqlite3

class NSWEBVoorzieningen():
    def __init__(self):
        user_agent = 'nsapi_pubsub/0.1'
        self.headers = { 'User-Agent' : user_agent, \
                         'Accept-Encoding': 'gzip, deflate, compress;q=0.9', \
                         'Cache-Control': 'max-age=0' }
        self.h = httplib2.Http()
        self.h.follow_redirects = False

        self.conn = sqlite3.connect('subscriptions.db', check_same_thread = False)
        self.conn.isolation_level = None

        self.voorzieningen = {}

    def fetchProperties(self):
        resp, content = self.h.request("http://www.ns.nl/reizigers/reisinformatie/stationsvoorzieningen")
        if resp['status'] == '200':
            voorzieningen = BeautifulSoup(content, convertEntities=BeautifulSoup.HTML_ENTITIES).find(id='voorzieningen')
            span = voorzieningen.findAll('span')
            link = voorzieningen.findAll('a')
            span = [x.text for x in span]
            link = [x.text for x in link]
            span.extend(link)

            return span
        return None

    def fetch(self, codes, cache=True):
        for code in codes:
            if cache and code in self.voorzieningen:
                continue

            resp, content = self.h.request('http://www.ns.nl/_hn:action|r124_r1_r2|/reizigers/reisinformatie/stationsvoorzieningen', 'POST', urlencode({'station': code}), headers={'Content-Type':'application/x-www-form-urlencoded'})
            if resp['status'] == '302':
                resp, content = self.h.request(resp['location'])
                if resp['status'] == '200':
                    voorzieningen = BeautifulSoup(content, convertEntities=BeautifulSoup.HTML_ENTITIES).find(id='voorzieningen')
                    
                    span = voorzieningen.findAll('span')
                    link = voorzieningen.findAll('a')

                    span = [x.text for x in span]
                    link = [x.text for x in link]

                    span.extend(link)
                    self.voorzieningen[code] = span

    def store(self):
        """
            CREATE TABLE voorzieningen (code varchar(4), voorziening varchar(128));
        """
        c = self.conn.cursor()
        sql = "DELETE FROM voorzieningen;"
        c.execute(sql)

        sql = "INSERT INTO voorzieningen (code, voorziening) VALUES (?, ?);"
        param = [(code, voorziening) for code in self.voorzieningen.keys() for voorziening in self.voorzieningen[code]]
        c.executemany(sql, param)
        c.close()
        self.conn.commit()

    def storeMaterialized(self):
        props = self.fetchProperties()
        if props is not None:
            c = self.conn.cursor()
            try:
                sql = "DROP TABLE voorzieningen_materialized;"
                c.execute(sql);
            except:
                pass

            sql = "CREATE TABLE voorzieningen_materialized (code VARCHAR(4), %s);"%('"'+'" BOOLEAN, "'.join(props)+'" BOOLEAN')
            c.execute(sql);

            sql = "INSERT INTO voorzieningen_materialized (code, %s) VALUES (%s);"%('"'+'", "'.join(props)+'"', ','.join(['?' for num in xrange(len(props)+1)]))
            params = []

            for code in self.voorzieningen.keys():
                param = [code]
                for prop in props:
                    param.append(prop in self.voorzieningen[code])

                params.append(param)

            c.executemany(sql, params)
            c.close()
            self.conn.commit()

    def restore(self):
        self.voorzieningen = {}
        c = self.conn.cursor()
        sql = "SELECT code, voorziening FROM voorzieningen;"
        c.execute(sql);
        rows = c.fetchall()
        c.close()
        
        for row in rows:
            if row[0] not in self.voorzieningen:
                self.voorzieningen[row[0]] = []

            self.voorzieningen[row[0]].append(row[1])

if __name__ == '__main__':
    import sys
    voorzieningen = NSWEBVoorzieningen()
    voorzieningen.restore()
    voorzieningen.fetch(['vb'])
    voorzieningen.store()
    #voorzieningen.fetchPosibilities()
    voorzieningen.storeMaterialized()
    #print voorzieningen.voorzieningen

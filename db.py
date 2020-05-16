#!/usr/bin/python3
import hashlib
import configparser
import sqlite3

class rss_db:

    def __init__(self,config):
        try:
            self.db = config['Database']['DB']
        except Exception as e:
            print("Config Error!")
            print(e)
            exit()
        try:
            self.connect()
        except Exception as e:
            print("Database Error!")
            print(e)
            exit()
        tables = self.execute("SELECT name FROM sqlite_master WHERE type='table';")

        if(('items',) not in tables):
            self.execute('''CREATE TABLE items
                            (id INTEGER,
                            local_name TEXT NOT NULL,
                            feed TEXT NOT NULL,
                            date TEXT NOT NULL);''')

    def close(self):
        self.conn.close()

    def connect(self):
        self.conn = sqlite3.connect(self.db)
        self.cur = self.conn.cursor()

    def execute(self,command):
        self.connect()
        self.cur.execute(command)
        self.conn.commit()
        text_return = self.cur.fetchall()
        self.close()
        return text_return

    def executevar(self,command,operands):
        self.connect()
        self.cur.execute(command,operands)
        self.conn.commit()
        text_return = self.cur.fetchall()
        self.close()
        return text_return

    def insertItem(self,id, local_name, feed, date):
        self.executevar('INSERT INTO items VALUES(?,?,?,?)', (id, local_name,feed, date))

    def getItems(self):
        items = self.execute('SELECT id,local_name,feed,date FROM items ORDER BY date')
        return items

    def getItemByID(self, id):
        item = self.executevar('SELECT id,local_name,feed,date FROM items WHERE id=?',(id,))
        return item[0]


    def getItemByFeed(self, feed):
        item = self.executevar('SELECT id,local_name,feed,date FROM items WHERE feed=? ORDER BY date',(feed,))
        return item

    def checkItemExists(self, id):
        count = self.executevar('SELECT COUNT(id) FROM items WHERE id=?',(id,))[0][0]
        if(count > 0):
            return True
        else:
            return False

    def removeItem(self, id):
        self.executevar('DELETE FROM items WHERE id=?',(id,))

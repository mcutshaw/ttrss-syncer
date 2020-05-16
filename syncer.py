from ttrss.client import TTRClient
from requests.exceptions import ConnectionError
import requests
from datetime import datetime
from db import rss_db
from bs4 import BeautifulSoup
from multiprocessing import Process
from urllib.parse import urljoin
from downloader import downloader
import socket
import time
from connector import connector
import timeout_decorator


class syncer:
    def __init__(self, config):
        if not self.getlock():
            exit()
        self.config = config
        self.headers = {'User-Agent': self.config['Headers']['headers']}
        self.connector=connector(config)
        self.downloader = downloader(self.headers, self.connector, dataDir=self.config['Main']['Data'], numProcs=4)

    @timeout_decorator.timeout(1200)
    def run(self):
        #os.chdir(self.config['Main']['Data'])
        feeds = self.get_feeds_from_config(self.config)
        threads = []
        print('test1')
        url = self.config['Main']['Url']
        username = self.config['Main']['Username']
        password = self.config['Main']['Password']
        client = TTRClient(url, username, password)
        print('test4')
        client.login()
        print('test2')
        db = rss_db(self.config)

        self.ifRemovedMarkRead(client, db) # first mark articles as read if they have been removed
        print('test3')

        for article_dict in feeds:
            print(article_dict)

            p = Process(target=self.feedCycle, args=(article_dict, self.downloader, db))
            p.start()
            threads.append(p)
        for thread in threads:
            thread.join()
        self.downloader.stop()

    def getlock(self):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            ## Create an abstract socket, by prefixing it with null.
            s.bind( '\0postconnect_gateway_notify_lock')
            return True
        except socket.error as e:
            error_code = e.args[0]
            error_string = e.args[1]
            print("Process already running!")
            return False

    # makes a dict of feed names, count to keep, and filter patterns, release type,
    def get_feeds_from_config(self, config):
        l = []
        for key in self.config['Feeds']:
            name = self.config['Feeds'][key]
            count = self.config[name]['count']
            get_filter = self.config[name]['filter']
            release_type = self.config[name]['release_type']
            l.append({'feed_name': name, 'count': count, 'filter': get_filter,
                      'release_type': release_type})  # feed_name,count,filter_release_type
        return l


    # only function so far that actually needs to support str AND list
    def mark_article_read(self, client, id):
        if type(id) == list:
            for article in id:
                if(article.unread == True):
                    article.toggle_unread()
        else:
            article = client.get_articles([id])[0]
            if(article.unread == True):
                article.toggle_unread()


    def str_to_date(self, string):
        datetime_object = datetime.strptime(string, '%Y-%m-%d %X')
        return datetime_object

    def get_feed(self, client, feed_name):
        for cat in client.get_categories(unread_only=True):
            for feed in cat.feeds():
                if feed.title == feed_name:
                    return feed

    def get_headlines(self, client, feed_name):
        feeds = self.get_feed(client, feed_name)
        if(type(feeds) is None):
            return None
        else:
            headlines = feeds.headlines()
            return headlines

    def get_unread_articles(self, client, feed_name):
        headlines = self.get_headlines(client, feed_name)

        if headlines is None:
            return None
        else:
            l = []
            for headline in headlines:
                art = headline.full_article()
                if art.unread == True:
                    l.append(art)
            return l


    def sort_articles(self, client, articles, release_type, count):
        if count == 0:
            return articles
        elif release_type == 'rolling':
            articles = sorted(articles, key=lambda x: x.updated, reverse=True)
            self.mark_article_read(client, articles[count:])
            return articles[:count]
        elif release_type == 'completion':
            articles = sorted(articles, key=lambda x: x.updated)
            return articles[:count]


    def filtered_download(self, article, get_filter, feed_name, downloader):
        main_page = requests.get(article.link, headers=self.headers)
        soup = BeautifulSoup(main_page.text, 'html.parser')
        paths = get_filter.split(':')
        a = None
        for item in paths:
            print(item)
            if '*' in item:
                item = item.replace('*', '')
                a = [a for a in soup.find_all(item)]
            elif '==' in item:
                l = []
                item = item.split('==')
                for k in a:
                    if k.get(item[0]) == item[1]:
                        l.append(k)
                a = l

            elif '->' in item:
                l = []
                item = item.split('->')
                for k in a:
                    if k.get(item[1]) != None and item[0] in k.get(item[1]):
                        l.append(k)
                a = l

            elif '!' in item:
                item = item.replace('!', '')
                if len(a) > 0:
                    a = a[0]
                    path = urljoin(article.link, a.get(item))
                    print(path)
                    return downloader.addToDownloadQueue(path, feed_name)
                else:
                    return None

            if item == 'attachment':
                return downloader.addToDownloadQueue(article.attachments[0]['1'], feed_name)


    def ifRemovedMarkRead(self, client, db):
        listdir = self.connector.listdir()                                  # grabs local items
        db_items = db.getItems()                                # grabs database items
        for item in db_items:
            # if the name of the database item is not local
            if item[1] not in listdir:
                # remove it from the database
                db.removeItem(item[0])
                # mark it as read on ttrss (if the item was deleted)
                self.mark_article_read(client, item[0])
        db_locs = [name[1] for name in db_items]
        for item in listdir:
            if item not in db_locs:
                # if the item is not in the database remove item
                try:
                    self.connector.remove(item)
                except Exception as e:
                    print(e)

    def feedCycle(self, article_dict, downloader, db):
        url = self.config['Main']['Url']
        username = self.config['Main']['Username']
        password = self.config['Main']['Password']
        client = TTRClient(url, username, password)
        client.login()

        db = rss_db(self.config)

        articles = self.get_unread_articles(client, article_dict['feed_name']) # grab all unread articles

        if articles is None:
            articles = []
        article_ids = [article.id for article in articles]

        for db_article in db.getItemByFeed(article_dict['feed_name']):
            if db_article[0] not in article_ids:
                db.removeItem(db_article[0])

        articles = self.sort_articles(client, articles, article_dict['release_type'], int(article_dict['count']))

        # has to create  new database object because of threads
        for article in articles:
            self.download_articles(rss_db(self.config), article, article_dict, downloader, client)

    def trim_db(self, feed, db, count, release_type):
        if release_type == 'rolling' and count != 0:
            items = db.getItemByFeed(feed)[::-1]
            for item in items[count:]:
                db.removeItem(item[0])


    def download_articles(self, db, art, article_dict, downloader, client):
        if not db.checkItemExists(art.id):
            article_content = self.filtered_download(
                art, article_dict['filter'], article_dict['feed_name'], downloader)
            if article_content == None:
                self.mark_article_read(client, art.id)
            elif article_content == 'Fail':
                pass
            else:
                db.insertItem(art.id, article_content,
                              article_dict['feed_name'], art.updated)
        self.trim_db(article_dict['feed_name'], db, int(
            article_dict['count']), article_dict['release_type'])

# currently:
# get feeds from config
# change into data dir
# for feed:
#     get all unread articles
#     convert articles to article ids
#     check if db articles are still unread, otherwise remove them
#     trim articles
#     download remaining articles

#next:
#get feeds from config
#change into data dir
#create downloader
# for feed:
#     make new thread

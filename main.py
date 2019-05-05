from ttrss.client import TTRClient
import configparser
from requests.exceptions import ConnectionError
import requests
from datetime import datetime
from db import rss_db
from bs4 import BeautifulSoup
import os
from multiprocessing.pool import ThreadPool

config = configparser.ConfigParser()
config.read('rss.conf')
db = rss_db(config)
url = config['Main']['Url']
username = config['Main']['Username']
password = config['Main']['Password']
client = TTRClient(url, username, password)
client.login()

def get_feeds_from_config(config):
        l = []
        for key in config['Feeds']:
                name = config['Feeds'][key]
                count = config[name]['count']
                get_type = config[name]['get_type']
                release_type = config[name]['release_type']
                l.append((name, count, get_type, release_type))
        return l

def mark_article_read(client, id):
        if type(id) == list:
                for article in id:
                        if(article.unread == True):
                                article.toggle_unread()
        else:     
                article = client.get_articles([id])
                article = article[0]
                if(article.unread == True):
                        article.toggle_unread()
                
def str_to_date(string):
        datetime_object = datetime.strptime(string,'%Y-%m-%d %X')
        return datetime_object

def download_item(url,feed_name):
        print(url)
        response = requests.get(url, stream=True, allow_redirects=True)
        local_filename = feed_name.replace(' ','_')+url.split('/')[-1]
        if os.path.isfile(local_filename):
                return local_filename
        handle = open(local_filename, "wb")
        for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:  # filter out keep-alive new chunks
                        handle.write(chunk)
        handle.close()
        return local_filename

def get_feed(client, feed_name):
    l = []
    for cat in client.get_categories(unread_only=True):
        for feed in cat.feeds():
                if(type(feed_name == str)):
                        if(feed.title) == feed_name:
                                return feed
                elif(type(feed_name == list)):
                        if(feed.title in feed_name):
                                l.append(feed)
    return l

def get_headlines(client, feed_name):
        feeds = get_feed(client, feed_name)
        if(feeds == []):
                return None
        elif(type(feed_name) == list):
                l = []
                for feed in feeds:
                        headlines = feed.headlines()
                        l.append(headlines)
                return l
        elif(type(feed_name) == str):
                headlines = feeds.headlines()
                return headlines

def get_articles(client, feed_name):
        headlines = get_headlines(client, feed_name)
        if headlines == None:
                return None
        l = []
        if(type(feed_name) == list):
                for item in headlines:
                        z = []
                        for headline in item:
                                art = headline.full_article()
                                if art.unread == True:
                                        z.append()
                        l.append(z)
                return l
        elif(type(feed_name) == str):
                for headline in headlines:
                        art = headline.full_article()
                        if art.unread == True:
                                l.append(art)
                return l

def article_trim(client, articles, release_type, count):
        if release_type == 'rolling':
                if count == 0:
                        return articles
                articles = sorted(articles, key=lambda x: x.updated, reverse=True)
                mark_article_read(client,articles[count:])
                return articles[:count]
        elif release_type == 'completion':
                if count == 0:
                        return articles
                articles = sorted(articles, key=lambda x: x.updated)
                return articles[:count]
        
def download_article_content(article, get_type, feed_name):
        main_page = requests.get(article.link)
        soup = BeautifulSoup(main_page.text, 'html.parser')
        paths = get_type.split(':')
        a = None
        for item in paths:
                if '*' in item:
                        item = item.replace('*', '')
                        a = [ a for a in soup.find_all(item)]
                elif '#' in item:
                        item = item.replace('#', '')
                        if item not in article.title:
                            return None

                elif '==' in item:
                        l = []
                        item = item.split('==')
                        for k in a:         
                                if k.get(item[0]) == item[1]:
                                        l.append(k)
                        a = l

                elif '...->' in item:
                        l = []
                        item = item.split('...->')
                        for k in a:       
                                if k.parent.parent.get(item[1]) != None and item[0] in k.parent.parent.get(item[1]):
                                        l.append(k)
                        a = l
                elif '..->' in item:
                        l = []
                        item = item.split('..->')
                        for k in a:       
                                if k.parent.get(item[1]) != None and item[0] in k.parent.get(item[1]):
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
                                return download_item(a.get(item), feed_name)
                        else:
                                return None
                elif '/' in item:
                        item = item.replace('/','')
                        if len(a) > 0:
                                a = a[0]
                                return download_item('http://'+article.link.split('/')[2]+a.get(item),feed_name)
                        else:
                                return None
                
                if item == 'attachment':
                        return download_item(article.attachments[0]['1'],feed_name)

def check_finished(client, db):
        listdir = os.listdir()
        db_items = db.getItems()
        for item in db_items:
                if item[1] not in listdir:
                        db.removeItem(item[0])
                        mark_article_read(client,item[0])
        db_locs = [name[1] for name in db_items]
        for item in listdir:
                if item not in db_locs:
                        os.remove(item)
def trim_db(feed, db, count, release_type):
        if release_type == 'rolling' and not count == 0:
                items = db.getItemByFeed(feed)[::-1]
                for item in items[count:]:
                        db.removeItem(item[0])

def download_articles(db, art ):
        if not db.checkItemExists(art.id):
                        article_content = download_article_content(art,item[2],item[0])
                        if article_content == None:
                            mark_article_read(client, art.id)
                        else:
                            db.insertItem(art.id,article_content , item[0], art.updated)
        trim_db(item[0],db, int(item[1]),item[3])

feeds = get_feeds_from_config(config)
os.chdir(config['Main']['Data'])
for item in feeds:
        articles = get_articles(client, item[0])
        if articles == None:
                articles = []
        article_ids =  [article.id for article in articles]
        for db_article in db.getItemByFeed(item[0]):                
                if db_article[0] not in article_ids:
                        db.removeItem(db_article[0])
        articles = article_trim(client,articles,item[3],int(item[1]))

        input_articles = [(rss_db(config), art) for art in articles]
        p = ThreadPool(4)
        
        p.starmap(download_articles,input_articles)                
check_finished(client, db)

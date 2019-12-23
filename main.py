from ttrss.client import TTRClient
import configparser
from requests.exceptions import ConnectionError
import requests
from datetime import datetime
from db import rss_db
from bs4 import BeautifulSoup
import os
from multiprocessing.pool import ThreadPool
from urllib.parse import urljoin

# makes a dict of feed names, count to keep, and filter patterns, release type,
def get_feeds_from_config(config):
    l = []
    for key in config['Feeds']:
        name = config['Feeds'][key]
        count = config[name]['count']
        get_filter = config[name]['filter']
        release_type = config[name]['release_type']
        l.append({'feed_name': name, 'count': count, 'filter': get_filter,
                  'release_type': release_type})  # feed_name,count,filter_release_type
    return l


# only function so far that actually needs to support str AND list
def mark_article_read(client, id):
    if type(id) == list:
        for article in id:
            if(article.unread == True):
                article.toggle_unread()
    else:
        article = client.get_articles([id])[0]
        if(article.unread == True):
            article.toggle_unread()


def str_to_date(string):
    datetime_object = datetime.strptime(string, '%Y-%m-%d %X')
    return datetime_object


def download_item(url, feed_name):
    print(url)
    # grabs the last element of an url and replaces chars
    local_filename = feed_name.replace(' ', '_')+url.split('/')[-1]
    local_filename = local_filename.split('?')[0] # grabs the last element of an url and replaces chars

    # will not overwrite files, even if they are zero btyes...
    if os.path.isfile(local_filename):
        return local_filename
    # grabs item to be downloaded as a stream
    with requests.get(url, stream=True, allow_redirects=True, headers=headers) as response:

        with open(local_filename, "wb") as handle:
            # download the item and write to a file
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:  # filter out keep-alive new chunks
                    handle.write(chunk)
    return local_filename


def get_feed(client, feed_name):
    for cat in client.get_categories(unread_only=True):
        for feed in cat.feeds():
            if feed.title == feed_name:
                return feed


def get_headlines(client, feed_name):
    feeds = get_feed(client, feed_name)
    if(type(feeds) is None):
        return None
    else:
        headlines = feeds.headlines()
        return headlines


def get_unread_articles(client, feed_name):
    headlines = get_headlines(client, feed_name)

    if headlines is None:
        return None
    else:
        l = []
        for headline in headlines:
            art = headline.full_article()
            if art.unread == True:
                l.append(art)
        return l


def article_trim(client, articles, release_type, count):
    if count == 0:
        return articles
    elif release_type == 'rolling':
        articles = sorted(articles, key=lambda x: x.updated, reverse=True)
        mark_article_read(client, articles[count:])
        return articles[:count]
    elif release_type == 'completion':
        articles = sorted(articles, key=lambda x: x.updated)
        return articles[:count]


def filtered_download(article, get_filter, feed_name):
    main_page = requests.get(article.link, headers=headers)
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
                return download_item(path, feed_name)
            else:
                return None

        if item == 'attachment':
            return download_item(article.attachments[0]['1'], feed_name)


def sync_items(client, db):
    listdir = os.listdir()                                  # grabs local items
    db_items = db.getItems()                                # grabs database items
    for item in db_items:
        # if the name of the database item is not local
        if item[1] not in listdir:
            # remove it from the database
            db.removeItem(item[0])
            # mark it as read on ttrss (if the item was deleted)
            mark_article_read(client, item[0])
    db_locs = [name[1] for name in db_items]
    for item in listdir:
        if item not in db_locs:
            # if the item is not in the database remove it
            os.remove(item)


def trim_db(feed, db, count, release_type):
    if release_type == 'rolling' and count != 0:
        items = db.getItemByFeed(feed)[::-1]
        for item in items[count:]:
            db.removeItem(item[0])


def download_articles(db, art, article_dict):
    if not db.checkItemExists(art.id):
        article_content = filtered_download(
            art, article_dict['filter'], article_dict['feed_name'])
        if article_content == None:
            pass
            # mark_article_read(client, art.id)
        else:
            db.insertItem(art.id, article_content,
                          article_dict['feed_name'], art.updated)
    trim_db(article_dict['feed_name'], db, int(
        article_dict['count']), article_dict['release_type'])

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('rss.conf')
    db = rss_db(config)
    url = config['Main']['Url']
    username = config['Main']['Username']
    password = config['Main']['Password']
    headers = {'User-Agent': config['Headers']['headers']}
    client = TTRClient(url, username, password)
    client.login()


    feeds = get_feeds_from_config(config)
    os.chdir(config['Main']['Data'])
    for article_dict in feeds:
        print(article_dict)
        articles = get_unread_articles(client, article_dict['feed_name'])
        if articles is None:
            articles = []
        article_ids = [article.id for article in articles]
        for db_article in db.getItemByFeed(article_dict['feed_name']):
            if db_article[0] not in article_ids:
                db.removeItem(db_article[0])
        articles = article_trim(
            client, articles, article_dict['release_type'], int(article_dict['count']))

        # has to create  new database object because of threads
        input_articles = [(rss_db(config), art, article_dict) for art in articles]
        p = ThreadPool(4)
        p.starmap(download_articles, input_articles)
    sync_items(client, db)

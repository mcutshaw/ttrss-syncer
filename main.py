import configparser
from syncer import syncer
import time

if __name__ == "__main__":
    delay = 20
    config = configparser.ConfigParser()
    config.read('rss.conf')
    while(True):
        try:
            s = syncer(config)
            s.run()
        except:
            print('timeout/error')
        time.sleep(120)






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

from webdav3.client import Client

class connector:
   def __init__(self, config):
       self.config = config
       options = {
         'webdav_hostname': config['Connector']['Host'],
         'webdav_login':    config['Connector']['Username'],
         'webdav_password': config['Connector']['Password']
        }
       self.client = Client(options)
       self.client.verfiy = False

       self.base=config['Connector']['Base']

   def listdir(self):
       l = self.client.list(self.base)
       l.pop(l.index(self.base+'/'))
       print(l)
       return l
   def remove(self, name):
       self.client.clean(self.base + '/' + name)
   def check(self, name):
       return self.client.check(self.base+'/'+name)
   def get(self, name):
       return self.client.resource(self.base+'/'+name)
   def create(self, name):
       self.client.upload_to(None, self.base+'/'+name)
   def upload(self, name):
       self.client.upload_file(self.base+'/'+name, name)

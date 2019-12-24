import multiprocessing
import os
import requests
from time import sleep

class downloader:
   def __init__(self, headers, numProcs=8, dataDir="."):
      self.headers = headers
      self.dataDir=dataDir
      self.numProcs = numProcs
      self.queue = multiprocessing.Queue()
      self.createProcs()

   def createProcs(self):
      for _ in range(self.numProcs):
         p = multiprocessing.Process(target=self._work)
         p.start()

   def _work(self):
      os.chdir(self.dataDir)
      while(True):
         task = self.queue.get()
         if task is None:
               print("Dying gracefully")
               break
         else:
            url = task[0]
            local_filename = task[1]
            self.download_item(url,local_filename)

   def download_item(self, url, local_filename):
      print(url)
      # will not overwrite files, even if they are zero btyes...
      if os.path.isfile(local_filename):
         return local_filename
      # grabs item to be downloaded as a stream
      with requests.get(url, stream=True, allow_redirects=True, headers=self.headers) as response:

         with open(local_filename, "wb") as handle:
            # download the item and write to a file
            for chunk in response.iter_content(chunk_size=1024*1024):
               if chunk:  # filter out keep-alive new chunks
                  handle.write(chunk)

   def addToDownloadQueue(self, url, feed_name):
      local_filename = feed_name.replace(' ', '_')+url.split('/')[-1]
      local_filename = local_filename.split('?')[0] # grabs the last element of an url and replaces chars
      self.queue.put((url, local_filename))
      return local_filename

   def stop(self):
      for _ in range(self.numProcs):
         self.queue.put(None)
      while(not self.queue.empty()):
         sleep(2)
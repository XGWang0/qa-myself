'''Process Management
'''

from multiprocessing import Process
from multiprocessing import Queue
import os  
import time  
import datetime

class ProcessMan(object):
    
    def __init__(self, name="sub_proce_1"):
        self.son_name = name
        self.par_pid = os.getpid()
        self.son = None
        self.pro_q = Queue()


    def createSubproc(self, func, param):
        self.son = Process(name=self.son_name,target=func, args=param)
    
    def recycleProc(self):
        if self.son.is_alive():
            self.son.join()

    def isalive(self):
        return self.son.is_alive()
    
    def getSonpid(self):
        return self.son.pid

    def terminalProc(self):
        self.son.terminate()
    
    def startProc(self):
        self.son.start()
    
    def catchProc(self, timeout=None):
        self.son.join(timeout)
    
    def getQueue(self):
        return self.pro_q
    
    def addCaseInfo2Q(self, msg):
        self.pro_q.put(msg)

def sleeper(name, seconds, q):
    
    print "Process ID# %s" % (os.getpid())  
    print "Parent Process ID# %s" % (os.getppid())  
    print "%s will sleep for %s seconds" % (name, seconds)
    q.put(os.getpid())
    time.sleep(seconds)
    print "subbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  
if __name__ == "__main__":

    print datetime.datetime.now()
    now = time.time()
    son_p = ProcessMan()
    son_p.createSubproc(sleeper, ('bob', 5, son_p.getQueue()))
    print "in parent process after child process start"  
    print "parent process abount to join child process"
    son_p.startProc()
    print son_p.getSonpid(),"child id "
    
    while True:
        if son_p.isalive():
            if time.time() - now > 15:
                son_p.terminalProc()
                break
            else:
                time.sleep(2)
        else:
            print '------------------------'
            
            print son_p.getQueue().get()
            print '------------------------'
            break

    print datetime.datetime.now()
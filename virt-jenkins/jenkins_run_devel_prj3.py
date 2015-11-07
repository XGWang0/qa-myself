import multiprocessing
import threading
import Queue
import os
import sys
import logging

from jenkins_run_devel_prj1 import *

class AllStaticFuncs(AllStaticFuncs):

    @staticmethod
    def pushList2Queue(obj_list, obj_task):
        for i in obj_list:
            obj_task.put(i)

class MultiThreadHostInstallation(GuestInstalling, object):
    '''Install host in parallel
    '''
    def __init__(self, task_q, build_v, test_mod, host_q):

        self.task_q = task_q
        self.host_q = host_q
        self.prd = self.getPrd(self.task_q)
        LOGGER.debug("prd is %s" %self.prd)
        super(MultiThreadHostInstallation, self).__init__(self.prd, build_v, test_mod, self.host_q)

        self.process_name = ''

        self.cmd11 = (self.feed_hamsta + " -x \"ls \" "
                    "-h %(host)s 127.0.0.1 -w")

    def getPrd(self, q):
        if q.qsize() > 0:
            return q.get(block=True, timeout=2)
        else:
            return None

    def storeTaskInstace(self, dict, key, value):
        dict[key] = value


    def installHost(self, addon_repo= "", phase="Phase0", timeout=4800):
        """Reinstall host by hamsta cmd:
        feed_hamsta.pl -t 5 --re_url  repo -re_sdk sdk --pattern kvm/xen_server
        -rpms qa_test_virtualization -h host 127.0.0.1 -w

        if xen type, execute extra switching xen kerenl
        """
        #Prepare all needed repos
        source_name = "source.%s.%s"%(self.repo_type, self.prd_ver.lower())
        host_img_repo = self.prepareRepos(source_name)

        if self.status:
            
            cmd_install_host = (self.cmd_installhost %dict(img_repo=host_img_repo,
                                                          host=self.host,
                                                          virttype=self.virt_type.lower()))
            cmd_install_host = self.cmd11 %dict(host=self.host)
            if DEBUG:
                # runCMDBlocked("scp /root/xgwang/prj3/* root@%s.bej.suse.com:/tmp/" %self.host)
                cmd_install_host = self.cmd11 %dict(host=self.host)

            LOGGER.info(("Start to install host with cmd[%s] on machine %s in parallel"
                         %(cmd_install_host, self.host)))
            #Install host
            self.execHamstaJob(cmd=cmd_install_host,
                               timeout=timeout,
                               job_sketch="Install host %s" %self.host,
                               phase=phase)

            #Switch xen kernel
            if self.virt_type == "XEN":
                self.switchXenKernel()
        else:
            LOGGER.warn("Failed to reserver host, skip host reinstallation")

    def run(self, status_q, lock):
        
        self.rebootHost(phase="Phase0",job_sketch="Reboot Machine %s To Initialize Status" %(self.host))
        self.installHost(phase="Phase1")
        #self.updateRPM(phase="Phase2")
        #self.makeEffect2RPM(phase="Phase2.1", job_sketch="Reboot Machine %s For Upgrade of RPM" %(self.host))

        lock.acquire()
        if status_q['org_host_task'] is None:
            self.process_name = 'org_host_task'
            self.storeTaskInstace(status_q, key='org_host_task', value=self)
            LOGGER.info("Org host %s" %self.host)
        else:
            self.process_name = 'dest_host_task'
            self.storeTaskInstace(status_q, key='dest_host_task', value=self)
            LOGGER.info("Dest host %s" %self.host)
        lock.release()

class GuestMigration(object):

    def __init__(self, prd_list, build_v, test_mod, host_queue):
        self.prd_list = prd_list
        self.host_list = []
        self.build_v = build_v
        self.test_mod = test_mod
        self.queue = host_queue
        self.host_q = Queue.Queue()
        #self.host_q = Queue.Queue()
        self.task_q = Queue.Queue()
        self.task_status = {'org_host_task':None, 'dest_host_task':None}

        self.feed_hamsta = "/usr/share/hamsta/feed_hamsta.pl"
        #bash guest_migrate.sh -d 147.2.207.36 -v xen -u root -p novell -i "sles-11-sp3 sles-11-sp4"
        self.cmd_guest_migration = ('guest_migrate.sh -d %(dest-host)s -v %(virt_type)s'
                                    ' -u root -p susetesting -i "%(guest_prd)s"')

        self.status = True
        self.result = []

        self.reserveHost()

    def reserveHost(self, timeout=7200):
        '''Resrve available and free host
        '''
        #TODO, There are some issue
        LOGGER.info("Start to reserve host")
        start_time = datetime.datetime.now()
        now = time.time()
        while time.time() - now < timeout:
            if self.queue.qsize() == 0:
                LOGGER.warn("There is no available host in queue")
                time.sleep(20)
            else:
                self.host_list = self.queue.get(block=True, timeout=2)
                for host in self.host_list:
                    if AllStaticFuncs().checkIPAddress(host) is False:
                        self.status = False
                        LOGGER.info("Machine [%s] is down, no enough machine to do test!!")
                        return False
                    else:
                        self.host_q.put(host)

                LOGGER.info("Reserve host ip [%s]" %str(self.host_list))
                return 

        LOGGER.error("There is no available host, exit!!")

        self.status = False
        self.no_host_flag = True
        result_map = {"scenario_status":20,
                      "step_info":[],
                      "scenario_alloutput":"No Availbale host",
                      "doc_str_flag":True,
                      "scenario_qadb_url":'',
                      "scenario_name":"Reserve host",
                      "hamsta_output":"No Availbale host",
                      "hamsta_status":0,
                      "start_time":start_time,
                      "end_time":datetime.datetime.now()}
        self.result.append(result_map)

    def releaseHost(self):
        '''Back host address into queue after finishing test on host
        '''
        self.queue.put(self.host_list)
        LOGGER.debug("Insert host list %s to queue %d" %(str(self.host_list), self.queue.qsize()))
        self.host_list = []

    '''
    def checkHosts(self):

        if  len(AllStaticFuncs().getAvailHost(self.host_list)) >= 2:
            AllStaticFuncs().pushList2Queue(self.host_list, self.host_q)
        else:
            self.status = False
            LOGGER.error("There is no enough available host to run test")
            return False
    '''

    def storePrd2Queue(self):
        LOGGER.debug("store prd : %s" %str(self.prd_list))
        AllStaticFuncs().pushList2Queue(self.prd_list, self.task_q)
 
    def installHostAndVM(self):
    
        task_lock = threading.Lock()
    
        t1 = threading.Thread(name="thread1",
                              target=MultiThreadHostInstallation(self.task_q, self.build_v,
                                                      self.test_mod, self.host_q).run,
                              args=(self.task_status, task_lock))
        t2 = threading.Thread(name="thread2",
                              target=MultiThreadHostInstallation(self.task_q, self.build_v,
                                                      self.test_mod, self.host_q).run,
                              args=(self.task_status, task_lock))
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
    
        for w in self.task_status.values():
            LOGGER.debug(w.status)
            self.status &= w.status
            self.result.append(w.result)

        LOGGER.debug(self.result)
        LOGGER.debug('-'*100)
        LOGGER.debug(self.status)
        LOGGER.debug('-'*100)
        return self.status

    def installPkg(self):
        pass

    def migrateGuest2DestHost(self, timeout=4800):
        """Execute guest migration script via HAMSTA
        """
        org_host_self = self.task_status['org_host_task']
        dest_host_self = self.task_status['dest_host_task']
        if self.status:
            cmd_gm_on_machine = " -x \"cd /usr/share/qa/virtautolib/lib;./guest_migrate.sh -d %(desthost)s -v %(virttype)s -u root -p susetestng -i sles-11-sp3 \""
            
            
            
            
            
            
            
            
            
            
            cmd_gm_on_machine = self.cmd11 %dict(host=self.host)
            
            
            
            
            
            
            
            
            
            
            
            #if DEBUG:
                #runCMDBlocked("scp /root/xgwang/prj3/* root@%s.bej.suse.com:/tmp/" %org_host_self.host)
            #    cmd_gm_on_machine = " -x \" /tmp/guestmigration.sh %(desthost)s %(virttype)s 1\""
            cmd_guest_migration = (self.feed_hamsta + cmd_gm_on_machine + 
                                   " -h %(host)s 127.0.0.1 -w") %dict(host=org_host_self.host,
                                                                     desthost=dest_host_self.host,
                                                                     virttype=org_host_self.virt_type)

            LOGGER.info(("Start to migrate guest with cmd[%s] on machine %s"
                         %(cmd_guest_migration, self.task_status['org_host_task'].host)))
            #Install host
            org_host_self.execHamstaJob(cmd=cmd_guest_migration,
                                        timeout=timeout,
                                        job_sketch="Migrate guest",
                                        phase="Phase3")
        else:
            LOGGER.warn("Last phase failure, skip guest migration operation")

    def collectResult(self, scen_stauts=True):
        '''Generate new data structure.
        '''
        feature_desc = ("Target : The  guest migration test."
                          " (Support xen & kvm type guest migration test)\n"
                          "\tFunctions:\n"
                          "\t\t1.   Install original host server remotely by HAMSTA.\n"
                          "\t\t1-1. Switch xen kernel only for xen test by HAMSTA.\n"
                          "\t\t1-2. Install needed packages on original host server remotely by HAMSTA.\n"
                          "\t\t2.   Install destination host server remotely by HAMSTA.\n"
                          "\t\t1-1. Switch xen kernel only for xen test by HAMSTA.\n"
                          "\t\t2-2. Install needed packages on original host server remotely by HAMSTA.\n"
                          "\t\t3.   Execute guest migration test.\n"
                          "\t\t4.   Verify the installing result."
                          "\n\nRunning Env"
                          "\nVirt Product Version:")
        scen_stauts = self.status
        LOGGER.debug(dir(self.task_status['org_host_task']))
        LOGGER.debug(dir(self.task_status['dest_host_task']))
        tmp_job_map = {}
        tmp_job_map["feature_prefix_name"] = 'Guest-Migration '
        tmp_job_map["feature_host"] = 'org_host:%s dest_host:%s'%(self.task_status['org_host_task'].host,
                                                                  self.task_status['dest_host_task'].host)
        tmp_job_map["feature_prj_name"] = "%s -> %s" %(self.prd_list[0],
                                                       self.prd_list[1])
        tmp_job_map["scenario_info"] = self.task_status['dest_host_task'].result + self.task_status['org_host_task'].result
        tmp_job_map["feature_desc"] = feature_desc  + "\n\n" + "Running Env, Host :\n%s" %(tmp_job_map["feature_host"])
        tmp_job_map["feature_status"] =  scen_stauts
        
        LOGGER.debug(tmp_job_map)
        
        return tmp_job_map


class MultipleProcessRun(MultipleProcessRun, object):
    """Class which supports multiple process running for virtualization
    """

    def __init__(self, options):
        """Initial process pool, valiables and constant values 
        """
        super(MultipleProcessRun, self).__init__(options)

    def combineProductV(self, list_a, list_b):
        '''Combine orginal product with updated product
        Sample : a = ['SLES-11-SP3-64.XEN','SLES-11-SP3-64.KVM', 'SLES-12-SP0-64.XEN','SLES-12-SP0-64.KVM','SLES-11-SP4-64.XEN','SLES-11-SP4-64.KVM']
                 b = ['SLES-12-SP0-64','SLES-11-SP4-64']
                 combineProductV(a,b)
        Return : [('SLES-11-SP3-64.XEN', 'SLES-11-SP4-64'), ('SLES-11-SP3-64.KVM', 'SLES-11-SP4-64'), ('SLES-11-SP4-64.XEN', 'SLES-12-SP0-64'), ('SLES-11-SP4-64.KVM', 'SLES-12-SP0-64')]
        '''
        ALL_SENARIOS = [('SLES-11-SP3-64', 'SLES-11-SP3-64'),
                        ('SLES-11-SP3-64', 'SLES-11-SP4-64'),
                        ('SLES-11-SP3-64', 'SLES-12-SP1-64'),
                        ('SLES-11-SP3-64', 'SLES-12-SP0-64'),
                        ('SLES-11-SP4-64', 'SLES-12-SP4-64'),
                        ('SLES-11-SP4-64', 'SLES-12-SP0-64'),
                        ('SLES-11-SP4-64', 'SLES-12-SP1-64'),
                        ('SLES-12-SP0-64', 'SLES-12-SP1-64'),
                        ('SLES-12-SP0-64', 'SLES-12-SP0-64'),
                        ('SLES-12-SP1-64', 'SLES-12-SP1-64'),
                        ]

        tmp = []
        for a_i in list_a:
            for b_i in list_b:
                a_v = a_i.split('.')[0]
                b_v = b_i.split('.')[0]
                
                if (a_v, b_v) in  ALL_SENARIOS:
                    tmp.append((a_i,b_i))

        not tmp and LOGGER.warn(("No valid senarios. Please check jenkins parameters "
                             "ORG_PRODUCT and UPG_PRODUCT, make sure at least one of combinations is valid."))
        LOGGER.debug("All task are %s" %(str(tmp)))
        return tmp


    def _divideHost2Q(self, step=2):
        avail_host_group = []
        tmplist = []
        all_host_list = AllStaticFuncs.getAvailHost(self.options.gm_host_list.split(","))
        for h in all_host_list:
            tmplist.append(h)
            if len(tmplist) == 2:
                self.queue.put(tmplist)
                avail_host_group.append(tmplist)
                tmplist = []
                continue
        LOGGER.debug("All avaliable host group are %s" %(str(avail_host_group)))

    def startRun(self):
        self._divideHost2Q()
        self.org_prd_list = self.options.gm_org_prd.strip().split(",")
        self.dest_prd_list = self.options.gm_dest_prd.strip().split(",")
        self.param = (self.build_version, self.test_mode)

        #Pool size is defined through host number.
        q_size = self.queue.qsize()
        if q_size != 0:
            self.pool = multiprocessing.Pool(processes=q_size)
            LOGGER.debug("Create process pool[%d]" %q_size)
            #self.initialQueue()
            self._gmMultipleTask()
            self.closeAndJoinPool()
        else:
            self.prj_status["status"]= False
            self.createFileFlag()
            self.prj_status["info"] = "There is no available host"

    def _gmMultipleTask(self):
        for prd_list in self.combineProductV(self.org_prd_list, self.dest_prd_list):
            LOGGER.debug("prd_list is %s" %str(prd_list))
            migrateGuest(prd_list, self.build_version, self.test_mode, self.queue)
            '''
            self.result.append([prd_list,
                self.pool.apply_async(migrateGuest,
                                      (prd_list, self.build_version, self.test_mode, self.queue))])
            '''

def migrateGuest(prd_list, prd_ver, test_mode, host_queue):

    gm = GuestMigration(prd_list, prd_ver, test_mode, host_queue)
    #gm.checkHosts()
    gm.storePrd2Queue()
    gm.installHostAndVM()
    gm.migrateGuest2DestHost()
    #result.append(gm.collectResult(rel))
    LOGGER.debug('-'*15 + 'separator line' + '-'*15)
    #gm.writeLog2File()
    LOGGER.info("Product version [%s] --> [%s] finished" %(prd_list[0], prd_list[1]))
    
    gm.releaseHost()
    return gm.collectResult()
'''
def main():
    param_opt = ParseCMDParam()
    options, _args = param_opt.parse_args()

    rel = True
    result = []

    for dest_prd in options.gm_dest_prd.split(','):
        LOGGER.info("%s --> %s" %(options.gm_org_prd, dest_prd))
        gm = GuestMigration([options.gm_org_prd, dest_prd], options.product_ver,
                             options.test_mode, options.gm_host_list.split(','))
        gm.checkHosts()
        gm.storePrd()
        rel &= gm.installHostAndVM()
        gm.migrateGuest()
        result.append(gm.collectResult(rel))
        LOGGER.info('-'*15 + 'separator line' + '-'*15)
    
    ConvertJson(result).genJsonFile()
    
    rel is False and sys.exit(1) or sys.exit(0)
'''
'''
def main():
    """Main function
    """
    
    #Initial environment
    AllStaticFuncs.cleanJosnFIle()
    #Parse commandline parameters
    start_time = datetime.datetime.now()
    param_opt = ParseCMDParam()
    options, _args = param_opt.parse_args()
    #Instance for multiple process
    mpr = MultipleProcessRun(options)
    #Collect all result and generate json file
    tcmap=mpr.getResultMap()
    #Compress result of project
    AllStaticFuncs.compressFile(AllStaticFuncs.getBuildPath())
    
    #Verify project result and mark status
    if mpr.getMulPoolStatus()["status"] is True:
        exit_code = 0
    else:
        LOGGER.warn(mpr.getMulPoolStatus()["info"])
        exit_code = 5
    sys.exit(exit_code)
'''
DEBUG = False

#LOGGER = LoggerHandling(os.path.join(AllStaticFuncs.getBuildPath(), "sys.log"), logging.DEBUG)
'''
if __name__ == "__main__":
    main()
'''


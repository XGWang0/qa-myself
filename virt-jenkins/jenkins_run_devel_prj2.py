#!/usr/bin/python
"""
****************************************************************************
Copyright (c) 2013 Unpublished Work of SUSE. All Rights Reserved.

THIS IS AN UNPUBLISHED WORK OF SUSE.  IT CONTAINS SUSE'S
CONFIDENTIAL, PROPRIETARY, AND TRADE SECRET INFORMATION.  SUSE
RESTRICTS THIS WORK TO SUSE EMPLOYEES WHO NEED THE WORK TO PERFORM
THEIR ASSIGNMENTS AND TO THIRD PARTIES AUTHORIZED BY SUSE IN WRITING.
THIS WORK IS SUBJECT TO U.S. AND INTERNATIONAL COPYRIGHT LAWS AND
TREATIES. IT MAY NOT BE USED, COPIED, DISTRIBUTED, DISCLOSED, ADAPTED,
PERFORMED, DISPLAYED, COLLECTED, COMPILED, OR LINKED WITHOUT SUSE'S
PRIOR WRITTEN CONSENT. USE OR EXPLOITATION OF THIS WORK WITHOUT
AUTHORIZATION COULD SUBJECT THE PERPETRATOR TO CRIMINAL AND  CIVIL
LIABILITY.

SUSE PROVIDES THE WORK 'AS IS,' WITHOUT ANY EXPRESS OR IMPLIED
WARRANTY, INCLUDING WITHOUT THE IMPLIED WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. SUSE, THE
AUTHORS OF THE WORK, AND THE OWNERS OF COPYRIGHT IN THE WORK ARE NOT
LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION
WITH THE WORK OR THE USE OR OTHER DEALINGS IN THE WORK.
****************************************************************************

Tool Brief:
  Description: Automatically distribute tasks into available host 
               and run virtualization relevant test.
  Function & Scope:
               Tool supports below projects:
                 1. Guest installation test
                 2. Host migration test
                 3. Guest migration test (in processing)
                 Note: Script combines with jenkins
"""

import datetime
import json
import logging
import multiprocessing
import os
import optparse
import re
import select
import signal
import subprocess
import sys
import time

from jenkins_run_devel_prj1 import * 

class HostMigration(GuestInstalling, object):
    '''The class is only for host migration test
    '''
    def __init__(self, org_prd, dest_prd, param, queue):
        '''Initial function and variables, inherit GuestInstalling class
        '''
        self.build_ver = param[0]
        super(HostMigration, self).__init__(org_prd, param[0], param[1], queue)
        self.dest_prd = dest_prd

        self.cmd_test_run =  ""
        
        #self.upd_desthost_repo = self._getUpdRepo(self.dest_prd)

    def generateTestRun(self, timeout=300):
        """Function which update host by hamsta API
        """
        def _get_test_run(result, keyword="Generated test run file:"):
                se_ins = re.search("%s\s*(\S+)" %(keyword), result, re.I)
                if se_ins:
                    return se_ins.groups()[0].strip()
                else:
                    return ""

        if self.status:
            cmd_generate_tr = (self.feed_hamsta +  " -x "
                   "\"/usr/share/qa/tools/_generate_vh-update_tests.sh "
                   "-m %(virt_std)s -v %(virt_type)s -b %(org_prd)s -u %(dest_prd)s \" "
                   "-h %(host)s 127.0.0.1 -w" %dict(host=self.host,
                                                    virt_std=self.test_mode,
                                                    virt_type=self.virt_type.lower(),
                                                    org_prd=self.prd_ver.lower().replace("-64",""),
                                                    dest_prd=self.dest_prd.lower().replace("-64","")))

            '''
            cmd11 = (self.feed_hamsta + " -x \"ls \" "
                          "-h %(host)s 127.0.0.1 -w")
            cmd_generate_tr = cmd11 %dict(host=self.host)
            '''
            
            
            
            if DEBUG:
                cmd_update_rpm = "/tmp/test.sh rpm"
            LOGGER.info(("Start to generate test run script with cmd [%s] on %s"
                         %(cmd_generate_tr, self.host)))
            self.execHamstaJob(cmd=cmd_generate_tr,
                               timeout=timeout,
                               job_sketch="Generate Test Run Script",
                               phase="Phase2")

            if self.status:
                job_result = self.result[-1]["scenario_alloutput"]
                cmd_test_run = _get_test_run(job_result)
                if cmd_test_run:
                    self.cmd_test_run = (self.feed_hamsta +
                                         " -x \"" + cmd_test_run + " %(step)s\"" 
                                         " -h %(host)s 127.0.0.1 -w ")
                else:
                    self.status = False
            else:
                pass
        else:
            LOGGER.warn("Last phase failure, skip generation test run script.")


    def updateRPM(self, phase="Phase0", timeout=3600):
        """Function which update host by hamsta API
        """
        if self.status:

            cmd_update_rpm = self.cmd_test_run  %dict(step="01",
                                                      host=self.host)

            '''
            cmd11 = (self.feed_hamsta + " -x \"ls \" "
                          "-h %(host)s 127.0.0.1 -w")
            cmd_update_rpm = cmd11 %dict(host=self.host)
            '''


            if DEBUG:
                cmd_update_rpm = "/tmp/test.sh rpm"
            LOGGER.info("Start to upgrade RPM with cmd [%s] %s" %(cmd_update_rpm, self.host))
            self.execHamstaJob(cmd=cmd_update_rpm,
                               timeout=timeout,
                               job_sketch="Upgrade RPM",
                               phase=phase)
            
            #self.rebootHost(phase=phase, job_sketch="Recover Machine Status", chk_postive_status=False)
        else:
            LOGGER.warn("Last phase failure, skip rpm updating.")

    def updateHost(self, phase="Phase0", timeout=172800):
        """Function which update host by hamsta API
        """
        if self.status:

            cmd_update_host = self.cmd_test_run %dict(step="02",
                                                      host=self.host)

            '''
            cmd11 = (self.feed_hamsta + " -x \"ls \" "
                          "-h %(host)s 127.0.0.1 -w")
            cmd_update_host = cmd11 %dict(host=self.host)
            '''

            if DEBUG:
                cmd_update_host = "/tmp/test.sh up"
            LOGGER.info("Start to upgrade host with cmd [%s] %s" %(cmd_update_host, self.host))
            self.execHamstaJob(cmd=cmd_update_host,
                               timeout=timeout,
                               job_sketch="Upgrade Host",
                               phase=phase)
        else:
            LOGGER.warn("Last phase failure, skip host updating.")

    def verifyGuest(self, timeout=10000):
        """Function which verifys result of host migration.
        Thru invoking hamsta cmd to do this operation.
        """
        if self.status:

            cmd_verify_guest = self.cmd_test_run %dict(step="03",
                                                       host=self.host)

            LOGGER.info("Start to verify host with cmd [%s] %s" %(cmd_verify_guest, self.host))

            if DEBUG:
                cmd_verify_guest = "/tmp/test.sh ver"
            self.execHamstaJob(cmd=cmd_verify_guest,
                                timeout=timeout,
                                job_sketch="Verify Guest",
                                phase="Phase7",
                                doc_str_flag=True)
        else:
            LOGGER.warn("Last phase failure, skip guest verfication.")

    def getDateTimeDelta(self, beg_time, end_time):
        '''Calculate difftime.
        '''
        beg_date_time_tuple = time.mktime(datetime.datetime.timetuple(beg_time))
        end_date_time_tuple = time.mktime(datetime.datetime.timetuple(end_time))
        
        return abs(int(end_date_time_tuple - beg_date_time_tuple))

    def assembleResult(self):
        '''Generate new data structure.
        
        Format Sample:
            {'feature_desc': 'desc',
              'feature_host': '147.2.207.27',
              'feature_prj_name': 'SLES-11-SP4-64.KVM',
              'feature_prefix_name': 'Virt Install - host '
              'scenario_info': [                
                                    {'doc_str_flag': False,
                                      'end_time': datetime.datetime(2015, 5, 6, 7, 55, 11, 871674),
                                      'hamsta_output': 'hamsta_out',
                                      'hamsta_status': 0,
                                      'scenario_alloutput': 'scenario_output',
                                      'scenario_name': 'Install host',
                                      'scenario_qadb_url': '',
                                      'scenario_status': 0,
                                      'start_time': datetime.datetime(2015, 5, 6, 7, 55, 11, 863720),
                                      'step_info': [{'step_name':'sles-11-sp2-64-fv-def-net',
                                                     'step_status':'PASSED',
                                                     'step_duration':100,
                                                     'step_stdout':"",
                                                     'step_errout':""}
                                                    ],
                                    }
                                ]
            }
        '''

        prefix_name="Host-Migration "

        if self.test_mode == "std":
            repo_chg_ver = self.build_ver
        else:
            repo_chg_ver = (self.getRepoChgVer(self.prd) + '\n' +
                            self.getRepoChgVer(self.dest_prd))

        feature_desc=("Target : The host migration test for virtualization."
                      " (Support xen & kvm type virtualization)\n"
                      "\tFunctions:\n"
                      "\t\t1.   Install host server remotely by HAMSTA.\n"
                      "\t\t2.   Install needed packages of virtualizaiton test.\n"
                      "\t\t2-1. Switch xen/kvm kernel\n"
                      "\t\t3.   Install guests in parallel on host server.\n"
                      "\t\t4.   Update host server.\n"
                      "\t\t5.   Verify the availability of guest.\n"
                      "\nRunning Env"
                      "\nVirt Product Version:\n%s" %repo_chg_ver)

        tmp_job_map = {}
        tmp_job_map["feature_prefix_name"] = prefix_name
        tmp_job_map["feature_host"] = self.host
        tmp_job_map["feature_prj_name"] = "%s -> %s.%s" %(self.prd, self.dest_prd, self.virt_type)
        tmp_job_map["scenario_info"] = self.result
        tmp_job_map["feature_desc"] = feature_desc  + "\n\n" + "Running Env, Host :%s" %self.host
        tmp_job_map["feature_status"] =  self.status

        return tmp_job_map

    def updateRPMFromMilestone(self, phase="Phase0", timeout=36000):
        """Function which update host from milestone repo
        """
        if self.test_mode == "std":
            if self.status:
                if self.upd_desthost_repo:
                    cmd_update_rpm = self.cmd_test_run  %dict(step="03",
                                                              host=self.host)
                    if DEBUG:
                        cmd_update_rpm = "/tmp/test.sh rpm"
                    LOGGER.info("Start to upgrade RPM from Milesteon Build with cmd [%s] %s" %(cmd_update_rpm, self.host))
                    self.execHamstaJob(cmd=cmd_update_rpm,
                                       timeout=timeout,
                                       job_sketch="Upgrade RPM From Milestone build",
                                       phase=phase)
                    
                    #self.rebootHost(phase=phase, job_sketch="Recover Machine Status", chk_postive_status=False)
                    self.makeEffect2HostUpgrade(phase="Phase9")
                else:
                    LOGGER.info("Update RPM from default source.")
            else:
                LOGGER.warn("Last phase failure, skip milestone rpm updating.")
        else:
            LOGGER.info("Test mode is dev, skip milestone rpm upgrade")
            pass

    def makeEffect2HostUpgrade(self, phase="Phase0", flag=True):
        if self.status:
            # Only upgraded product is sle-12 or up version needs to be switched kernel
            if 'SLES-12' in self.dest_prd and self.virt_type == "XEN":
                self.switchXenKernel()
            else:
                pass
        else:
            pass

#def migrateHost(org_prd, dest_prd, build_ver, test_mode='dev', queue=None,):
def migrateHost(org_prd, dest_prd, param, queue=None,):
    """Externel function, only for warp migration host function
    """
    def _migrateHostDevel(hm_inst):
        if hm_inst.status:
            hm_inst.setDefaultGrub(phase="Phase0")
            hm_inst.rebootHost(phase="Phase1",job_sketch="Recover Machine Status")
            hm_inst.installHost(phase="Phase2")
            hm_inst.generateTestRun(timeout=1800)
            hm_inst.updateRPM(phase="Phase3")
            hm_inst.makeEffect2RPM(phase="Phase4")
            hm_inst.updateHost(phase="Phase5")
            hm_inst.rebootHost(phase="Phase6", timeout=5400,
                               job_sketch="Reboot Machine For Host Update")
            hm_inst.makeEffect2HostUpgrade(phase="Phase7", flag=False)
            hm_inst.verifyGuest()
            hm_inst.releaseHost()

    vir_opt = HostMigration(org_prd, dest_prd, param, queue)
    LOGGER.info("Product version [%s] starts to run on host [%s] now" %(org_prd, vir_opt.host))

    _migrateHostDevel(vir_opt)

    vir_opt.writeLog2File()
    LOGGER.info("Product version [%s] finished" %org_prd)
    
    return vir_opt.assembleResult()

class MultipleProcessRun(MultipleProcessRun, object):
    """Class which supports multiple process running for virtualization
    """

    def __init__(self, options):
        """Initial process pool, valiables and constant values 
        """
        super(MultipleProcessRun, self).__init__(options)

    def startRun(self):
        self.host_list = AllStaticFuncs.getAvailHost(self.options.hu_host_list.split(","))
        self.org_prd_list = self.options.org_product_list.strip().split(",")
        self.upg_prd_list = self.options.upg_product_list.strip().split(",")
        self.param = (self.build_version, self.test_mode)

        #Pool size is defined through host number.
        if self.host_list:
            self.pool = multiprocessing.Pool(processes=len(self.host_list))
            LOGGER.debug("Create process pool[%d]" %len(self.host_list))
            self.initialQueue()
            self._huMultipleTask()
            self.closeAndJoinPool()
        else:
            self.prj_status["status"]= False
            self.createFileFlag()
            self.prj_status["info"] = "There is no available host"

    def _huMultipleTask(self):
        """Execute multiple taskes in processes pool only for guest installing
        """
        for (ord_prd,upg_prd) in self.combineProductV(self.org_prd_list, self.upg_prd_list):
            #migrateHost(ord_prd, upg_prd, self.param, self.queue)

            self.result.append([ord_prd+upg_prd,
                self.pool.apply_async(migrateHost,
                                      (ord_prd, upg_prd, self.param, self.queue))])
        
    def combineProductV(self, list_a, list_b):
        '''Combine orginal product with updated product
        Sample : a = ['SLES-11-SP3-64.XEN','SLES-11-SP3-64.KVM', 'SLES-12-SP0-64.XEN','SLES-12-SP0-64.KVM','SLES-11-SP4-64.XEN','SLES-11-SP4-64.KVM']
                 b = ['SLES-12-SP0-64','SLES-11-SP4-64']
                 combineProductV(a,b)
        Return : [('SLES-11-SP3-64.XEN', 'SLES-11-SP4-64'), ('SLES-11-SP3-64.KVM', 'SLES-11-SP4-64'), ('SLES-11-SP4-64.XEN', 'SLES-12-SP0-64'), ('SLES-11-SP4-64.KVM', 'SLES-12-SP0-64')]
        '''
        ALL_SENARIOS = [('SLES-11-SP3-64', 'SLES-11-SP4-64'),
                        ('SLES-11-SP3-64', 'SLES-12-SP0-64'),
                        ('SLES-11-SP3-64', 'SLES-12-SP1-64'),
                        ('SLES-11-SP4-64', 'SLES-12-SP0-64'),
                        ('SLES-11-SP4-64', 'SLES-12-SP1-64'),
                        ('SLES-12-SP0-64', 'SLES-12-SP1-64'),
                        ]

        tmp = []
        for a_i in list_a:
            for b_i in list_b:
                a_v = a_i.split('.')[0]
                b_v = b_i.split('.')[0]
                
                if (a_v, b_v) in  ALL_SENARIOS:
                    tmp.append((a_i,b_v))

        not tmp and LOGGER.warn(("No valid senarios. Please check jenkins parameters "
                             "ORG_PRODUCT and UPG_PRODUCT, make sure at least one of combinations is valid."))
        return tmp
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
    mpr.startRun()

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
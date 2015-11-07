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

from jenkins_execute_jobs import *

class GuestInstalling(GuestInstalling, object):
    '''Class representing virt-install test runner
    '''

    def __init__(self, prd, buildver, testmode, queue):
        '''Initial variable and constant value
        '''
        super(GuestInstalling, self).__init__(prd, buildver, testmode, queue)


    def assembleResult(self, prefix_name="Virt Install -  ",
                       feature_desc="Description of Feature"):
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

        repo_chg_ver = self.build_ver

        feature_desc=("Target : The virt-install guest installing test."
                  " (Support xen & kvm type virtualization)\n"
                  "\tFunctions:\n"
                  "\t\t1.   Install host server remotely by HAMSTA.\n"
                  "\t\t2.   Install needed packages of virtualizaiton test.\n"
                  "\t\t2-1. Switch xen/kvm kernel\n"
                  "\t\t3.   Install guests in parallel on host server.\n"
                  "\t\t4.   Verify the installing result."
                  "\n\nRunning Env"
                  "\nVirt Product Version:%s" %repo_chg_ver)

        tmp_job_map = {}
        tmp_job_map["feature_prefix_name"] = prefix_name
        tmp_job_map["feature_host"] = self.host
        tmp_job_map["feature_prj_name"] = self.prd
        tmp_job_map["scenario_info"] = self.result
        tmp_job_map["feature_desc"] = feature_desc  + "\nHost :%s" %self.host
        tmp_job_map["feature_status"] =  self.status

        return tmp_job_map


    def updateRPM(self, phase="Phase0", timeout=3600):
        """Function which update host by hamsta API
        """
        upd_repo = self._getUpdRepo(self.prd_ver)
        if upd_repo:
            cmd_update_rpm = (self.feed_hamsta + 
                              " -x \"source /usr/share/qa/virtautolib/lib/virtlib;"
                              "update_virt_rpms off on off %(upd_repo)s\""
                              " -h %(host)s 127.0.0.1 -w" %dict(upd_repo=upd_repo,
                                                                host=self.host))
        else:
            cmd_update_rpm = (self.feed_hamsta +
                              " -x \"source /usr/share/qa/virtautolib/lib/virtlib;"
                              "update_virt_rpms off on off\""
                              " -h %(host)s 127.0.0.1 -w" %dict(host=self.host))

        if self.status:

            if DEBUG:
                cmd_update_rpm = "/tmp/test.sh rpm"
            LOGGER.info("Start to upgrade RPM with cmd [%s] %s" %(cmd_update_rpm, self.host))
            self.execHamstaJob(cmd=cmd_update_rpm,
                               timeout=timeout,
                               job_sketch="Upgrade RPM",
                               phase=phase)

        else:
            LOGGER.warn("Last phase failure, skip rpm updating.")            


    def _getUpdRepo(self, prd_ver):
        '''Get upgrad repo url for milestone test
        '''
        if not self.build_ver or self.build_ver == "NULL":
            LOGGER.info("There is no build version, default update repo will be used")
            upd_repo = ""
        else:
            source_name = "source.virtupdate.milestone.%s" %(prd_ver.lower())
            milestone_root_repo = self.prepareRepos(source_name)

            upd_repo = os.path.join(milestone_root_repo, self.build_ver)
        
        LOGGER.debug("Update repo : %s" %upd_repo)
        return upd_repo

def installGuest(prd, param, queue=None):
    """External function to warp gest installing functions
    """
    
    def _installGuestMileS(gi_inst):
        if gi_inst.status:
            gi_inst.setDefaultGrub(phase="Phase1")
            gi_inst.rebootHost(phase="Phase2",job_sketch="Reboot Machine To Initialize Status")
            gi_inst.installHost(phase="Phase3")
            gi_inst.updateRPM(phase="Phase4")
            gi_inst.makeEffect2RPM(phase="Phase4.1")
            gi_inst.impExteralScript('Virt_jenkins_cmd_hook')
            gi_inst.installVMGuest(filter=param[0], process_num=param[1])
            gi_inst.releaseHost()

    vir_opt = GuestInstalling(prd, param[2], param[3], queue)
    LOGGER.info("Product version [%s] starts to run on host [%s] now" %(prd, vir_opt.host))

    _installGuestMileS(vir_opt)

    vir_opt.writeLog2File()
    LOGGER.info("Product version [%s] finished" %prd)
    
    
    return vir_opt.assembleResult()


class MultipleProcessRun(MultipleProcessRun, object):
    """Class which supports multiple process running for virtualization
    """

    def __init__(self, options):
        """Initial process pool, valiables and constant values 
        """
        self.options = options
        self.result = []
        self.all_result = []
        self.prj_status = dict(status=True, info="")
        self.queue = multiprocessing.Manager().Queue()
        
        self.cleanFileFlag()
        #self.logpath = AllStaticFuncs.getBuildPath()
        #LOGGER.debug("Get build log path :%s" % self.logpath)
    
        self.test_type = self.options.test_type
        self.build_version = self.options.product_ver.strip()
        self.test_mode = self.options.test_mode.strip()

        #Guest installation test
        self.host_list = AllStaticFuncs.getAvailHost(self.options.gi_host_list.split(","))
        self.task_list = self.options.gi_h_product_list.strip().split(",")
        self.param = (self.options.gi_g_product_list, self.options.gi_g_concurrent_num,
                      self.build_version, self.test_mode)
        self._guestInstall()


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

DEBUG = False

LOGGER = LoggerHandling(os.path.join(AllStaticFuncs.getBuildPath(), "sys.log"), logging.DEBUG)

if __name__ == "__main__":
    main()

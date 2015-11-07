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

def runCMDBlocked(cmd):
    """Run a command line with blocking format
    """
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

    LOGGER.info("Execute cmd :%s" %cmd)
    (r_stdout, r_stderr) = result.communicate()
    return_code = result.returncode
    #LOGGER.info("Returned info :%s" %(r_stdout + r_stderr))
    return (return_code, r_stdout + r_stderr)

def runCMDNonBlocked(cmd, timeout=5):
    """Run command line with non-blocking format
    """
    #print "current param1 :%s \npid is :%s" %(task, os.getpid())

    start_time = datetime.datetime.now()
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, preexec_fn=os.setpgrp)

    readbuf_msg = ""
    select_rfds = [result.stdout]
    result_buf = ""
    timeout_flag = False

    while len(select_rfds) > 0:
        (rfds, _wfds, _efds) = select.select(select_rfds, [], [], timeout)
        if not rfds:
            #print "kill pid = ",result.pid
            os.kill(-result.pid, signal.SIGKILL)
            timeout_flag = True
            result_buf = "--------timeout(%d secs)--------\n" %timeout
            return_code = 10
            break
        for rfd in rfds:
            readbuf_msg = rfd.readline()
            result_buf = result_buf + readbuf_msg
            if len(readbuf_msg) == 0:
                select_rfds.remove(result.stdout)

    result.wait()

    end_time = datetime.datetime.now()
    if timeout_flag is False:
        return_code = result.returncode

    return (return_code, result_buf, start_time, end_time)

class GuestInstalling(object):
    '''Class representing virt-install test runner
    '''

    def __init__(self, prd, buildver, testmode, queue):
        '''Initial variable and constant value
        '''
        self.prd = prd
        self.queue = queue
        self.repo_type = "http"
        self.prd_ver, self.virt_type = prd.split(".")
        self.build_ver = buildver
        self.test_mode = testmode

        self.host = ""
        self.logname = ""
        self.qadb_link = ""

        self.result = []
        self.status = True
        self.timeout_flag = False
        self.no_host_flag = False

        self.feed_hamsta = "/usr/share/hamsta/feed_hamsta.pl"
        self.get_source = "/usr/share/qa/virtautolib/lib/get-source.sh"

        self.cmd_getoutput = self.feed_hamsta + " 127.0.0.1 --query_log %s"
        self.cmd_getstatus = self.feed_hamsta + " 127.0.0.1 --query_job %s"

        self.cmd_installhost = (self.feed_hamsta + " -t 5 --re_url  %(img_repo)s "
                                '--re_opts "console=ttyS0,115200 vnc=1 vncpassword=susetesting" '
                                "--pattern %(virttype)s_server "
                                "--rpms qa_test_virtualization -h %(host)s 127.0.0.1 -w")
        '''
        self.cmd_installhost = (self.feed_hamsta + " -t 5 --re_url  %(img_repo)s "
                                #'-o "console=ttyS0,115200 vnc=1 vncpassword=susetesting" '
                                "--re_sdk %(addon_repo)s --pattern %(virttype)s_server "
                                "--rpms qa_test_virtualization -h %(host)s 127.0.0.1 -w")
        '''
        if 'SLES-11' in self.prd:
            in_guest_run = "/usr/share/qa/tools/test_virtualization-standalone-run"
        else:
            in_guest_run = "/usr/share/qa/tools/test_virtualization-virt_install_withopt-run"

        self.cmd_installguest = (self.feed_hamsta + " -x \"" + in_guest_run + 
                                 " -f \'%(filter)s\' -n %(process_num)s -t %(test_mode)s\" -h %(host)s 127.0.0.1 -w")

        self.cmd_switchxenker = (self.feed_hamsta + " -t 1 -n set_xen_default "
                                 "-h %(host)s 127.0.0.1 -w")
        
        self.cmd_runcmd = (self.feed_hamsta + " -x \"%(runcmd)s\" -h %(host)s 127.0.0.1 -w")
        
        self.cmd_reboot_host = (self.feed_hamsta +  " -t 1 -n reboot -h %(host)s 127.0.0.1 -w")

        self.start_time = datetime.datetime.now()
        
        #Reserve host from queue
        self.reserveHost()
        #Get absolute log path
        self.getLogName()

    def getLogName(self):
        """Get absolute log path for each test case
        """
        logpath = AllStaticFuncs.getBuildPath()
        LOGGER.debug("Get build log path :%s" %logpath)
        self.logname = os.path.join(logpath, self.prd)

    def writeLog2File(self):
        """Redirect result information to file,
        """
        end_time = datetime.datetime.now()
        if os.path.exists(self.logname):
            os.remove(self.logname)
        with open(self.logname, "a+") as f:
            f.write("Task : %s" %(self.prd) + os.linesep)
            f.write("Host : %s" %(self.host) + os.linesep)
            if self.status:
                f.write("Status : Passed" + os.linesep)
            else:
                if self.timeout_flag:
                    f.write("Status : Timeout" + os.linesep)
                elif self.no_host_flag:
                    f.write("Status : No Available Host" + os.linesep)
                else:
                    f.write("Status : Failed" + os.linesep)

            f.write(os.linesep)
            f.write("Running time : %s" %(end_time - self.start_time) + os.linesep)
            f.write("-" * 30 + os.linesep)
            f.write(os.linesep)
            tmp_result = ""
            for rel in self.result:
                if rel["scenario_alloutput"] is not None:
                    tmp_result = tmp_result + rel["scenario_alloutput"]
            f.write("Output : " + os.linesep +
                    ("\t%s" %(tmp_result.replace(os.linesep, os.linesep+"\t"))))
            f.flush()
            f.close()

    def getJobStatus(self, output):
        '''Get job status through hamsta command :
        feed_hamsta.pl --query_log jobid 127.0.0.1
        '''
        job_id = self.getJobID(output)
        if job_id == 0:
            return "Abnormal"
        cmd_get_job_status = self.cmd_getstatus %(job_id)
        status_buf= runCMDNonBlocked(cmd_get_job_status, timeout=10)[1]
        se_job_status = re.search("stauts : (\S+)", status_buf, )
        if se_job_status:
            job_status = se_job_status.groups()[0].strip()
        else:
            LOGGER.warn("Failed to get job status from %s" %output)
            job_status = "failed"
        
        return job_status

    def getJobID(self, output, search_key="internal id:\s*(\d+)"):
        '''Get job id thru hamsta output,
        Search key word "internal id :" and capture the jobid with regular expression
        
        Sample
            output :
            "
            Connecting to master 127.0.0.1 on 18431
            MASTER::FUNCTIONS cmdline Reinstall Job send to scheduler, at 147.2.207.60 internal id: 1317
            "
            return: 1317
        '''
        se_job_id = re.search(search_key, output)
        if se_job_id:
            job_id = se_job_id.groups()[0]
            LOGGER.info("Job ID is %s" %job_id)
            return job_id
        else:
            LOGGER.debug(output)
            LOGGER.error("Failed to get job id from hamsta output")
            return 0

    def getQadbURL(self, output, search_key="http:.*submission_id.*"):
        '''Get job url of QADB from job terminal output,
        1. get hamsta output and capture jobid
        2. get job terminal output through hamsta cmd "
           feed_hamsta.pl --query_log jobid 127.0.0.1"
        3. search keyword "http:.*submission_id.*" to capture url
        '''
        se_qadb_url = re.search(search_key, output, re.I)
        
        if se_qadb_url:
            qadb_url = se_qadb_url.group()
            LOGGER.info("QADB url : %s" %qadb_url)
            return qadb_url
        else:
            LOGGER.warn("Failed to get QADB url for test suite, use local suite log")
            #TODO, need to discuss for the return value
            return ""

    def getSubCaseData(self, output, prefix_tc_cont="STDOUT  job"):
        '''Split result and get sub test case result,
           then convert sub result into list

        Sub case result content:
        "2015-04-09 15:37:28 STDOUT  job **** Test in progress ****
         2015-04-09 16:15:40 STDOUT  job sles-11-sp2-64-fv-def-net ... ... PASSED (35m10s)
         2015-04-09 16:15:40 STDOUT  job sles-11-sp3-64-fv-def-net ... ... FAILED (37m16s)
         2015-04-09 16:15:40 STDOUT  job sles-11-sp3-32-fv-def-net ... ... PASSED (38m12s)
         2015-04-09 16:15:40 STDOUT  job sles-11-sp2-32-fv-def-net ... ... SKIPPED (38m12s)
         2015-04-09 16:15:40 STDOUT  job sles-11-sp2-32-fv-def-net ... ... TIMEOUT (38m12s)
         2015-04-09 16:15:40 STDOUT  job **** Test run complete **"
         
         Result:
         [{'step_name':'sles-11-sp2-64-fv-def-net',
           'step_status':'PASSED',
           'step_duration':1000,
           'step_stdout':'',
           'step_errout':''},
           {...},....]
        '''
        def _convertTime(str_time="0d0h0m0s"):
            day_num = hour_num = min_num = sec_num = 0
            if 'd' in str_time:
                day_num = re.search("(\d+)d", str_time).groups()[0]
            if 'h' in str_time:
                hour_num = re.search("(\d+)h", str_time).groups()[0]
            if 'm' in str_time:
                min_num = re.search("(\d+)m", str_time).groups()[0]
            if 's' in str_time:
                sec_num = re.search("(\d+)s", str_time).groups()[0]
            total_sec = int(day_num)*24*3600 + int(hour_num)*3600 + int(min_num)*60 + int(sec_num)
            return total_sec

        tmp_allcase_result = []
        case_cont_compile = re.compile(
            ("%s\s+([ \S\w]+).*(passed|failed|skipped|timeout).*\((\S+)\)" %prefix_tc_cont),
            re.I)
        case_result_list = re.findall(case_cont_compile, output)
        if case_result_list:
            for case_result in case_result_list:
                tmp_case_map = {}
                tmp_case_map["step_name"] = case_result[0]
                tmp_case_map["step_status"] = case_result[1] != "TIMEOUT" and case_result[1] or "failed"
                tmp_case_map["step_duration"] = _convertTime(case_result[2])
                tmp_case_map["step_stdout"] = ""
                tmp_case_map["step_errout"] = ""
                tmp_allcase_result.append(tmp_case_map)
        else:
            tmp_allcase_result = []
        LOGGER.debug(case_result_list)
        LOGGER.debug("test for getSubCaseData, output:" + output)
        return tmp_allcase_result

    def parseOutput(self, output):
        '''Parse hamsta output and get job stdout
        '''
        #Get job id
        job_id = self.getJobID(output)
        if job_id == 0:
            return output

        cmd_get_result = self.cmd_getoutput %(job_id)
        return_code, case_result = runCMDBlocked(cmd_get_result)

        return case_result or output

    def _getRepoSource(self, source_name):
        """Get repository url (ftp/http) path by local get_source.sh script
        
        source name : source.http.sles-11-sp4-64
        execute cmd "/usr/share/qa/virtautolib/lib/get-source.sh -p ${source name}"
        to get repo of source name
        """
        #source_prd = "source.%s.%s"%(self.repo_type, self.prd_ver.lower())

        if not os.path.exists(self.get_source):
            LOGGER.error(("Failed to get repository due to %s does not exist"
                          %prefix_cmd_get_source))
        
            return ""

        cmd_get_repo =  self.get_source + " -p " + source_name

        LOGGER.info("Get repository with cmd[%s]" %(cmd_get_repo))
        return_code, result_buf = runCMDBlocked(cmd_get_repo)
        if return_code != 0:
            LOGGER.error(result_buf)
            return ""
        else:
            return result_buf.strip()

    def checkHostStatus(self, timeout=200):
        now = time.time()
        while time.time() - now < timeout:
            if AllStaticFuncs.checkIPAddress(self.host):
                return True
            
            time.sleep(5)
        
        return False

    def execHamstaJob(self, cmd, timeout, job_sketch, phase, doc_str_flag=False, save_result=True):
        '''Common function, which executes hamsta cmd to finish:
        1. collect hamsta output
        2. collect job terminal output and case substr.
        3. analyze result and generate job info map
        '''
        if not self.checkHostStatus(timeout=1800):
            LOGGER.error("Host ip [%s] is not up status on hamster" %self.host)
            return_code = job_status_code = 1
            sub_tc_result = []
            hamsta_output = job_result_all = 'Host [%s] is not available' %self.host
            qadb_link = ''
            job_sketch = 'Check Host Status'
            start_time = end_time = datetime.datetime.now()
            self.status = False
        else:
            if DEBUG:
                
                cmd = (self.feed_hamsta +  " -x "
                       "\"%s\" -h %s 127.0.0.1 -w" %(cmd, self.host))
            LOGGER.info("Execute \"%s\" on %s machine" %(job_sketch, self.host))
            (return_code, hamsta_output,
             start_time, end_time) = runCMDNonBlocked(cmd, timeout=timeout)
            LOGGER.info('CMD:%s, return_valure:%s, return_result:%s' %(cmd, str(return_code), hamsta_output))
            #Get qadb link for test suite
            job_status = self.getJobStatus(hamsta_output)
    
            #Analyze hamsta status and job status
            if return_code == 0:
                if job_status == "passed" :
                    job_status_code = 0
                    self.status = True
                    return_msg = ("Finished \"%s\" successfully" %(job_sketch))
                else:
                    job_status_code = 1
                    self.status = False
                    return_msg = ("Failed to execute \"%s\"" %(job_sketch))
                    
            else:
                if return_code == 10:
                    self.timeout_flag = True
                job_status_code = return_code
                self.status = False
    
                return_msg = ("Failed to execute \"%s\" ,cause :[%s]" %(job_sketch, hamsta_output))
   
            job_result_all = self.parseOutput(hamsta_output)
            qadb_link = self.getQadbURL(job_result_all)
    
            sub_tc_result = self.getSubCaseData(job_result_all)
            LOGGER.debug(sub_tc_result)
            fmt_result_all = AllStaticFuncs.genStandardOutout("%s %s" %(phase, job_sketch),
                                                              job_status,
                                                              job_result_all,
                                                              display_phase=True)
            LOGGER.info(return_msg)

        if self.status is True and save_result is False:
            LOGGER.debug("Do not save result data")
        else:     
            #Collect job information
            result_map = {"doc_str_flag":doc_str_flag,
                          "scenario_status":job_status_code,
                          "step_info":sub_tc_result,
                          "scenario_alloutput":job_result_all,
                          "scenario_qadb_url":qadb_link,
                          "scenario_name":job_sketch,
                          "hamsta_output":hamsta_output,
                          "hamsta_status":return_code,
                          "start_time":start_time,
                          "end_time":end_time
                          }
    
            self.result.append(result_map)


    def prepareRepos(self, source_name):
        '''Prepare all needed repo for reinstallation host
        '''
        img_repo = self._getRepoSource(source_name)

        '''
        virttest_source_name = "source.%s.%s"%("virttest", self.prd_ver.lower())
        virttest_repo = self.getRepoSource(virttest_source_name)
        virtdevel_source_name = "source.%s.%s"%("virtdevel", self.prd_ver.lower())
        virtdevel_repo = self.getRepoSource(virtdevel_source_name)

        if host_img_repo == "" or virttest_repo == "" or virtdevel_repo == "":
        '''
        if img_repo == "":
            self.status = False
            LOGGER.error("Failed to install host due to needed repos do not exist.")
            result_map = {"scenario_status":30,
                          "step_info":[],
                          "scenario_alloutput":"Needed repos do not exist",
                          "doc_str_flag":True,
                          "scenario_qadb_url":"",
                          "scenario_name":"Reinstall host",
                          "hamsta_output":"Needed repos do not exist",
                          "hamsta_status":0,
                          "start_time":datetime.datetime.now(),
                          "end_time":datetime.datetime.now()}
            self.result.append(result_map)
        
        return img_repo

    def switchXenKernel(self, phase="Phase0", timeout=1800):
        '''Switch xen kernel for supporting xen virtualization ,
        execute hamsta cmd "feed_hamsta.pl -t 1 -n set_xen_default -h host"
        '''
        if self.status:
            time.sleep(60)
            cmd_switch_xen_ker = self.cmd_switchxenker %dict(host=self.host)
            if DEBUG:
                cmd_switch_xen_ker = "/tmp/test.sh xen"
            self.execHamstaJob(cmd=cmd_switch_xen_ker,
                               timeout=timeout,
                               job_sketch="Switch xen kernel",
                               phase=phase)
        else:
            LOGGER.error("Last phase is failed, skip xen kernel switching")

    def installHost(self, phase="phase0", timeout=80000):
        """Reinstall host by hamsta cmd:
        feed_hamsta.pl -t 5 --re_url  repo -re_sdk sdk --pattern kvm/xen_server
        -rpms qa_test_virtualization -h host 127.0.0.1 -w

        if xen type, execute extra switching xen kerenl
        """
        #Prepare all needed repos
        source_name = "source.%s.%s"%(self.repo_type, self.prd_ver.lower())
        host_img_repo = self.prepareRepos(source_name)

        #Get host install repository 
        if self.status:
            
            cmd_install_host = (self.cmd_installhost %dict(img_repo=host_img_repo,
                                                           #addon_repo=addon_repo,
                                                           virttype=self.virt_type.lower(),
                                                           host=self.host,))
            '''
            cmd11 = (self.feed_hamsta + " -x \"ls \" "
                          "-h %(host)s 127.0.0.1 -w")
            cmd_install_host = cmd11 %dict(host=self.host)
            '''
            LOGGER.info(("Start to install host with cmd[%s] on machine %s"
                         %(cmd_install_host, self.host)))
            #Install host
            self.execHamstaJob(cmd=cmd_install_host,
                               timeout=timeout,
                               job_sketch="Install host",
                               phase=phase)
            #Switch xen kernel
            if self.virt_type == "XEN":
                self.switchXenKernel()
        else:
            LOGGER.warn("Failed to reserver host, skip host reinstallation")



    def installVMGuest(self, filter="", process_num=4, timeout=180000):
        """
        Precondition : virt-install test suite should be installed when reinstallation host
        
        Thru execute hamsta cmd to invoke virt-install test suite ,then automatiocally 
        install guest on host.
        """
        if self.status:

            cmd_install_guest = (self.cmd_installguest %dict(host=self.host,
                                                             filter=filter,
                                                             process_num=process_num,
                                                             test_mode=self.test_mode,
                                                             ))
            '''
            cmd11 = (self.feed_hamsta + " -x \"ls \" "
                          "-h %(host)s 127.0.0.1 -w")
            cmd_install_guest = cmd11 %dict(host=self.host)
            '''
            LOGGER.info(("Start to install guest with cmd[%s] on host %s"
                         %(cmd_install_guest, self.host)))

            self.execHamstaJob(cmd=cmd_install_guest,
                               timeout=timeout,
                               job_sketch="Install guest",
                               phase="Phase3")

        else:
            LOGGER.warn("Last phase is failed, skip guest installing")


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

        repo_chg_ver = self.getRepoChgVer(self.prd)

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
                self.host = self.queue.get(block=True, timeout=2)
                if AllStaticFuncs.checkIPAddress(self.host):
                    LOGGER.info("Reserve host ip [%s]" %self.host)
                    return True
                else:
                    self.releaseHost()
                    time.sleep(20)
                LOGGER.warn("No available host currently, wait 10s....")
        LOGGER.error("There is no available host, exit!!")

        self.status = False
        self.no_host_flag = True
        result_map = {"scenario_status":20,
                      "step_info":[],
                      "scenario_alloutput":"No Availbale host",
                      "doc_str_flag":True,
                      "scenario_qadb_url":self.qadb_link,
                      "scenario_name":"Reserve host",
                      "hamsta_output":"No Availbale host",
                      "hamsta_status":0,
                      "start_time":start_time,
                      "end_time":datetime.datetime.now()}
        self.result.append(result_map)

    def releaseHost(self):
        '''Back host address into queue after finishing test on host
        '''
        self.queue.put(self.host)

    def getRepoChgVer(self, prd):
        '''Get change version of repo
        '''
        if self.test_mode == "std":
            return self.build_ver
        else:
            prd_ver = prd.strip().split(".")[0]
            return ''.join(re.findall("%s-devel.*?;|%s-test.*?;" %(prd_ver,prd_ver),
                                      self.build_ver, re.I))

    def impExteralScript(self, script_name):
        '''This may be a temporary function
        '''
        #abs_script_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), script_name)
        abs_script_path = "/tmp/%s" %script_name
        if os.path.exists(abs_script_path):
            scp_cmd = "scp -r -p %s %s@%s:/tmp/%s" %(abs_script_path,
                                                  'root',
                                                  self.host,
                                                  script_name)
            (rc, rr) = runCMDNonBlocked(scp_cmd, timeout=60)[:2]
            LOGGER.info("scp cmd %s : return : %d, %s" %(scp_cmd, rc, rr))
            
            run_cmd = "ssh root@%s /tmp/%s" %(self.host, script_name)
            (rc, rr) = runCMDNonBlocked(run_cmd, timeout=60)[:2]

            LOGGER.info("run cmd %s : return : %d, %s" %(run_cmd, rc, rr))
        else:
            LOGGER.info("THere is no tmporary file, skip")

    def updateRPM(self, phase="Phase0", timeout=3600):
        """Function which update host by hamsta API
        """
        cmd_update_rpm = (self.feed_hamsta +
                          " -x \"source /usr/share/qa/virtautolib/lib/virtlib;"
                          "update_virt_rpms off on off\""
                          " -h %(host)s 127.0.0.1 -w" %dict(host=self.host))
        '''
        cmd11 = (self.feed_hamsta + " -x \"ls \" "
                      "-h %(host)s 127.0.0.1 -w")
        cmd_update_rpm = cmd11 %dict(host=self.host)
        '''

        if self.status:

            if DEBUG:
                cmd_update_rpm = "/tmp/test.sh rpm"
            LOGGER.info("Start to upgrade RPM with cmd [%s] %s" %(cmd_update_rpm, self.host))
            self.execHamstaJob(cmd=cmd_update_rpm,
                               timeout=timeout,
                               job_sketch="Upgrade RPM",
                               phase=phase)
            
            # Reboot machine for recovering machine intial status
            #self.rebootHost(phase=phase, job_sketch="Recover Machine Status", chk_postive_status=False)

        else:
            LOGGER.warn("Last phase failure, skip rpm updating.")            

    def makeEffect2RPM(self, phase="Phase0", job_sketch="Reboot Machine For Upgrade of RPM"):

        if self.status:
            # Only "SLES-12" product needs to switch kernel again after updating rpm
            if 'SLES-12' in self.prd_ver and self.virt_type == "XEN":
                #Switch xen kernel
                self.switchXenKernel(phase=phase)
            else:
                self.rebootHost(phase=phase, job_sketch=job_sketch, timeout=3600)
        else:
            LOGGER.warn("Last phase failure, skip reboot or switch xen kernel step.") 

    def setDefaultGrub(self, phase="Phase0", timeout=1800):
        (return_code, output) = runCMDBlocked(
            "/usr/share/hamsta/feed_hamsta.pl -p 127.0.0.1")

        re_i = re.search("%s.*VERSION=(\d+)" %(self.host), output)
        if re_i:
            host_v = re_i.groups()[0]
        else:
            host_v = 0
        
        LOGGER.debug("Host %s version is %s " %(self.host, str(host_v)))
        if  11 < int(host_v):
            cmd_setgrub = self.cmd_runcmd %dict(runcmd="grub2-once 0",
                                                host=self.host)
        elif 11 >= int(host_v):
            cmd_setgrub = self.cmd_runcmd %dict(runcmd="grubonce 0",
                                                host=self.host)
        else:
            cmd_setgrub = ""

        LOGGER.debug("setDefaultGrub, debuging ......")
        if cmd_setgrub:
            self.execHamstaJob(cmd=cmd_setgrub,
                               timeout=timeout,
                               job_sketch="Recover Grub Options",
                               phase=phase)

            #self.rebootHost(phase=phase, job_sketch="Recover Machine Status", chk_postive_status=False)

    def rebootHost(self, phase="Phase0", job_sketch="Reboot Host", timeout=1800, chk_postive_status=True):
        '''Reboot host by hamsta cmd
        '''
        cmd_reboot_host = self.cmd_reboot_host %dict(host=self.host)

        if DEBUG:
            cmd_reboot_host = "/tmp/test.sh reboot"

        if self.status:
            if chk_postive_status is True:
                LOGGER.info("Start to reboot host with cmd [%s]  for %s" %(cmd_reboot_host, self.host))
                self.execHamstaJob(cmd=cmd_reboot_host,
                                    timeout=timeout,
                                    job_sketch=job_sketch,
                                    phase=phase)
                time.sleep(180)
            if  chk_postive_status is False:
                pass
        else:
            if chk_postive_status is True:
                LOGGER.warn("Last phase failure, skip rebooting host.")
            else:
                LOGGER.info("Start to reboot host with cmd [%s]  for %s" %(cmd_reboot_host, self.host))
                self.execHamstaJob(cmd=cmd_reboot_host,
                                    timeout=timeout,
                                    job_sketch=job_sketch,
                                    phase=phase)
                self.status = False
                time.sleep(180)

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
    def _installGuestDevel(gi_inst):
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

    _installGuestDevel(vir_opt)

    vir_opt.writeLog2File()
    LOGGER.info("Product version [%s] finished" %prd)

    return vir_opt.assembleResult()


class ConvertJson(object):
    '''Convert virtualization test result into json format data, which
        supports to cucumber report plugin to generate pretty report.
    '''
    def __init__(self, result):
        self.result = result

    def genJsonFile(self):
        '''Generate json file with json data, file path is the 
        ${WORKSPACE}/result.json on jenkins environemnt, or the path 
        is  ./result.json
        '''
        json_data = self.getJsonData()

        file_path = os.path.join(os.getenv("WORKSPACE",
                                           os.getcwd()),
                                           'result.json')
        if os.path.exists(file_path):
            os.remove(file_path)
        with open(file_path, "w+") as f:
            f.write(json_data)
        os.chmod(file_path, 0777)

    def getJsonData(self):
        '''Return json data
        '''
        tmp_json_rel = []
        for i, fet in enumerate(self.result):
            tmp_json_rel.append(
                self.getFeatureData(name=(fet["feature_prefix_name"] +
                                    fet["feature_prj_name"]),
                                    uri="%s_%d" %(fet["feature_prj_name"], i),
                                    desc=fet["feature_desc"],
                                    sen_info=fet["scenario_info"]))
        
        return json.dumps(tmp_json_rel, sort_keys = True, indent = 4, )

    def getFeatureData(self, name, uri, desc, sen_info, keyword="Feature"):
        '''Generate feature section data
        '''
        tf_map = {}
        tf_map["keyword"] = keyword
        tf_map["name"] = name
        tf_map["uri"] = uri
        tf_map["description"] = desc
        tf_map["tags"] = [{'name':name}]
        tc_element = []
        scenario_info = sen_info
        
        for scn in scenario_info:
            if 'doc_str_flag' in scn:
                doc_str_flag = scn["doc_str_flag"]
            else:
                doc_str_flag = False
            
            if 'end_time' in scn and 'start_time' in scn:
                sen_duration = (time.mktime(
                    datetime.datetime.timetuple(scn["end_time"])) - 
                                time.mktime(
                    datetime.datetime.timetuple(scn["start_time"])))
            else:
                sen_duration = 0
            sen_output = scn["scenario_alloutput"] or scn["hamsta_output"]
            tc_element.append(self.getScenarioData(
                                name=scn["scenario_name"],
                                step_info=scn["step_info"],
                                sen_output=sen_output,
                                qadb_url=scn["scenario_qadb_url"],
                                sen_status=scn["scenario_status"],
                                sen_duration=sen_duration,
                                doc_str_flag=doc_str_flag))
        
        tf_map["elements"] = tc_element

        return tf_map

    def getScenarioData(self, name, step_info, sen_output, qadb_url, sen_status, 
                        sen_duration, doc_str_flag=False, sen_type="Sce_T", keyword="Scenario"):
        '''Generate scenario section data
        '''
        ts_map = {}
        tc_step = []
        ts_map["keyword"] = keyword
        ts_map["type"] = sen_type
        if qadb_url:
            ts_map["name"] =  (name + "  <a href=%s>QADB URL</a>"
                                       %qadb_url)
        else:
            ts_map["name"] =  name
        
        if step_info:
            for step_i, step in enumerate(step_info):
                step_name = step["step_name"]
                step_status = step["step_status"].lower()
                step_duration = step["step_duration"]
                step_errout = step["step_errout"]
                step_stdout = step["step_stdout"]
                if step_status != "passed":
                    error_msg = step_errout or "%s failure : %s" %(name, step_name)
                else:
                    error_msg = ""
                
                if 'step_doc_str_flag' in step:
                    doc_str_flag = step["step_doc_str_flag"]

                step_info = self.addStep(step_name="",
                                        step_status=step_status,
                                        step_keyword=step_name,
                                        step_duration=step_duration,
                                        step_stdout_msg=step_stdout,
                                        step_error_msg=error_msg,
                                        doc_str_flag=doc_str_flag)
                tc_step.append(step_info)
        else:
            if sen_status != 0:
                step_name = name.lower()
                error_msg = sen_output
                step_info = self.addStep(step_name=step_name,
                                         step_status="failed",
                                         step_keyword=step_name,
                                         step_duration=sen_duration,
                                         step_stdout_msg="",
                                         step_error_msg=error_msg)
                tc_step.append(step_info)
            else:
                pass        
        
        ts_map["steps"] = tc_step
        return ts_map

    def addStep(self, step_stdout_msg, step_name="", step_status="passed",
                step_keyword="", step_duration=0, step_error_msg="", doc_str_flag=False):
        '''Generate step secitons data
        '''
        tc_step_map = {}
        tc_step_map["keyword"] = step_keyword.capitalize()
        tc_step_map["name"] = "  " + step_status.lower()
        tc_step_map["match"] = {}
        if doc_str_flag:
            tc_step_doc = {}
            tc_step_doc["value"] = AllStaticFuncs.cutString(step_stdout_msg)
            tc_step_map["doc_string"] = tc_step_doc

        tc_step_result = {}
        tc_step_result["status"] = step_status.lower()
        if tc_step_result["status"] != "passed":
            tc_step_result["error_message"] = AllStaticFuncs.cutString(step_error_msg)
        tc_step_result["duration"] = step_duration * pow(10,9)
        tc_step_map["result"] = tc_step_result
        
        return tc_step_map


class AllStaticFuncs(object):
    """Class which contains all staticmethod functions
    """
    def __init__(self):
        pass

    @staticmethod
    def checkIPAddress(ip_address):
        """Check if the host address is available through hamsta command line
        """
        (return_code, output) = runCMDBlocked(
            "/usr/share/hamsta/feed_hamsta.pl -p 127.0.0.1")
        LOGGER.debug("Current all availiable host %s" %output)
        if return_code == 0 and output:
            #if len(ip_address.split(".")) == 4 and re.search(ip_address.strip(),
            if re.search(ip_address.strip(), output, re.I):
                return True
            else:
                return False

    @staticmethod
    def getAvailHost(host_list):
        """Get availiable host list
        """
        tmp_host_list = map(lambda x: x.strip(), host_list)
        tmp_host_list = filter(AllStaticFuncs.checkIPAddress, tmp_host_list)
        LOGGER.info("Available hosts :" + str(tmp_host_list))
        return tmp_host_list

    @staticmethod
    def writeLog2File(task, logname, returncode=0,
                      host="1.1.1.1", content="empty", duration="0"):
        """Write output info of command line to file
        """
        if os.path.exists(logname):
            os.remove(logname)
        with open(logname, "a+") as f:
            f.write("Task : %s" %(task) + os.linesep)
            f.write("Host : %s" %(host) + os.linesep)
            if returncode == 0:
                f.write("Status : Passed" + os.linesep)
            elif returncode == 10:
                f.write("Status : Timeout" + os.linesep)
            else:
                f.write("Status : Failed" + os.linesep)

            f.write(os.linesep)
            f.write("Running time : %s" %(duration) + os.linesep)
            f.write("-" * 30 + os.linesep)
            f.write(os.linesep)
            f.write("Output : " + os.linesep +
                    ("\t%s" %(content.replace(os.linesep, os.linesep+"\t"))))
            f.flush()
            f.close()

    @staticmethod
    def getBuildPath():
        """Get build path, environment WORKSPACE and BUILD_TAG are built-in 
        environment variable of jenkins
        """
        build_path = os.path.join(os.getenv("WORKSPACE", os.getcwd()),
                                   "LOG", os.getenv("BUILD_TAG", ""))
        if not os.path.exists(build_path):
            os.makedirs(build_path)
        return build_path

    @staticmethod
    def getJobURL():
        """Get environment variable JOB_URL which belongs to Jenkins variable
        """
        return os.getenv("JOB_URL", os.getcwd())

    @staticmethod
    def cutString(string, max_len=100, separator=os.linesep):
        """Cut string, string lenth is less than 100 characters
        """
        lines = string.split(separator)
        for l_i, line in enumerate(lines):
            quotient = len(line) / max_len
            for q_i in range(0, quotient):
                cut_len = (q_i + 1) * max_len
                lines[l_i] = lines[l_i][:cut_len] + os.linesep + lines[l_i][cut_len:]
        return '\n'.join(lines)
        #lines = string.split(separator)
        
        #return '\n'.join(map(lambda x:(len(x) < max_len and x or x[:max_len] + os.linesep + x[max_len:]), lines))
  
    @staticmethod
    def compressFile(file_name):
        """Compress log folder/files
        """
        if os.path.exists(file_name):
            if os.path.isfile(file_name):
                basname_file = os.path.basename(file_name)
                dirname_file = os.path.dirname(file_name)
            elif os.path.isdir(file_name):
                if file_name[-1] == os.linesep:
                    basname_file = os.path.basename(file_name[:-1])
                else:
                    basname_file = os.path.basename(file_name)
                dirname_file = os.path.dirname(file_name)

            tar_file_name = file_name + ".tar.gz"
            os.chdir(dirname_file)
            sz_cmd = "tar czf " + tar_file_name + " " + basname_file
            return_code, _output = runCMDBlocked(sz_cmd)
            if return_code != 0:
                LOGGER.warn("Failed to compress log file [%s]" %file_name)
        else:
            LOGGER.error("Log folder/file does not exist")

    @staticmethod
    def cleanJosnFIle():
        '''Rmove file content
        '''
        file_path = os.path.join(os.getenv("WORKSPACE", os.getcwd()),
                                     'result.json')
        with open(file_path, "w+") as f:
            f.truncate()

    @staticmethod
    def genStandardOutout(phase="", status="passed",
                          output ="", display_phase=False):
        if display_phase:
            tmp_whole_info = ("%(phase)s:\n"
                              "\tStatus:\n"
                              "\t\t%(status)s\n"
                              "\tOutput:\n"
                              "\t\t%(output)s\n" 
                              %dict(phase=phase,
                                    status=status,
                                    output=output.replace(os.linesep,
                                                          os.linesep+"\t\t")))
        else:
            tmp_whole_info = ("\tDetails:\n"
                              "\t\t%(output)s\n" 
                              %dict(output=output.replace(os.linesep,
                                                          os.linesep+"\t\t")))
        return tmp_whole_info


class MultipleProcessRun(object):
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

        self.test_type = self.options.test_type
        self.build_version = self.options.product_ver.strip()
        self.test_mode = self.options.test_mode.strip()

        self.host_list = []
        self.task_list = []
        self.param = ()
        
        self.cleanFileFlag()

    def startRun(self):
        self.host_list = AllStaticFuncs.getAvailHost(self.options.gi_host_list.split(","))
        self.task_list = self.options.gi_h_product_list.strip().split(",")
        self.param = (self.options.gi_g_product_list, self.options.gi_g_concurrent_num,
                      self.build_version, self.test_mode)

        #Pool size is defined through host number.
        if self.host_list:
            self.pool = multiprocessing.Pool(processes=len(self.host_list))
            LOGGER.debug("Create process pool[%d]" %len(self.host_list))
            self.initialQueue()
            self._giMultipleTask()
            self.closeAndJoinPool()
        else:
            self.prj_status["status"]= False
            self.createFileFlag()
            self.prj_status["info"] = "There is no available host"

    def _giMultipleTask(self):
        """Execute multiple taskes in processes pool only for guest installing
        """
        for task in self.task_list:
            #installGuest(task, self.param,self.queue)

            self.result.append([task,
                                self.pool.apply_async(
                                    installGuest,
                                    (task, self.param, self.queue)
                                    )])

    def createFileFlag(self, file_name="no_availiable_host.flg"):
        '''Generate a file flag to workspace for jenkins using
        '''
        abs_file_name = os.path.join(os.getenv("WORKSPACE", os.getcwd()),
                                     file_name)
        
        if os.path.exists(abs_file_name):
            pass
        else:
            open(abs_file_name, 'a').close()

    def cleanFileFlag(self, file_name="no_availiable_host.flg"):
        '''Remove file flag
        '''
        abs_file_name = os.path.join(os.getenv("WORKSPACE", os.getcwd()),
                                     file_name)
        if os.path.exists(abs_file_name):
            os.remove(abs_file_name) 
        
    def combineProductV(self, list_a, list_b):
        '''Combine orginal product with updated product
        Sample : a = ['SLES-11-SP3-64.XEN','SLES-11-SP3-64.KVM', 'SLES-12-SP0-64.XEN','SLES-12-SP0-64.KVM','SLES-11-SP4-64.XEN','SLES-11-SP4-64.KVM']
                 b = ['SLES-12-SP0-64','SLES-11-SP4-64']
                 combineProductV(a,b)
        Return : [('SLES-11-SP3-64.XEN', 'SLES-11-SP4-64'), ('SLES-11-SP3-64.KVM', 'SLES-11-SP4-64'), ('SLES-11-SP4-64.XEN', 'SLES-12-SP0-64'), ('SLES-11-SP4-64.KVM', 'SLES-12-SP0-64')]
        '''
        ALL_SENARIOS = [('SLES-11-SP3-64', 'SLES-11-SP4-64'),
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
        tmp = []
        for a_i in list_a:
            for b_i in list_b:
                a_v,a_p = a_i.split('.')[0].split("-")[1:3]
                b_v,b_p = b_i.split('.')[0].split("-")[1:3]
                a_p_n = int(a_p.replace('SP',''))
                b_p_n = int(b_p.replace('SP',''))
        
                if a_v == b_v and b_p_n - a_p_n == 1:
                    tmp.append((a_i, b_i))
                elif int(b_v) - int(a_v) == 1:
                    if int(a_v) == 11:
                        if b_p == "SP0" and a_p == "SP4":
                            tmp.append((a_i, b_i))
                    else:
                        pass
            
        return tmp
        '''

    def initialQueue(self):
        """Initial queue, add host name to queue
        """
        LOGGER.debug("Initial queue with host name")
        for host in self.host_list:
            self.queue.put(host)

    def getLogName(self, filename):
        """Get initial log path
        """
        return os.path.join(self.logpath, filename)

    def closeAndJoinPool(self):
        """Close and wait pool
        """
        self.pool.close()
        self.pool.join()

    def getResultMap(self):
        """Display result
        """
        LOGGER.info("Get all processes infomation")
        tmp_prj_result = []
        for res in self.result:
            tc_result = res[1].get()
            #Check project status
            self.prj_status["status"] &= tc_result["feature_status"]
            tmp_prj_result.append(tc_result)
        LOGGER.debug(tmp_prj_result)

        #Generate json file for cucumber report
        ConvertJson(tmp_prj_result).genJsonFile()

    def getMulPoolStatus(self):
        return self.prj_status


class LoggerHandling(object):
    """Class which support to add five kind of level info to file
    and standard output 
    """
    def __init__(self, log_file, log_level=logging.DEBUG):
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(filename)s[line:%(lineno)d] [%(process)d] [%(threadName)s] %(levelname)-6s | %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            filename=log_file,
                            filemode='w')

        console = logging.StreamHandler()
        console.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s [%(process)d] [%(threadName)s]: %(levelname)-8s %(message)s')
        console.setFormatter(formatter)

        self.logger = logging.getLogger('')
        self.logger.addHandler(console)

    def debug(self, message):
        """Display debug message
        """
        self.logger.debug(message)

    def info(self, message):
        """Display info message
        """
        self.logger.info(message)

    def warn(self, message):
        """Display warning message
        """
        self.logger.warn("\033[1;33;47m" + message + "\033[0m")

    def error(self, message):
        """Display error message
        """
        self.logger.error("\033[1;31;47m" + message + "\033[0m")

    def crit(self, message):
        """Display Criticall message
        """
        self.logger.critical(message)

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

LOGGER = LoggerHandling(os.path.join(AllStaticFuncs.getBuildPath(), "sys.log"), logging.DEBUG)
'''
if __name__ == "__main__":
    main()
'''
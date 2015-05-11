#!/usr/bin/python
"""
Automatically distribute task into available host and run guest installing by virt-install,
after done, generate case log and html report.
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
            result_buf = "--------timeout(%dsecs)--------\n" %timeout
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

    def __init__(self, prd, queue):
        '''Initial variable and constant value
        '''
        self.prd = prd
        self.queue = queue
        self.repo_type = "http"
        self.prd_ver, self.virt_type = prd.split(".")

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
                                "--re_sdk %(addon_repo)s --pattern %(virttype)s_server "
                                "-rpms qa_test_virtualization -h %(host)s 127.0.0.1 -w")
        
        self.cmd_installguest = (self.feed_hamsta + " -x "
                                 "\"%(guest_script)s\" -h %(host)s 127.0.0.1 -w")
        
        self.cmd_switchxenker = (self.feed_hamsta + " -t 1 -n set_xen_default "
                                 "-h %(host)s 127.0.0.1 -w")
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
        #LOGGER.debug(("Write log to file , params :[task=%s,returncode=%d,"
        #              "logname=%s,host=%s,content=%s]" %(task, returncode,
        #                                                 logname, host, content)))
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
            return "abnormal"
        cmd_get_job_status = self.cmd_getstatus %(job_id)
        status_buf= runCMDNonBlocked(cmd_get_job_status, timeout=10)[1]
        se_job_status = re.search("stauts : (\S+)", status_buf, )
        if se_job_status:
            job_status = se_job_status.groups()[0].strip()
        else:
            LOGGER.warn("Failed to get job status from %s" %output)
            job_status = "failed"
        
        return job_status

    def getJobID(self, output, search_key="internal id: (\d+)"):
        '''Get job id thru hamsta output,
        Search key word "internal id :" and capture the jobid with regular expression
        
        Sample:
        hamsta output :
        "
        Connecting to master 127.0.0.1 on 18431
        MASTER::FUNCTIONS cmdline Reinstall Job send to scheduler, at 147.2.207.60 internal id: 1317
        "
        result: return 1317
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
            return  os.path.join(AllStaticFuncs.getJobURL(), "ws",
                                 "LOG", os.getenv("BUILD_TAG", ""), self.prd)

    def getSubCaseData(self, output, prefix_tc_cont="STDOUT  job"):
        '''Collect sub test case result
        Sub case result content:
        "2015-04-09 15:37:28 STDOUT  job **** Test in progress ****
         2015-04-09 16:15:40 STDOUT  job sles-11-sp2-64-fv-def-net ... ... PASSED (35m10s)
         2015-04-09 16:15:40 STDOUT  job sles-11-sp3-64-fv-def-net ... ... FAILED (37m16s)
         2015-04-09 16:15:40 STDOUT  job sles-11-sp3-32-fv-def-net ... ... PASSED (38m12s)
         2015-04-09 16:15:40 STDOUT  job sles-11-sp2-32-fv-def-net ... ... SKIPPED (38m12s)
         2015-04-09 16:15:40 STDOUT  job **** Test run complete **"
         
         Result:
         [{'step_name':'sles-11-sp2-64-fv-def-net',
           'step_status':'PASSED',
           'step_duration':1000,
           'step_stdout':'',
           'step_errout':''},
           {...},....]
        '''
        def _convertTime(str_time="0h0m0s"):
            hour_num = min_num = sec_num = 0
            if 'h' in str_time:
                hour_num = re.search("(\d+)h", str_time).groups()[0]
            if 'm' in str_time:
                min_num = re.search("(\d+)m", str_time).groups()[0]
            if 's' in str_time:
                sec_num = re.search("(\d+)s", str_time).groups()[0]
            total_sec = int(hour_num) * 3600 + int(min_num) * 60 + int(sec_num)
            return total_sec

        tmp_allcase_result = []
        case_cont_compile = re.compile(
            ("%s (\S+).*(passed|failed|skipped).*\((\S+)\)" %prefix_tc_cont),
            re.I)
        case_result_list = re.findall(case_cont_compile, output)
        if case_result_list:
            for case_result in case_result_list:
                tmp_case_map = {}
                tmp_case_map["step_name"] = case_result[0]
                tmp_case_map["step_status"] = case_result[1]
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
        '''Parse hamsta output and get substr
        1. get jobid form hamsta output
        2. get job output through hamsta cmd
        '''
        #Get job id
        job_id = self.getJobID(output)
        if job_id == 0:
            return output

        cmd_get_result = self.cmd_getoutput %(job_id)
        return_code, case_result = runCMDBlocked(cmd_get_result)

        return case_result or output

    def getRepoSource(self, source_name):
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

    def execHamstaJob(self, cmd, timeout, job_sketch, phase, doc_str_flag=False):
        '''Common function, which executes hamsta cmd to finish:
        1. collect hamsta output
        2. collect job terminal output and case substr.
        3. analyze result and generate job status map
        '''

        LOGGER.info("Execute \"%s\" on %s machine" %(job_sketch, self.host))
        (return_code, hamsta_output,
         start_time, end_time) = runCMDNonBlocked(cmd, timeout=timeout)

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
        #LOGGER.info("Finally Output:" + fmt_result_all)
        LOGGER.info(return_msg)
        #Collect job infomation
        result_map = {"doc_str_flag":doc_str_flag,
                      "scenario_status":job_status_code,
                      "step_info":sub_tc_result,
                      "scenario_alloutput":fmt_result_all,
                      "scenario_qadb_url":qadb_link,
                      "scenario_name":job_sketch,
                      "hamsta_output":hamsta_output,
                      "hamsta_status":return_code,
                      "start_time":start_time,
                      "end_time":end_time
                      }

        self.result.append(result_map)

    def _switchXenKernel(self, timeout=600):
        '''Switch xen kernel for supporting xen virtualization ,
        execute hamsta cmd "feed_hamsta.pl -t 1 -n set_xen_default -h host"
        '''
        if self.status:
            cmd_switch_xen_ker = self.cmd_switchxenker %dict(host=self.host)
            if DEBUG:
                cmd_switch_xen_kernel = "./test test"
                LOGGER.info(("Start to switch xen kernl with cmd[%s] on machine %s"
                             %(cmd_switch_xen_ker, self.host)))
    
            self.execHamstaJob(cmd=cmd_switch_xen_ker,
                               timeout=600,
                               job_sketch="Switch xen kernel",
                               phase="Phase1.1")
        else:
            LOGGER.error("Failed to install host, skip xen kernel switching")

    def prepareRepos(self):
        '''Prepare all needed repo for reinstallation host
        '''
        prd_source_name = "source.%s.%s"%(self.repo_type, self.prd_ver.lower())
        host_img_repo = self.getRepoSource(prd_source_name)
        
        virttest_source_name = "source.%s.%s"%("virttest", self.prd_ver.lower())
        virttest_repo = self.getRepoSource(virttest_source_name)
        virtdevel_source_name = "source.%s.%s"%("virtdevel", self.prd_ver.lower())
        virtdevel_repo = self.getRepoSource(virtdevel_source_name)

        if host_img_repo == "" or virttest_repo == "" or virtdevel_repo == "":
            self.status = False
            LOGGER.error("Failed to install host due to needed repos do not exist.")
            result_map = {"scenario_status":30,
                          "step_info":[],
                          "scenario_alloutput":"Needed repos do not exist",
                          "doc_str_flag":True,
                          "scenario_qadb_url":"",
                          "scenario_name":"Reserve host",
                          "hamsta_output":"Needed repos do not exist",
                          "hamsta_status":0,
                          "start_time":datetime.datetime.now(),
                          "end_time":datetime.datetime.now()}
            self.result.append(result_map)
        else:
            self.status = True
            return {'host_img_repo':host_img_repo,
                    'virttest_repo':virttest_repo,
                    'virtdevel_repo':virtdevel_repo}

    def _installHost(self, addon_repo = "http://download.suse.de/ibs/home:/jerrytang/SLE_11_SP4",
                     timeout=4800):
        """Reinstall host by hamsta cmd:
        feed_hamsta.pl -t 5 --re_url  repo -re_sdk sdk --pattern kvm/xen_server
        -rpms qa_test_virtualization -h host 127.0.0.1 -w

        if xen type, execute extra switching xen kerenl
        """
        #Prepare all needed repos
        repo_map = self.prepareRepos()
        #Get host install repository 
        if self.status:
            #Concat multiple repos for reinstallation host (virt devel repo and virt test repo)
            addon_repo = "%s,%s,%s" %(addon_repo,
                                      repo_map["virttest_repo"],
                                      repo_map["virtdevel_repo"])
            host_img_repo = repo_map["host_img_repo"]

            cmd_install_host = (self.cmd_installhost %dict(img_repo=host_img_repo,
                                                           addon_repo=addon_repo,
                                                           virttype=self.virt_type.lower(),
                                                           host=self.host,))
            LOGGER.info(("Start to install host with cmd[%s] on machine %s"
                         %(cmd_install_host, self.host)))
            if DEBUG:
                timeout = 120
                cmd_install_host = "/tmp/171test.sh p"
                LOGGER.info(("Start to install host with cmd[%s] on machine %s"
                         %(cmd_install_host, self.host)))
                ig_stript = "/tmp/27test1.sh p"
                #cmd_install_guest = "./test test"
                cmd_install_host = (self.cmd_installguest %dict(guest_script=ig_stript,
                                                                host=self.host))
    
            #Install host
            self.execHamstaJob(cmd=cmd_install_host,
                               timeout=timeout,
                               job_sketch="Install host",
                               phase="Phase1")
            #Switch xen kernel
            if self.virt_type == "XEN":
                self._switchXenKernel()
        else:
            LOGGER.warn("Failed to reserver host, skip host reinstallation")

    def _installGuest(self, ig_stript="/usr/share/qa/tools/virt-simple-run", timeout=7200):
        """
        Precondition : virt-install test suite should be installed when reinstallation host
        
        Thru execute hamsta cmd to invoke virt-install test suite ,then automatiocally 
        install guest on host.
        """
        if self.status:
            #TODO START only for test, will be remove.
            cmd1 = "scp /root/virt/virt-simple.tcf root@%s:/usr/share/qa/tcf/" %self.host
            cmd2 = "scp /root/virt/virt-simple-run root@%s:/usr/share/qa/tools/" %self.host
            cmd3 = "scp /root/virt/source.cn root@%s:/usr/share/qa/virtautolib/data/" %self.host
            cmd4 = "ssh root@%s \"mkdir /.virtinst\"" %self.host
            runCMDBlocked(cmd1)
            runCMDBlocked(cmd2)
            runCMDBlocked(cmd3)
            runCMDBlocked(cmd4)
            #TODO END
            if DEBUG:
                timeout = 120
                ig_stript = "/tmp/27test.sh"
                #cmd_install_guest = "./test test"
            cmd_install_guest = (self.cmd_installguest %dict(guest_script=ig_stript,
                                                             host=self.host))
            LOGGER.info(("Start to install guest with cmd[%s] on host %s"
                         %(cmd_install_guest, self.host)))

            self.execHamstaJob(cmd=cmd_install_guest,
                               timeout=timeout,
                               job_sketch="Install guest",
                               phase="Phase2")
        else:
            LOGGER.warn("Host installing failure, skip guest installing")


    def getResultList(self, prefix_name="Virt Install -  ",
                      feature_desc="Description of Feature", display_all=False):
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
        tmp_job_map = {}
        tmp_job_map["feature_prefix_name"] = prefix_name
        tmp_job_map["feature_host"] = self.host
        tmp_job_map["feature_prj_name"] = self.prd
        tmp_job_map["scenario_info"] = self.result
        tmp_job_map["feature_desc"] = feature_desc  + "\n\n" + "Host :%s" %self.host
        tmp_job_map["feature_status"] =  self.status

        return tmp_job_map

    def reserveHost(self, timeout=7200):
        '''Resrve available and free host
        '''
        #TODO, There are some issue
        LOGGER.info("Start to reserve host")
        now = time.time()
        while time.time() - now < timeout:
            if self.queue.qsize() == 0:
                LOGGER.warn("There is no available host in queue")
                time.sleep(20)
            else:
                self.host = self.queue.get(block=True, timeout=2)
                if AllStaticFuncs.checkIPAddress(self.host):
                    LOGGER.info("Reserve host ip [%s]" %self.host)
                    return
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
                      "start_time":datetime.datetime.now(),
                      "end_time":datetime.datetime.now()}
        self.result.append(result_map)

    def releaseHost(self):
        '''Back host address into queue after finishing test on host
        '''
        self.queue.put(self.host)

def installGuest(prd, queue=None,):
    """External function to warp gest installing functions
    """
    vir_opt = GuestInstalling(prd, queue)
    LOGGER.info("Product version [%s] starts to run on host [%s] now" %(prd, vir_opt.host))
    if vir_opt.status:
        #TODO start, gi_pg_repo will be removed during formal test
        gi_pg_repo = vir_opt.getRepoSource(
                        "source.%s.%s" %("guestinsall", vir_opt.prd_ver.lower()))
        #TODO end
        vir_opt._installHost(addon_repo=gi_pg_repo)
        vir_opt._installGuest()
        vir_opt.releaseHost()
    vir_opt.writeLog2File()
    LOGGER.info("Product version [%s] finished" %prd)
    return vir_opt.getResultList(
                feature_desc=("Target : The virt-install guest installing test."
                          " (Support xen & kvm type virtualization)\n"
                          "\tFunctions:\n"
                          "\t\t1.   Install host server remotely by HAMSTA.\n"
                          "\t\t2.   Install needed packages of virtualizaiton test.\n"
                          "\t\t2-1. Switch xen/kvm kernel\n"
                          "\t\t3.   Install guests in parallel on host server.\n"
                          "\t\t4.   Verify the installing result."))

class HostMigration(GuestInstalling):
    '''The class is only for host migration test
    '''
    def __init__(self, org_prd, dest_prd, queue):
        '''Initial function and variables, inherit GuestInstalling class
        '''
        super(HostMigration, self).__init__(org_prd, queue)
        self.dest_prd = dest_prd
        
        self.cmd_update_host = (self.feed_hamsta +  " -x "
               "\"/usr/share/qa/virtautolib/lib/vh-update.sh -p vhPrepAndUpdate "
               "-t %(virt_type)s -m %(org_prd)s -n %(dest_prd)s \" -h %(host)s 127.0.0.1 -w")
        self.cmd_verify_host = (self.feed_hamsta +  " -x "
               "\"/usr/share/qa/virtautolib/lib/vh-update.sh -p vhUpdatePostVerification "
               "-t %(virt_type)s -m %(org_prd)s -n %(dest_prd)s \" -h %(host)s 127.0.0.1 -w")
        self.cmd_reboot_host = (self.feed_hamsta +  " -t 1 -n reboot -h %(host)s "
                                "127.0.0.1 -w")

    def rebootHost(self, timeout=600):
        '''Reboot host by hamsta cmd
        '''
        if self.status:
            cmd_rb_host = self.cmd_reboot_host %dict(host=self.host,)
            LOGGER.info("Start to reboot host with cmd [%s]  for %s" %(cmd_rb_host, self.host))

            self.execHamstaJob(cmd=cmd_rb_host,
                                timeout=timeout,
                                job_sketch="Reboot Host",
                                phase="Phase4")
        else:
            LOGGER.warn("Last phase failure, skip rebooting host.")

    def updateHost(self, timeout=7200):
        """Function which update host by hamsta API
        """
        if self.status:
            if DEBUG:
                cmd_hu_host = "./test ttttttt"
            else:
                cmd_hu_host = self.cmd_update_host %dict(
                    host=self.host,
                    virt_type=self.virt_type.lower(),
                    org_prd=self.prd_ver.lower(),
                    dest_prd=self.dest_prd.lower())

            LOGGER.info("Start to upgrade host with cmd [%s] %s" %(cmd_hu_host, self.host))
            self.execHamstaJob(cmd=cmd_hu_host,
                               timeout=timeout,
                               job_sketch="Upgrade Host",
                               phase="Phase3")
        else:
            LOGGER.warn("Last phase failure, skip host updating.")

    def verifyGuest(self, timeout=2000):
        """Function which verifys result of host migration.
        Thru invoking hamsta cmd to do this operation.
        """
        if self.status:
            if DEBUG:
                cmd_hu_host = "./test tttttt"
                ig_stript = "/root/171test.sh"
                #cmd_install_guest = "./test test"
                cmd_hu_host = (self.cmd_installguest %dict(guest_script=ig_stript,
                                                           host=self.host))
            else:
                cmd_hu_host = self.cmd_verify_host %dict(host=self.host,
                                                         virt_type=self.virt_type,
                                                         org_prd=self.prd_ver.lower(),
                                                         dest_prd=self.dest_prd.lower())

            LOGGER.info("Start to verify host with cmd [%s] %s" %(cmd_hu_host, self.host))

            self.execHamstaJob(cmd=cmd_hu_host,
                                timeout=timeout,
                                job_sketch="Verify Guest",
                                phase="Phase5",
                                doc_str_flag=True)
        else:
            LOGGER.warn("Last phase failure, skip guest verfication.")

    def getSubCaseData(self, output, prefix_tc_cont="STDOUT  job",
                       start_tc_cont="Executing log comparison", 
                       end_tc_cont="Host upgrade virtualization test"):
        '''Get sub test case result
        
        Result Sample:
        "
        Executing log comparison ...
        Before virtual host upgrade, administration result table is:
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        |                         |virsh list|virsh destroy|virsh start|virsh save|virsh restore|virsh dumpxml|virsh domxml-to-native|virsh shutdown|virsh undefine|virsh define|virsh start|
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        |sles-11-sp3-64-fv-def-net|      PASS|         PASS|       PASS|      PASS|         PASS|         PASS|                  PASS|          PASS|          PASS|        PASS|       PASS|
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        |sles-11-sp4-64-fv-def-net|      PASS|         PASS|       PASS|      PASS|         PASS|         PASS|                  PASS|          PASS|          PASS|        PASS|       PASS|
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        After virtual host upgrade, administration result table is:
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        |                         |virsh list|virsh destroy|virsh start|virsh save|virsh restore|virsh dumpxml|virsh domxml-to-native|virsh shutdown|virsh undefine|virsh define|virsh start|
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        |sles-11-sp3-64-fv-def-net|      PASS|         PASS|       PASS|      PASS|         PASS|         PASS|                  PASS|          PASS|          PASS|        PASS|       PASS|
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        |sles-11-sp4-64-fv-def-net|      PASS|         PASS|       PASS|      PASS|         PASS|         PASS|                  PASS|          PASS|          PASS|        PASS|       PASS|
        -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        Congratulations! No administration result difference!
        Host upgrade virtualization test
        "
        '''
        def _getSpecialCaseInfo(start_cont="Test in progress",
                                end_cont="Test run complete"):
            se_gi_cont = re.search("%s.*%s.*?\n" %(start_cont, end_cont),
                                   output, re.S)
            
            if se_gi_cont:
                tc_rel = se_gi_cont.group()
                rpl_rlt =  re.sub(".*%s" %prefix_tc_cont, "", tc_rel, flags=re.I)
                return rpl_rlt
            else:
                return ""
        
        guest_inst_cont = _getSpecialCaseInfo()
        guest_verf_cont = _getSpecialCaseInfo(start_cont=start_tc_cont,
                                              end_cont=end_tc_cont)

        LOGGER.debug("test for getSubCaseData, output:" + guest_verf_cont)
        return guest_inst_cont or guest_verf_cont

    def getDateTimeDelta(self, beg_time, end_time):
        '''Calculate difftime.
        '''
        beg_date_time_tuple = time.mktime(datetime.datetime.timetuple(beg_time))
        end_date_time_tuple = time.mktime(datetime.datetime.timetuple(end_time))
        
        return abs(int(end_date_time_tuple - beg_date_time_tuple))
     
    def getResultList(self, prefix_name="Virt Install -  ",
                      feature_desc="Description of Feature", display_all=False):
        '''Generate data structure
        '''
        tmp_job_map = {}
        tmp_job_map["feature_prefix_name"] = prefix_name
        tmp_job_map["feature_host"] = self.host
        tmp_job_map["feature_prj_name"] = self.host

        tmp_job_map["feature_desc"] = feature_desc  + "\n\n" + "Host :%s" %self.host
        tmp_job_map["feature_status"] =  self.status
        
        scenario_info = []
        scenario_map = {}
        scenario_map["scenario_status"] = self.status
        scenario_map["scenario_name"] = "%s -> %s.%s" %(self.prd, self.dest_prd, self.virt_type)
        scenario_map["hamsta_output"] = ""
        scenario_map["scenario_qadb_url"] = ""
        step_info = []
        for sen in self.result:
            step_map = {}    
            step_map["step_name"] = sen["scenario_name"]
            step_map["step_status"] = sen["scenario_status"] and "failed" or "passed"
            step_map["step_duration"] = self.getDateTimeDelta(sen["end_time"], sen["start_time"])
            step_map["step_doc_str_flag"] = sen["doc_str_flag"]
            step_map["step_qadb_url"] = sen["scenario_qadb_url"]
            if sen["hamsta_status"] == 0:
                if sen["scenario_status"] == 0:
                    step_map["step_stdout"] = sen["step_info"] or sen["scenario_alloutput"]
                    step_map["step_errout"] = ""
                else:
                    step_map["step_errout"] = sen["step_info"] or sen["scenario_alloutput"]
                    step_map["step_stdout"] = ""
            else:
                step_map["step_stdout"] = ""
                step_map["step_errout"] = sen["hamsta_output"]
            step_info.append(step_map)
        scenario_map["step_info"] = step_info
        scenario_info.append(scenario_map)
        tmp_job_map["scenario_info"] = scenario_info 

        return tmp_job_map

def migrateHost(org_prd, dest_prd, queue=None,):
    """Externel function, only for warp migration host function
    """
    vir_opt = HostMigration(org_prd, dest_prd, queue)
    LOGGER.info("Product version [%s] starts to run on host [%s] now" %(org_prd, vir_opt.host))
    #vir_opt._installHost(addon_repo = "http://download.suse.de/ibs/home:/xlai/SLE_11_SP3/,http://download.suse.de/ibs/Devel:/Virt:/SLE-11-SP4/SLE_11_SP4,http://download.suse.de/ibs/Devel:/Virt:/Tests/SLE_11_SP4/")
    if vir_opt.status:
        #TODO start, gi_pg_repo will be removed during formal test
        hu_pg_repo = vir_opt.getRepoSource(
                "source.%s.%s" %("hostupdate", vir_opt.prd_ver.lower()))
        #TODO end
        vir_opt._installHost(addon_repo=hu_pg_repo)
        vir_opt.updateHost()
        vir_opt.rebootHost()
        vir_opt.verifyGuest()
        vir_opt.releaseHost()
    vir_opt.writeLog2File()
    LOGGER.info("Product version [%s] finished" %org_prd)
    return vir_opt.getResultList(
                feature_desc=("Target : The host migration test for virtualization."
                              " (Support xen & kvm type virtualization)\n"
                              "\tFunctions:\n"
                              "\t\t1.   Install host server remotely by HAMSTA.\n"
                              "\t\t2.   Install needed packages of virtualizaiton test.\n"
                              "\t\t2-1. Switch xen/kvm kernel\n"
                              "\t\t3.   Install guests in parallel on host server.\n"
                              "\t\t4.   Update host server.\n"
                              "\t\t5.   Verify the availability of guest."),
                prefix_name="Host-Migration Host")


class ParseCMDParam(optparse.OptionParser):
    """Class which parses command parameters
    """

    def __init__(self):
        optparse.OptionParser.__init__(
            self, 
            usage='Usage: %prog [options]',
            epilog="NOTE: Only one kind of test at once is supported.")

        self.add_option("-t", "--test-type", action="store", type="string",
                        dest="test_type",
                        help=("Set test type, gi|hu|gm is available"))
        self.add_option("-r", "--repository", action="store", type="string",
                        dest="repo",
                        help=("Set path of repositroy for installing virtualization"))
        #Guest installing test parameters 
        group = optparse.OptionGroup(
            self,
            "Prj1:Guest Installing",
            "Execute test of guest installing on virtualization")

        self.add_option_group(group)
        group.add_option("--gi-host", action="store", type="string",
                        dest="gi_host_list",
                        help=("Set one or multiple hosts to run "
                              "guest installing case with distributed"))
        group.add_option("--host-product", action="store", type="string",
                        dest="gi_product_list",
                        help=("Specify one or more product verion to be ran"))

        #Host upgrade and vm-guest verfication test parameters
        group = optparse.OptionGroup(
            self,
            "Prj2:Host Upgrade",
            "Execute test for host upgrade and vm-guest verfication on virtualization")

        self.add_option_group(group)
        group.add_option("--hu-host", action="store", type="string",
                        dest="hu_host_list",
                        help=("Set one or multiple hosts to run "
                              "host upgrade case with distributed"))
        group.add_option("--org-product", action="store", type="string",
                        dest="org_product_list",
                        help=("Set orginal product version"))
        group.add_option("--upg-product", action="store", type="string",
                        dest="upg_product_list",
                        help=("Set upgraded product version"))
        '''
        #Guest migration test parameters
        group = optparse.OptionGroup(
            self,
            "Prj3:Guest Migration",
            "Execute test for guest migration on virtualization")

        self.add_option_group(group)
        group.add_option("--org-host", action="store", type="string",
                        dest="org_host_list",
                        help=("Set orginal host addr"))
        group.add_option("--dest-host", action="store", type="string",
                        dest="dest_host_list",
                        help=("Set destination host addr"))
        group.add_option("-p", "--product", action="store", type="string",
                        dest="product_list",
                        help=("Set product version"))

        '''
        #Guest migration test parameters
        LOGGER.debug("Params : " + str(sys.argv))


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
        #LOGGER.info("Json file :\n\%s" %json_data)

        file_path = os.path.join(os.getenv("WORKSPACE",
                                           os.getcwd()),
                                           'result.json')
        if os.path.exists(file_path):
            os.remove(file_path)
        with open(file_path, "w+") as f:
            f.write(json_data)
        os.chmod(file_path, 0777)
        
        print file_path

    def genJsonData(self, json_data):
        '''Convert list data into json format data
        '''
        josn_str = json.dumps(json_data, sort_keys = True, indent = 4, )
        return josn_str

    def getJsonData(self):
        '''Return json data
        '''
        tmp_json_rel = []
        for fet in self.result:
            tmp_json_rel.append(
                self.getFeatureData(name=(fet["feature_prefix_name"] +
                                    fet["feature_prj_name"]),
                                    uri=fet["feature_prj_name"],
                                    desc=fet["feature_desc"],
                                    sen_info=fet["scenario_info"]))
        
        return self.genJsonData(tmp_json_rel)

    def getFeatureData(self, name, uri, desc, sen_info, keyword="Feature"):
        '''Generate feature section data
        '''
        tf_map = {}
        tf_map["keyword"] = keyword
        tf_map["name"] = name
        tf_map["uri"] = uri
        tf_map["description"] = desc
        tc_element = []
        scenario_info = sen_info
        
        for scn in scenario_info:
            if 'doc_str_flag' in scn:
                doc_str_flag = scn["doc_str_flag"]
            else:
                doc_str_flag = False
            sen_duration = (time.mktime(
                datetime.datetime.timetuple(scn["end_time"])) - 
                            time.mktime(
                datetime.datetime.timetuple(scn["start_time"])))
            tc_element.append(self.getScenarioData(
                                name=scn["scenario_name"],
                                step_info=scn["step_info"],
                                hamsta_output=scn["hamsta_output"],
                                qadb_url=scn["scenario_qadb_url"],
                                sen_status=scn["scenario_status"],
                                sen_duration=sen_duration,
                                doc_str_flag=doc_str_flag))
        
        tf_map["elements"] = tc_element

        return tf_map

    def getScenarioData(self, name, step_info, hamsta_output, qadb_url, sen_status, 
                        sen_duration, doc_str_flag=False, sen_type="Sce_T", keyword="Scenario"):
        '''Generate scenario section data
        '''
        ts_map = {}
        tc_step = []
        ts_map["keyword"] = keyword
        ts_map["type"] = sen_type
        if qadb_url:
            ts_map["name"] =  (name + "<a href=%s>QADB URL</a>"
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
                error_msg = hamsta_output
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

        if doc_str_flag:
            tc_step_doc = {}
            tc_step_doc["value"] = step_stdout_msg
            tc_step_map["doc_string"] = tc_step_doc

        tc_step_result = {}
        tc_step_result["status"] = step_status.lower()
        if tc_step_result["status"] != "passed":
            tc_step_result["error_message"] = step_error_msg
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
            if len(ip_address.split(".")) == 4 and re.search(ip_address.strip(),
                                                             output, re.I):
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
        #LOGGER.debug(("Write log to file , params :[task=%s,returncode=%d,"
        #              "logname=%s,host=%s,content=%s]" %(task, returncode,
        #                                                 logname, host, content)))
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
        self.result = []
        self.all_result = []
        self.prj_status = dict(status=True, info="")
        self.queue = multiprocessing.Manager().Queue()
        #self.logpath = AllStaticFuncs.getBuildPath()
        #LOGGER.debug("Get build log path :%s" % self.logpath)
    
        self.test_type = options.test_type    
        if self.test_type == "gi":
            #Guest installation test
            self.host_list = AllStaticFuncs.getAvailHost(options.gi_host_list.split(","))
            self.task_list = options.gi_product_list.strip().split(",")
            self._guestInstall()
        elif self.test_type == "hu":
            #Host migration test
            self.host_list = AllStaticFuncs.getAvailHost(options.hu_host_list.split(","))
            self.org_prd_list = options.org_product_list.strip().split(",")
            self.upg_prd_list = options.upg_product_list.strip().split(",")
            self._hostMigrate()


    def _guestInstall(self):
        #Pool size is defined through host number.
        if self.host_list:
            self.pool = multiprocessing.Pool(processes=len(self.host_list))
            LOGGER.debug("Create process pool[%d]" %len(self.host_list))
            self.initialQueue()
            self._giMultipleTask()
            self.closeAndJoinPool()
        else:
            self.prj_status["status"]= False
            self.prj_status["info"] = "There is no available host"

    def _giMultipleTask(self):
        """Execute multiple taskes in processes pool only for guest installing
        """
        for task in self.task_list:
            #installGuest(task, self.queue)
            self.result.append([task,
                                self.pool.apply_async(
                                    installGuest,
                                    (task, self.queue)
                                    )])

    def _hostMigrate(self):
        #Pool size is defined through host number.
        if self.host_list:
            self.pool = multiprocessing.Pool(processes=len(self.host_list))
            LOGGER.debug("Create process pool[%d]" %len(self.host_list))
            self.initialQueue()
            self._huMultipleTask()
            self.closeAndJoinPool()
        else:
            self.prj_status["status"]= False
            self.prj_status["info"] = "There is no available host"

    def _huMultipleTask(self):
        """Execute multiple taskes in processes pool only for guest installing
        """
        for org_prd, dest_prd in zip(self.org_prd_list, self.upg_prd_list):
            #migrateHost(org_prd, dest_prd, self.queue)
            self.result.append([org_prd,
                                self.pool.apply_async(
                                    migrateHost,
                                    (org_prd, dest_prd, self.queue)
                                    )])
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
    def __init__(self, log_file):
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(filename)s[line:%(lineno)d] [%(process)d] %(levelname)-6s | %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            filename=log_file,
                            filemode='w')

        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(process)d]: %(levelname)-8s %(message)s')
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
#DEBUG = True
LOGGER = LoggerHandling(os.path.join(AllStaticFuncs.getBuildPath(), "sys.log"))

if __name__ == "__main__":
    main()

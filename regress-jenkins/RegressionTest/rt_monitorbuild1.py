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
  Description: Execute stree validation test on host machine
"""

from  pylib.constantvars import *
from  pylib import StringColor as StringClor
from  pylib import CMDParamParser as ParseParam
from  pylib import RegConfigParser as ParseConfig
from  pylib import URLParser, HostContorller

from ast import literal_eval

class RTBuildChange(object):
    def __init__(self, config_file, options):
        
        pc = ParseConfig()
        self.hosts = pc.getItem(config_file, options.mbuild_prj, 'host')

        self.larch = literal_eval(pc.getItem(config_file, options.mbuild_prj, 'larch'))
        self.lrepo = options.mbuild_lrepo
        self.rarch = literal_eval(pc.getItem(config_file, options.mbuild_prj, 'rarch'))
        self.rrepo = options.mbuild_mrepo
        
        self.prj_cfg_path = RT_PRJ_CONFIG_PATH

        self.repo_store_path = PrjPath().createFolder(os.path.join(self.prj_cfg_path, 'rt_repo'))
        self.host_status_file = HOST_STATUS_FILE
        self.rdy_tirgger_job_file = os.path.join(self.prj_cfg_path, RT_RDY_TRIGGER_JOB_FILE)

        self.prefix_jenkins_job = options.mbuild_jjob
        self.jenkins_job = "%(prefix_jj)s/%(arch)s/job/02_InstallHost/buildWithParameters?REPOSITORY=%(repo)s&ARCH=%(arch)s&BUILD_VER=%(build_ver)s"
        
        self.triggered_arch = ""
        self.return_code = 1
        
        self.urlpaser = URLParser()
        self.flowctrller = HostContorller()
        #self.loopCheckBuildChange(self.larch)

    def loopCheckBuildChange(self, arch_list):
        
        cmd_triggerjob_map = CommonOpt().loadData(self.rdy_tirgger_job_file) or {}

        for arch in arch_list:
            trigger_job_cmd = ""
            LOGGER.info( "arch %s" %arch)
            LOGGER.info(arch_list)
            if arch in self.larch:
                repo = self.lrepo
            else:
                repo = self.rrepo

            bc = self.getBuildChange(repo, arch)

            if bc[0] is True:
                trigger_job_cmd = self.jenkins_job %dict(prefix_jj=self.prefix_jenkins_job,
                                                         arch=arch,
                                                         repo=repo,
                                                         build_ver=bc[2])

                trigger_job_cmd = "wget -O - -q \"%s\"" %trigger_job_cmd

            elif bc[0] is False:
                if arch in cmd_triggerjob_map and cmd_triggerjob_map[arch]:
                    trigger_job_cmd = cmd_triggerjob_map[arch]
                else:
                    trigger_job_cmd = ""
            
            if trigger_job_cmd:
                fh = self.flowctrller.markHostStatus(host_list, self.host_status_file,
                                                     org_status=HostContorller.HOST_FREE,
                                                     cur_status=HostContorller.HOST_RUNNING)
                if fh:
                    if bc[0] is False:
                        LOGGER.info("No build change, Trigger job for last build change with cmd [%s]" % trigger_job_cmd)
                        cmd_triggerjob_map[arch] = ''
                        CommonOpt().dumpData(self.rdy_tirgger_job_file, cmd_triggerjob_map)
                    else:
                        LOGGER.info("Trigger job with cmd [%s]" % trigger_job_cmd)
                    
                    trigger_job_cmd = trigger_job_cmd + "&MACHINE=%s" %fh
                    self.triggerJob(arch, trigger_job_cmd)
                else:
                    if bc[0] is False:
                        pass
                    else:
                        cmd_triggerjob_map[arch] = trigger_job_cmd
                        CommonOpt().dumpData(self.rdy_tirgger_job_file, cmd_triggerjob_map)
                        LOGGER.info("No free host, store data [%s] for arch %s" %(trigger_job_cmd,arch))
            else:
                LOGGER.info("No build change")
            LOGGER.info("-"*50)   


    def triggerJob(self, arch, cmd):
        self.triggered_arch = self.triggered_arch and  self.triggered_arch + ',%s' %arch or arch
        self.return_code = 0
        pass
        #os.system(cmd)

    def combineParamForTrigger(self):
        pass

    def getArchDefHost(self, arch):
        for archost in self.hosts.strip(",").split("," + os.linesep):
            if arch in archost:
                return literal_eval(archost.split(":")[-1])

    def getBuildChange(self, repo, arch):
        url = os.path.join(repo, arch, "DVD1", 'media.1', 'build')
        abs_last_file = os.path.join(self.repo_store_path, "last_repo_file_on_%s" %arch)

        return self.checkBuildChange(abs_last_file, url)
    
    def checkBuildChange(self, last_file, url):

        last_content = CommonOpt().loadData(last_file)
        curr_content = self.urlpaser.getFileContent(url)
        
        if ''.join(last_content).strip() == curr_content.strip():
            return (False, last_content, curr_content)
        else:
            CommonOpt().dumpData(last_file, curr_content)
            return (True, last_content, curr_content)


def main():
    
    ins_parseparam = ParseParam().parseMonitorParam()
    options, _args = ins_parseparam.parse_args()
    
    abs_file_path = os.path.abspath(os.path.dirname(sys.argv[0]))
    abs_cfg_file = os.path.join(abs_file_path, RT_REF_TEST_CFG_FILE)

    if os.path.exists(abs_cfg_file):
        rtbc = RTBuildChange(abs_cfg_file, options)
        rtbc.loopCheckBuildChange(rtbc.larch)
        rtbc.loopCheckBuildChange(rtbc.rarch)
        sys.exit(rtbc.return_code)
    else:
        LOGGER.error("Config file does not exist.")
        sys.exit(-1)


if __name__ == '__main__':
    main()


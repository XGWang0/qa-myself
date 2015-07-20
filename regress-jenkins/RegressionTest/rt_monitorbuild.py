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
  Description: This script is used to monitor repo change and trigger remote jenkins job to do test
"""

from  pylib.constantvars import *
from  pylib import StringColor as StringClor
from  pylib import CMDParamParser as ParseParam
from  pylib import RegConfigParser as ParseConfig
from  pylib import URLParser, HostContorller
from  pylib import JenkinsAPI


class RTBuildChange(object):
    def __init__(self, options):
        
        pc = ParseConfig()
        
        # Get project project name, host list, archs repo and so on
        self.prj_name = options.mbuild_prj.upper()
        self.hosts = pc.convertItem(pc.getItem(RT_REF_TEST_CFG_FILE, self.prj_name, 'host'))

        self.lrepo = options.mbuild_lrepo
        self.larch = pc.convertItem(pc.getItem(RT_REF_TEST_CFG_FILE, self.prj_name, 'larch'))

        self.rrepo = options.mbuild_mrepo
        self.rarch = pc.convertItem(pc.getItem(RT_REF_TEST_CFG_FILE, self.prj_name, 'rarch'))

        # Get folder contains all relevant files
        self.prj_cfg_path = RT_PRJ_CONFIG_PATH

        self.repo_store_path = PrjPath().createFolder(
                                os.path.join(self.prj_cfg_path, 'rt_repo', self.prj_name))
        self.host_status_file = HOST_STATUS_FILE
        self.rdy_tirgger_job_file = os.path.join(self.prj_cfg_path, RT_RDY_TRIGGER_JOB_FILE)

        # Initial jenkins jobs and triggered cmd
        self.prefix_jenkins_job = options.mbuild_jjob
        self.jenkins_job = [self.prefix_jenkins_job + "/%(arch)s/job/02_InstallHost", self.prefix_jenkins_job + "/%(arch)s/job/03_StressValidation"]
        self.jenkins_job_with_param = [self.jenkins_job[0] + "/buildWithParameters?REPOSITORY=%(repo)s&ARCH=%(arch)s&BUILD_VER=%(build_ver)s&MACHINE=",
                                       self.jenkins_job[1] + "/buildWithParameters?ARCH=%(arch)s&BUILD_VER=%(build_ver)s&MACHINE="]
        
        self.triggered_arch = ""
        self.return_code = 1
        
        # Instance for url operation and host controller
        self.urlpaser = URLParser()
        self.flowctrller = HostContorller()
        self.loopCheckBuildChange(self.larch)

    def loopCheckBuildChange(self, arch_list):
        '''Traverse needed arches and mode for build change
        '''
        for arch in filter(lambda x:x in self.hosts, arch_list):
                
            trigger_job_cmd = ""

            if arch in self.larch:
                repo = self.lrepo 
            else:
                repo = self.rrepo
            
            abs_repo = os.path.join(repo, arch, "DVD1", 'media.1', 'build')
            # Get stored data from local file
            cmd_triggerjob_map = CommonOpt().loadData(self.rdy_tirgger_job_file) or {}
            key_name_tirgger_job = '%s_%s' %(self.prj_name, arch)

            # Get build change information
            file_stored_last_build_chg = os.path.join(self.repo_store_path, "last_repo_file_on_%s" %arch)
            bc = self.checkBuildChange(file_stored_last_build_chg, abs_repo)

            LOGGER.info(bc)
            #bc = (True, 'kernel-default-24983947dffdsf.rpm', '>kernel-default-24983947dffdsf.rpm<')
            LOGGER.info("Current arch is  %s" %(arch))
            build_version = bc[2]

            # Check jenkins job if is enable
            enable_job_name = self.getEnableJenkinsJob(arch, build_version, repo)

            # If build change is existent, followint operation will be done
            if bc[0] is True:

                LOGGER.info("BC:Detect build change")
                if  enable_job_name:
                    trigger_job_cmd = "wget -O - -q \"%s" %enable_job_name
                    cmd_triggerjob_map[key_name_tirgger_job] = ""
                else:
                    LOGGER.info(StringClor().printColorString(
                                "There is no enable job for build change triggering",
                                StringClor.F_GRE))
                    cmd_triggerjob_map[key_name_tirgger_job] = enable_job_name
                
                #Dump data to local file which it's convenients for next trigger
                CommonOpt().dumpData(self.rdy_tirgger_job_file, cmd_triggerjob_map)
            
            # BUild change is non-existent
            elif bc[0] is False:
                LOGGER.info("NBC: NO build change")
                if enable_job_name:
                    # If last build change is existent, the job should be tiggered
                    if key_name_tirgger_job in cmd_triggerjob_map and cmd_triggerjob_map[key_name_tirgger_job]:
                        LOGGER.info(StringClor().printColorString(
                                    "No build change, Try to tirgger last build change with job cmd : %s" %trigger_job_cmd,
                                    StringClor.F_GRE))

                        trigger_job_cmd = cmd_triggerjob_map[key_name_tirgger_job]

                        cmd_triggerjob_map[key_name_tirgger_job]=""
                        CommonOpt().dumpData(self.rdy_tirgger_job_file, cmd_triggerjob_map)
                    else:
                        LOGGER.info(StringClor().printColorString(
                                    "No build change or last build change needs to be triggered",
                                    StringClor.F_GRE))
                        
                else:
                    LOGGER.info(StringClor().printColorString('No enable job to be triggered',
                                StringClor.F_GRE))

            self.triggerJob(arch, trigger_job_cmd, cmd_triggerjob_map, file_stored_last_build_chg, bc)
            LOGGER.info("-"*80 + '\n'*2)   

    def getEnableJenkinsJob(self, arch, build_ver, install_repo):
        ''' Return enable jobs with parameters
        '''
        for (i, job) in enumerate(self.jenkins_job):
            if JenkinsAPI().checkBuildable(job %dict(arch=arch)) is True:
                break
        else:
            LOGGER.warn("There is not enable job can be triggered")
            return ""
        
        install_repo = os.path.join(install_repo, arch, 'dvd1')
        if i == 0:
            return self.jenkins_job_with_param[i] %dict(arch=arch,
                                                        #repo=self.repo,
                                                        build_ver=build_ver,
                                                        repo=install_repo)
        else:
            return self.jenkins_job_with_param[i] %dict(arch=arch,
                                                        build_ver=build_ver)

    def triggerJob(self, arch, cmd, reloaded_data, build_chg_last_bc, bc):
        key_name_tirgger_job = '%s_%s' %(self.prj_name, arch)
        if cmd:
            fh = self.flowctrller.markHostStatus(self.hosts[arch], self.host_status_file,
                                                 org_status=HostContorller.HOST_FREE,
                                                 cur_status=HostContorller.HOST_RUNNING)
            if fh:
                LOGGER.info("Get available host : %s" %fh)

                self.return_code = 0
                cmd = cmd + fh + "\""

                LOGGER.info("Trigger job %s" %cmd)
                os.system(cmd)
            else:
                LOGGER.info("NO available host %s for triggering, dump data to file" %str(self.hosts[arch]))
                reloaded_data[key_name_tirgger_job]=cmd
                CommonOpt().dumpData(self.rdy_tirgger_job_file, reloaded_data)
            
            CommonOpt().dumpData(build_chg_last_bc, bc[2])
            self.return_code = 0
        else:
            pass

        self.triggered_arch = self.triggered_arch and  self.triggered_arch + ',%s' %arch or arch


    def getBuildVersion(self, build_output, mode='default'):
        rei =  re.search('>%s-(\S+?).rpm<' %'kernel-%s' %mode, build_output, re.I)
        if rei:
            return  rei.groups()[0].strip()
        return "Not-match-build-version-%s" %(time.time())
    
    def checkBuildChange(self, last_file, url):

        last_content = CommonOpt().loadData(last_file)
        curr_content = self.urlpaser.getFileContent(url).strip()

        if ''.join(curr_content.strip()) == "":
            return (False, last_content, "")
        else:
            if ''.join(last_content).strip() == curr_content.strip():
                return (False, last_content, curr_content)
            else:
                #CommonOpt().dumpData(last_file, curr_content)
                return (True, last_content, curr_content)


def main():
    
    # Get parameters from cmd
    ins_parseparam = ParseParam().parseMonitorParam()
    options, _args = ins_parseparam.parse_args()
    
    # Get config file of kotd project
    if os.path.exists(RT_REF_TEST_CFG_FILE):
        rtbc = RTBuildChange(options)
        sys.exit(rtbc.return_code)
    else:
        LOGGER.error("Config file does not exist.")
        sys.exit(-1)


if __name__ == '__main__':
    main()


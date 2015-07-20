# ****************************************************************************
# Copyright (c) 2013 Unpublished Work of SUSE. All Rights Reserved.
# 
# THIS IS AN UNPUBLISHED WORK OF SUSE.  IT CONTAINS SUSE'S
# CONFIDENTIAL, PROPRIETARY, AND TRADE SECRET INFORMATION.  SUSE
# RESTRICTS THIS WORK TO SUSE EMPLOYEES WHO NEED THE WORK TO PERFORM
# THEIR ASSIGNMENTS AND TO THIRD PARTIES AUTHORIZED BY SUSE IN WRITING.
# THIS WORK IS SUBJECT TO U.S. AND INTERNATIONAL COPYRIGHT LAWS AND
# TREATIES. IT MAY NOT BE USED, COPIED, DISTRIBUTED, DISCLOSED, ADAPTED,
# PERFORMED, DISPLAYED, COLLECTED, COMPILED, OR LINKED WITHOUT SUSE'S
# PRIOR WRITTEN CONSENT. USE OR EXPLOITATION OF THIS WORK WITHOUT
# AUTHORIZATION COULD SUBJECT THE PERPETRATOR TO CRIMINAL AND  CIVIL
# LIABILITY.
# 
# SUSE PROVIDES THE WORK 'AS IS,' WITHOUT ANY EXPRESS OR IMPLIED
# WARRANTY, INCLUDING WITHOUT THE IMPLIED WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. SUSE, THE
# AUTHORS OF THE WORK, AND THE OWNERS OF COPYRIGHT IN THE WORK ARE NOT
# LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION
# WITH THE WORK OR THE USE OR OTHER DEALINGS IN THE WORK.
# ****************************************************************************

import re
import fcntl

from constantvars import *

class HostContorller(object):

    HOST_READY = 'READY'
    HOST_FREE = 'FREE'
    HOST_RUNNING = 'RUNNING'
    HOST_RUNNING_RH = 'RUNNING RH'
    HOST_RUNNING_SK = 'RUNNING SK'
    HOST_RUNNING_SV = 'RUNNING SV'
    HOST_RUNNING_US = 'RUNNING US'

    def __init__(self):
        pass

    def reserveFile(self, fp, timeout=100):
        curr_time = time.time()
        while time.time() - curr_time < 100:
            try:
                fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError, e:
                LOGGER.warn(e)
                return False
            else:
                return True
        
        LOGGER.error("Failed to get file lock of file %s" %fp.filename)
        return False
    
    def releaseFile(self, fp):
        try:
            fcntl.flock(fp, fcntl.LOCK_UN)
        except Exception,e:
            print e
            return False
        else:
            return True

    #TODO Maybe exist blocking issue
    def markHostStatus(self, choice_host, host_status_file,
                       org_status=HOST_FREE, cur_status=HOST_READY):

        acquired_host_flag = False
        try:
            fp = open(host_status_file, "a+")
        except IOError,e:
            LOGGER.error("Failed to open file becuase of %s" %e)
            return ""

        if self.reserveFile(fp) is False:
            LOGGER.info()
            return ""
        
        lines = fp.readlines()
        for host in choice_host:
            if filter(lambda x:re.search("%s\s+%s" %(host, org_status), x), lines):
                self.modifyHostStatus(fp, lines, host, cur_status)
                acquired_host_flag = True
                break

        self.releaseFile(fp)
        fp.close()
        if acquired_host_flag is True:
            return host
        else:
            return ""

    def modifyHostStatus(self, fp, file_lines, host, status=HOST_READY):
        
        l_num = 0
        l_str = ""
        lines = file_lines

        if not filter(lambda x:host in x, lines):
            lines.append("\n%s %s" %(host, status))
        else:
            for l_num, l_str in enumerate(lines):
                if host in l_str:
                    lines[l_num] = "%s %s\n" %(host, status)
                    break
        LOGGER.info(("ALL LINES is ", lines))
        fp.seek(0)
        fp.truncate()
        fp.writelines(lines)
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
from virt_repo_monitor_devel import *

class MSRepoMontior(RepoMontior):
    
    def __init__(self):
        pass

    def getRepoAdress(self, product):
        '''repotype scope : virttest or virtdevel
        '''
        get_source_api = '/usr/share/qa/virtautolib/lib/get-source.sh'
        
        if os.path.exists(get_source_api):
            product = product.strip().lower()
            get_repo_cmd = '%s -p source.virtupdate.milestone.%s' %(get_source_api, product)


            return_code, result_buf = runCMDBlocked(get_repo_cmd)
            if return_code != 0:
                LOGGER.error('Failed to get %s repository, due to [%s]' %(product, result_buf))
                return ""
            else:
                repo_address = result_buf.strip()
                LOGGER.info('%s repository address is [%s]' %(product, repo_address))
                return repo_address
        else:
            LOGGER.error("Can not get source api [%s] on local host" %get_source_api)
            sys.exit(-1)

    def _getRepoData(self, url):
        xml_content = URLParser().getFileContent(url)
        
        if xml_content:
            l1 = re.findall("=\"(\S+-Server-POOL-x86_64-Build\d+-Media1).*(\d{2}-\S+-\d{4}\s+\d{2}:\d{2})\s+-", xml_content)
            if l1:
                l2 = list(set(l1))
                l2 = sorted(l2, key=l1.index)
                l2 = sorted(l2, key=lambda x:time.mktime(time.strptime(x[1],'%d-%b-%Y %H:%M')), reverse=True)
                return l2[0][0].strip()
            else:
                LOGGER.warn("Not grab build info")
                return None
        else:
            LOGGER.warn("Not get content of url [%s]" %url)
            return None

    def compareRepoChange(self, product, last_repo_file, current_content):

        last_repo_cont = ''
        curr_repo_cont = current_content
        product = product.upper()
        cmp_status = False
        chg_prd = ''

        if curr_repo_cont is None:
            LOGGER.warn("Not grab build version , skip comparison of version")
            return (False, chg_prd)

        LOGGER.debug("last saved repo file is %s" %last_repo_file)
        if os.path.exists(last_repo_file):
            with open(last_repo_file, 'r') as f:
                last_repo_cont = f.read().strip()

            LOGGER.info("Build version org:%s VS cur:%s" %(last_repo_cont, current_content))
            if last_repo_cont != current_content:
                chg_prd = '%s.KVM,%s.XEN' %(product, product)
                LOGGER.info("Build version is changed, trigger xen and kvm test")
                cmp_status = True
            else:
                LOGGER.info("No changed !")
            LOGGER.debug("cmp_status is %s" %str(cmp_status))
            return (cmp_status, chg_prd)
            
        else:
            LOGGER.info("No last repo content, trigger xen and kvm test")
            chg_prd = '%s.KVM,%s.XEN' %(product, product)
            cmp_status = True
            return (cmp_status, chg_prd)

            
class MSPorjectMonitor(PorjectMonitor):

    def __init__(self, options, rm):
        super(MSPorjectMonitor, self).__init__(options, rm)

        
    def getFmtOfParamData(self, project, ):
        if project == 'GI':
            param_data = {'VIRT_PRODUCT_VERSION':None,
                          'HOST_LIST':None,
                          'HOST_PRODUCT':None}
        elif project == 'HU':
            param_data = {'VIRT_PRODUCT_VERSION':None,
                          'HOST_LIST':None,
                          'TEST_MODE':'std'}
        elif project == 'GM':
            param_data = {'VIRT_PRODUCT_VERSION':None,
                          'ORG_PRODUCT':None,
                          'HOST_LIST':None,
                          'TEST_MODE':None}
        
        return param_data

    def updatePrjData(self, projectanme, verinfo, prdinfo):
        prdinfo = prdinfo.upper()
        for i in self.project_data:
            if i['name'] == projectanme:
                i['status'] |= True
                if i['paramet']['VIRT_PRODUCT_VERSION']:
                    if verinfo in  i['paramet']['VIRT_PRODUCT_VERSION']:
                        pass
                    else:
                        i['paramet']['VIRT_PRODUCT_VERSION'] += ',' + verinfo
                else:
                    i['paramet']['VIRT_PRODUCT_VERSION'] = verinfo

                if projectanme == 'GI':
                    if i['paramet']['HOST_PRODUCT']:
                        if prdinfo in i['paramet']['HOST_PRODUCT']:
                            pass
                        else:
                            i['paramet']['HOST_PRODUCT'] += ',' + prdinfo
                    else:
                         i['paramet']['HOST_PRODUCT'] = prdinfo
                elif projectanme == 'GM':
                    if i['paramet']['ORG_PRODUCT']:
                            if prdinfo in i['paramet']['ORG_PRODUCT']:
                                pass
                            else:
                                i['paramet']['ORG_PRODUCT'] += ',' + prdinfo
                    else:
                        i['paramet']['ORG_PRODUCT'] = prdinfo

    def getRepoChange(self):
        LOGGER.info('')
        LOGGER.info(' Get Repository Info '.center(90,'='))
        for c,i in enumerate(self.all_prd_list):
            if c != 0:
                LOGGER.info('')
            LOGGER.info("[%d] Monitor %s repository change" %(c+1,i))
            tmp_repo_cont = tmp_repo_ver = ''
            # Get virtual devel repository and file list content
            repo_url = self.rm.getRepoAdress(i)
            # Get version information of virtual devel repository
            tmp_repo_cont = tmp_repo_ver = self.rm._getRepoData(repo_url)

            LOGGER.debug(tmp_repo_cont)
            LOGGER.debug(i)
            LOGGER.debug(self.project_data)
            # Package content of last time 
            for j,p in enumerate(filter(lambda x: i in x['prdlist'], self.project_data)):
                if j != 0:
                    LOGGER.info('')
                LOGGER.info('[%d.%d] Deal with data for project [%s] and product [%s]' %(c+1,j+1,i,p['name']))
                last_repo_file = self.getRepoDataOuputFile(p['name'], i, 'last')
                curr_repo_file = self.getRepoDataOuputFile(p['name'], i, 'curr')
                # Comparer package content of last time with current package content and
                # detect which package is changed
                rel = self.rm.compareRepoChange(i, last_repo_file, tmp_repo_cont)
                self.rm.replaceLastRepo(curr_repo_file, tmp_repo_cont)
                if rel[0] is True:
                    p['chkprd'].append((last_repo_file, curr_repo_file))
                    for prd in self._getAllPrdInfoForHU(p['name'], rel[1]):
                        self.updatePrjData(p['name'], tmp_repo_ver, prd)
                    p['status'] = True

def main():
    LOGGER.info(' START '.center(90,"="))
    param_opt = ParseCMDParam()
    options, _args = param_opt.parse_args()

    rm = MSRepoMontior()
    dp = MSPorjectMonitor(options, rm)
    dp.cleanEnv()
    dp.checkTrigJob()
    dp.getRepoChange()

    LOGGER.debug(dp.project_data)

    dp.allocateHost()
    dp.dumpParamData2File()
    dp.updateLastRepoData()
    LOGGER.info(' END '.center(90,"="))
    return dp.status is False and 1 or 0


if __name__ == '__main__':
    w = main()
    LOGGER.info(w)
    sys.exit(w)


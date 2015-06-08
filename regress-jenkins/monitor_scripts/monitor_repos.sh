#!/bin/bash

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


#-------------------------------------------------------------------------------
# Global variables
#-------------------------------------------------------------------------------

ARCH_LIST="i386 ia64 x86_64"
BASIC_REPO=http://147.2.207.1/dist/install/SLP/SLES-11-SP4-LATEST

RETURN_CODE=1
if [ -z "${WORKSPACE}" ];then
	CURRPATH=./
else
	CURRPATH=${WORKSPACE}
fi

#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  download_filelist
#   DESCRIPTION: Download changlog file from repository
#    PARAMETERS:  1:Repo name
#		  2:Redirection file name
#       RETURNS:  0:passed
#		  1:failed
#-------------------------------------------------------------------------------

download_filelist() {
  REPO=$1
  LOGFILE=$2
  RET=0
  pwd
  readlink -f $LOGFILE
  if (wget -q -O $LOGFILE ${REPO}/media.1/build); then
    RET=0
  else
    RET=1
  fi
  return $RET
}

#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  trigger_Jenkins
#   DESCRIPTION:  Trigger remote jenkins to execute job
#    PARAMETERS:  1:Architecture
#		  2:Repository address
#       RETURNS:  
#-------------------------------------------------------------------------------

trigger_Jenkins() {
    ARCH=$1
    REPO=$2
    BUILD_NUM=$3   
    lowerarch=`echo ${ARCH} | tr [[:upper:]] [[:lower:]]` 
    echo "$JENKINS_URL/job/REGRESSIONTEST/job/SLES-11-SP4/job/${ARCH}/job/02_InstallHost/buildWithParameters?REPOSITORY=$2&ARCH=${lowerarch}"
    wget -O - -q  "$JENKINS_URL/job/REGRESSIONTEST/job/SLES-11-SP4/job/${ARCH}/job/02_InstallHost/buildWithParameters?REPOSITORY=$2&ARCH=${lowerarch}&BUILD_VER=${BUILD_NUM}" > /dev/null
    RETURN_CODE=0
}

print_full_usage()
{
        echo "Purpose: This program will monitor repository of sles product, it will trigger reomote jenkins job once found any change"
        echo
        echo "Usage: $0 --help -h -help | <repoistory> [log path]"
        echo
        echo "Man: "
        echo
        echo " -h,-help,--help"
        echo "        - Prints the full usage"
        echo 
        echo " <repoistory>"
        echo "        - repoistory address"
        echo "        - EXAMPLE: http://147.2.207.1/dist/install/SLP/SLES-11-SP4-LATEST"
        echo 
        echo " [log path]"
        echo "        - log path"
	echo "        - default : current path; jenkins workspace if running on jenkins"
        echo "        - EXAMPLE: ./"
        echo 
        echo "Examples:"
        echo "        $0 http://147.2.207.1/dist/install/SLP/SLES-11-SP4-LATEST"
        popd > /dev/null; exit 1

}       # ----------  end of function print_full_usage  ----------

#-------------------------------------------------------------------------------
#	Main Enterance 
#-------------------------------------------------------------------------------


if [ $# -eq 1 ]
then
        if [ "${1}" == "--help" ] || [ "${1}" == "-help" ] || [ "${1}" == "-h" ]
        then
                print_full_usage
                popd > /dev/null; exit 1
	else
		BASIC_REPO=$1
        fi
elif [ $# -ne 1 -a $# -ne 2 ];then
        print_full_usage
        popd > /dev/null; exit 1
elif [ $# -eq 2 ];then
	BASIC_REPO=$1
	CURRPATH=$2
fi

for ARCH in $ARCH_LIST; do
    REL_REPO=${BASIC_REPO}/${ARCH}/DVD1/
      if ! [ -e "${CURRPATH}/repo_info" ];then
          mkdir repo_info
      fi

      REPO_CURR=${CURRPATH}/repo_info/repo_curr_build_${ARCH}
      REPO_LAST=${CURRPATH}/repo_info/repo_last_build_${ARCH}

    # Download changelog of repo
    echo "[INFO] Retrieving changelog for ${ARCH} on ${BASIC_REPO}"
    download_filelist ${REL_REPO} ${REPO_CURR}
    # compare last to curr
    curr_build_num=`cat ${REPO_CURR} | sed ':^$::g'`
    if [ ! -e "$REPO_LAST" ]; then
      echo "Triggering jenkins job for ${ARCH}: Missing previous cangelog"
      trigger_Jenkins ${ARCH} ${REL_REPO} ${curr_build_num}
    else
      if `diff -i -E -w -B ${REPO_CURR} ${REPO_LAST} > /dev/null` ;then
        echo "There is no any change from last check, do not need to trigger"
      else
	echo "Last build number is `cat ${REPO_LAST}`"
	echo "Curr build number is `cat ${REPO_LAST}`"
        trigger_Jenkins ${ARCH} ${REL_REPO} ${curr_build_num}
      fi
    fi
    cp ${REPO_CURR} ${REPO_LAST}

done
exit $RETURN_CODE

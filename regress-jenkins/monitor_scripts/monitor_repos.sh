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

L_ARCH_LIST="i386 x86_64"
R_ARCH_LIST="ppc64 s390x ia64"

RETURN_CODE=1
if [ -z "${WORKSPACE}" ];then
	CURRPATH=./
else
	CURRPATH=${WORKSPACE}
fi




#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  printOutput
#   DESCRIPTION:  display normal output to console
#    PARAMETERS:  1:message level (N:normal messages;
#                                  E:error messages; W:warning messages)
#                 2:messages
#                 3:return code
#       RETURNS:  parameters 3 value
#-------------------------------------------------------------------------------
printOutput ()
{
        MSG_LEVEL=$1
        MSG_CONT=$2
        RETURN_CODE=$3

        if [ ${MSG_LEVEL} = "E" ]  ; then
                echo "ERROR:${MSG_CONT}"
        elif [ ${MSG_LEVEL} = "W" ]  ; then
                echo "WARN :${MSG_CONT}"
        else
                echo "INFO :${MSG_CONT}"
        fi

        return ${RETURN_CODE}

}       # ----------  end of function printOutput  ----------


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
    JENKINS_PREFIX=$4

    lowerarch=`echo ${ARCH} | tr [[:upper:]] [[:lower:]]` 
    echo
    echo "*----------------------------------------------------------------------------"
    printOutput N  "${JENKINS_PREFIX}/${ARCH}/job/02_InstallHost/buildWithParameters?REPOSITORY=$2&ARCH=${lowerarch}"
    #wget -O - -q  "${JENKINS_PREFIX}/${ARCH}/job/02_InstallHost/buildWithParameters?REPOSITORY=$2&ARCH=${lowerarch}&BUILD_VER=${BUILD_NUM}" > /dev/null
    echo "*----------------------------------------------------------------------------"
    echo
    RETURN_CODE=0
}       # ----------  end of function trigger_Jenkins  ----------

#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  check_repo_change
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#-------------------------------------------------------------------------------

check_repo_change ()
{
	ARCH_LIST=$1
	REPO_PREFIX=$2
	JENKINS_PREFIX=$3

	for ARCH in $ARCH_LIST; do
	    REL_REPO=${REPO_PREFIX}/${ARCH}/DVD1/
	      if ! [ -e "${CURRPATH}/repo_info" ];then
	          mkdir repo_info
	      fi
	
	      REPO_CURR=${CURRPATH}/repo_info/repo_curr_build_${ARCH}
	      REPO_LAST=${CURRPATH}/repo_info/repo_last_build_${ARCH}
	
              if (wget -q --spider ${REL_REPO});then
                :
              else
                REL_REPO=${REL_REPO/DVD1/dvd1}
              fi
  

	    # Download changelog of repo
	    printOutput N "Retrieving changelog for ${ARCH} on ${BASIC_REPO}"
	    download_filelist ${REL_REPO} ${REPO_CURR}
	    # compare last to curr
	    curr_build_num=`cat ${REPO_CURR} | sed ':^$::g'`
	    if [ ! -e "$REPO_LAST" ]; then
	      printOutput N "Triggering jenkins job for ${ARCH}: Missing previous changelog"
	      trigger_Jenkins ${ARCH} ${REL_REPO} "${curr_build_num}" ${JENKINS_PREFIX}
	    else
	      if `diff -i -E -w -B ${REPO_CURR} ${REPO_LAST} > /dev/null` ;then
	        printOutput N "There is no any change from last check, do not need to trigger"
	      else
	        printOutput N "Last build number is `cat ${REPO_LAST}`"
	        printOutput N "Curr build number is `cat ${REPO_LAST}`"
	        trigger_Jenkins ${ARCH} ${REL_REPO} "${curr_build_num}" ${JENKINS_PREFIX}
	      fi
	    fi
	    cp ${REPO_CURR} ${REPO_LAST}
	
	done

	
}	# ----------  end of function check_repo_change  ----------




#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  print_full_usage
#   DESCRIPTION:  Display all help information for help
#    PARAMETERS:  
#       RETURNS:  
#-------------------------------------------------------------------------------

print_full_usage()
{
        echo "Purpose: This program will monitor repository of sles product, it will trigger reomote jenkins job once found any change"
        echo
        echo "Usage: $0 --help -h -help | -L <local repoistory>  -R <remote repository> -j <Jenkins job prefix>"
        echo
        echo "Man: "
        echo
        echo " -h,-help,--help"
        echo "        - Prints the full usage"
        echo 
        echo " -L <local repoistory>"
        echo "        - repoistory address"
        echo "        - EXAMPLE: http://147.2.207.1/dist/install/SLP/SLES-11-SP4-LATEST"
        echo 
        echo " -R <remote repoistory>"
        echo "        - repoistory address"
        echo "        - EXAMPLE: http://dist.ext.suse.de/install/SLP/SLES-11-SP4-LATEST/"
        echo 
        echo " -j <Jenkins job prefix>"
        echo "        - Jenkins job prefix triggered"
        echo "        - EXAMPLE: http://147.2.207.67:8080/job/REGRESSIONTEST/job/SLES-11-SP4/job/"
        echo 
        echo "Examples:"
        echo "        $0 -L http://147.2.207.1/dist/install/SLP/SLES-11-SP4-LATEST -R http://dist.ext.suse.de/install/SLP/SLES-11-SP4-LATEST/ -j http://147.2.207.67:8080/job/REGRESSIONTEST/job/SLES-11-SP4/job/"
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
        fi
elif [ $# -ne 6 ];then
        print_full_usage
        popd > /dev/null; exit 1
fi


while getopts "L:R:j:" OPTIONS; do
  case $OPTIONS in
    L)
      LOCAL_REPO=$OPTARG
      ;;
    R)
      REMOTE_REPO=$OPTARG
      ;;
    j)
      JENKINS_JOB_PREFIX=$OPTARG
      ;;
    \?)
      printOutput W "Invalid parameters !!" 1
      print_usage; exit 1
      ;;
  esac
done


check_repo_change "$L_ARCH_LIST" ${LOCAL_REPO} $JENKINS_JOB_PREFIX
check_repo_change "$R_ARCH_LIST" ${REMOTE_REPO} $JENKINS_JOB_PREFIX


#for ARCH in $ARCH_LIST; do
#    REL_REPO=${BASIC_REPO}/${ARCH}/DVD1/
#      if ! [ -e "${CURRPATH}/repo_info" ];then
#          mkdir repo_info
#      fi
#
#      REPO_CURR=${CURRPATH}/repo_info/repo_curr_build_${ARCH}
#      REPO_LAST=${CURRPATH}/repo_info/repo_last_build_${ARCH}
#
#    # Download changelog of repo
#    echo "[INFO] Retrieving changelog for ${ARCH} on ${BASIC_REPO}"
#    download_filelist ${REL_REPO} ${REPO_CURR}
#    # compare last to curr
#    curr_build_num=`cat ${REPO_CURR} | sed ':^$::g'`
#    if [ ! -e "$REPO_LAST" ]; then
#      echo "Triggering jenkins job for ${ARCH}: Missing previous cangelog"
#      trigger_Jenkins ${ARCH} ${REL_REPO} ${curr_build_num}
#    else
#      if `diff -i -E -w -B ${REPO_CURR} ${REPO_LAST} > /dev/null` ;then
#        echo "There is no any change from last check, do not need to trigger"
#      else
#	echo "Last build number is `cat ${REPO_LAST}`"
#	echo "Curr build number is `cat ${REPO_LAST}`"
#        trigger_Jenkins ${ARCH} ${REL_REPO} ${curr_build_num}
#      fi
#    fi
#    cp ${REPO_CURR} ${REPO_LAST}
#
#done
exit $RETURN_CODE

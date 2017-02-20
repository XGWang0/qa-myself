#!/bin/bash
#===============================================================================
#
#          FILE:  install_qa_repo_in_guest.sh
# 
#         USAGE:  ./install_qa_repo_in_guest.sh 
# 
#   DESCRIPTION:  
# 
#       OPTIONS:  ---
#  REQUIREMENTS:  ---
#          BUGS:  ---
#         NOTES:  ---
#        AUTHOR:   (), 
#       COMPANY:  
#       VERSION:  1.0
#       CREATED:  02/14/2017 03:27:50 AM EST
#      REVISION:  ---
#===============================================================================

function zypper_opt_strict ()
{
    cmd=$*
    zypper $cmd
    ret=$?
    if [ $ret -ne 0 ];then
       echo "Failed to run zypper $cmd"
       exit 1
    fi
}    # ----------  end of function zypper_opt  ----------

function zypper_opt ()
{
    cmd=$*
    zypper $cmd
    ret=$?
    if [ $ret -ne 0 ];then
       echo "[WARN ]: Failed to run zypper $cmd"
    fi
}    # ----------  end of function zypper_opt  ----------


release=`grep "VERSION" /etc/SuSE-release | sed "s/^.*VERSION = \(.*\)\s*$/\1/"`
spack=`grep "PATCHLEVEL" /etc/SuSE-release | sed "s/^.*PATCHLEVEL = \(.*\)\s*$/\1/"`
if zypper lr -u | grep -iq qa_auto_repo ; then
        zypper rr qa_auto_repo
fi

if [ "$spack" = "0" ];then
        QA_HEAD_REPO="http://dist.nue.suse.com/ibs/QA:/Head/SLE-$release"
else
        QA_HEAD_REPO="http://dist.nue.suse.com/ibs/QA:/Head/SLE-$release-SP${spack}"
fi
QA_HEAD_REPO=${QA_HEAD_REPO%-}

zypper_opt_strict --non-interactive --gpg-auto-import-keys ar ${QA_HEAD_REPO} qa_auto_repo
zypper_opt_strict --non-interactive --gpg-auto-import-keys ref qa_auto_repo
zypper_opt_strict --non-interactive --gpg-auto-import-keys in -l qa_testset_automation 
zypper_opt --non-interactive --gpg-auto-import-keys in -l ca-certificates-suse

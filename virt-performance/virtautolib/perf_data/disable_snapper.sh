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

function zypper_opt ()
{
    cmd=$*
    zypper $cmd
    ret=$?
    if [ $ret -ne 0 ];then
       echo "Failed to run zypper $cmd"
       exit 1
    else
       exit 0
    fi
}    # ----------  end of function zypper_opt  ----------

zypper_opt --non-interactive rm snapper-zypp-plugin
sed -i 's/USE_SNAPPER="yes"/#USE_SNAPPER="yes"/g' /etc/sysconfig/yast2
sed -i '/USE_SNAPPER="yes"/a USE_SNAPPER="no"' /etc/sysconfig/yast2sssss


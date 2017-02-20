#!/bin/bash
#===============================================================================
#
#          FILE:  generate_case_list.sh
# 
#         USAGE:  ./generate_case_list.sh 
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
#       CREATED:  02/15/2017 01:32:54 AM EST
#      REVISION:  ---
#===============================================================================

#===  FUNCTION  ================================================================
#          NAME:  check_run_done
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================


function check_run_done ()
{
     local checked_file=$1
     local timeout=$2
     local interval=3

     if [[ ${checked_file} =~ '/' ]];then
         :
     else
         basefolder="/var/log/qaset"
         checked_file=${basefolder}/${checked_file}
     fi
     echo "[INFO ]: Checking whether file $checked_file is existent or not"
     for ((i=0;i<${timeout};i=i+${interval}))
     do
          if `ls -l ${checked_file} > /dev/null 2>&1`;then
              echo "[INFO ]: File $checked_file is existent now"
              return 0
          fi
          sleep $interval
     done
     echo "[ERROR]: Performance test is still running within ${timeout}s"
     return 1

}    # ----------  end of function create_distro_pair  ----------

check_run_done /var/log/qaset/control/DONE 600

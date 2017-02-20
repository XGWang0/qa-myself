#!/bin/bash
#===============================================================================
#
#          FILE:  vm-perf.sh
# 
#         USAGE:  ./vm-perf.sh 
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
#       CREATED:  02/13/2017 04:18:39 AM EST
#      REVISION:  ---
#===============================================================================

source ./vm-perf-lib.sh

#-------------------------------------------------------------------------------
#   Global variables
#-------------------------------------------------------------------------------
VM_NAME=sles-12-sp2-64-fv-def-net

OIFS=$IFS
IFS='-'
A_DEF=(${VM_NAME})
OS=${A_DEF[0]}
RELEASE=${A_DEF[1]}
PATCH=${A_DEF[2]}
IFS=$OIFS
unset A_DEF

SCRIPT_ROOT_PATH=/usr/share/qa/virtautolib/data/perf_data

function prepare_env ()
{
    #-------------------------------------------------------------------------------
    #   Verify if guest is up or no
    #-------------------------------------------------------------------------------
    #get_ip_address ${VM_NAME} 200
    printInfo "Verify Guest Status" BANNER
    verify_guest_up_via_ssh ${VM_NAME} 20 4 
    
    #-------------------------------------------------------------------------------
    #   Change hostname of guest
    #-------------------------------------------------------------------------------
    printInfo "Change guest HostName" BANNER
    change_guest_hostname "PERF"
    
    #-------------------------------------------------------------------------------
    #   Install repo and relevant packages for performance test
    #-------------------------------------------------------------------------------
    printInfo "Install qa repo within guest" BANNER
    qa_repo_install_script=$SCRIPT_ROOT_PATH/install_qa_repo_in_guest.sh
    run_script_within_guest ${VM_NAME} $qa_repo_install_script "install qa repo within guest"
    
    
    #-------------------------------------------------------------------------------
    #   Disable snapper within guest
    #-------------------------------------------------------------------------------
    printInfo "Disable snapper within guest" BANNER
    disable_snapper_script=$SCRIPT_ROOT_PATH/disable_snapper.sh
    run_script_within_guest ${VM_NAME} $disable_snapper_script "disable snapper within guest"
    
}    # ----------  end of function prepare_env  ----------


#===  FUNCTION  ================================================================
#          NAME:  
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================
function generate_case_list ()
{
    testcase=$1
    times=$2
    printInfo "Create performance test case" INFO

    [ -z "$testcase" ] && testcase=sysbench_sys
    [ -z "$times" ] && times=3
    sed  -e "s/TESTCASE/${testcase}/" -e "s/TIMES/$times/" ${SCRIPT_ROOT_PATH}/generate_case_list.sample > ${SCRIPT_ROOT_PATH}/generate_case_list.sh
    run_script_within_guest ${VM_NAME} ${SCRIPT_ROOT_PATH}/generate_case_list.sh "generate case list within guest"
    if [ $? -ne 0 ];then
        printInfo "Failed to create test plan for performance test" ERROR && exit 1 
    fi
}   # ----------  end of function qaset_run  ----------


function generate_cmp_pair ()
{
    local tp=$1
    local product=$2
    printInfo "Start create comparison pair for performance test" BANNER
    base_product=${OS}-${RELEASE}-${PATCH}
    sed  -e "s/TESTPLAN/${tp}/" -e "s/BASEPROJECT/${base_product}/" ${SCRIPT_ROOT_PATH}/init_perf_test.sample > ${SCRIPT_ROOT_PATH}/init_perf_test.sh
    run_script_within_guest ${VM_NAME} ${SCRIPT_ROOT_PATH}/init_perf_test.sh "create comarsion pair within guest"
    if [ $? -ne 0 ];then
         printInfo "Failed to create comparsion pair for performance test" ERROR && exit 1
    fi
}    # ----------  end of function generate_cmp_pair  ----------


#===  FUNCTION  ================================================================
#          NAME:  
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================
function execute_cmd_within_guest ()
{
    local run_cmd=$*
    [ -z "${run_cmd}" ] && printInfo "Lack of primay parameter which wants to execute." INFO
    for i in `seq 0 3`
    do
        output=`$sshNoPass $vmUser@$vmIP " $run_cmd " 2>&1`
        ret=$?
        if [ $ret -eq 0 ];then
           printInfo "Successfully launch $run_cmd " INFO
           return 0
        else echo "$output" | grep -iq "Permission denied"
           commands=`echo "$output" | sed -n '/ssh-keygen/p'`
           eval $commands
           sleep 3
           rm /root/.ssh/known_hosts
        fi
    done
    printInfo "Failed to launch $run_cmd " ERROR
    exit 2
}    # ----------  end of function execute_perf_run  ----------


function execute_perf_run_all ()
{
    local all_cases=$*
    printInfo "Start to generate and run performance testcase" BANNER
    for case in ${all_cases}
    do
         verify_guest_up_via_ssh ${VM_NAME} 20 4 || exit 2
         printInfo "Start handle case [$case]" BREAKLINE
         generate_case_list $case 
         execute_cmd_within_guest /usr/share/qa/qaset/run/performance-run.upload_Beijing 
         trace_cmd_run /var/log/qaset/control/DONE 600
         execute_cmd_within_guest "/usr/share/qa/qaset/qaset reset" 
         virsh reboot $vmName && sleep 30

    done
}    # ----------  end of function execute_perf_run_all  ----------

function trace_cmd_run ()
{
    local checkedfile=$1
    local timeout=$2
    [ -z "${file}" ] && checkedfile="/var/log/qaset/control/DONE"
    [ -z "$timeout" ] && timeout=60
    printInfo "Start trace performance run" INFO
    sed  -e "s:CHECKEDFILE:${checkedfile}:" -e "s/TIMEOUT/${timeout}/" ${SCRIPT_ROOT_PATH}/trace_perf_run.sample > ${SCRIPT_ROOT_PATH}/trace_perf_run.sh
    run_script_within_guest ${VM_NAME} ${SCRIPT_ROOT_PATH}/trace_perf_run.sh " check that perf test case is done"
    if [ $? -ne 0 ];then
         printInfo "Performance run is not done successfully within ${timeout}s" ERROR && exit 1
    fi

}    # ----------  end of function trace_cmd_run  ----------

function compare_perf_result ()
{
     local cmptype=$1
     local product=$2
     local tpnum=$3
     printInfo "Start to compare performance result" BANNER
     base_product=${OS}-${RELEASE}-${PATCH}
    sed  -e "s:CMPTYPE:${cmptype}:" -e "s/BASEPRODUCT/${base_product}/" -e "s/TPNUM/${tpnum}/" ${SCRIPT_ROOT_PATH}/compare_perf_result.sample > ${SCRIPT_ROOT_PATH}/compare_perf_result.sh
    run_script_within_guest ${VM_NAME} ${SCRIPT_ROOT_PATH}/compare_perf_result.sh " compare performance result within guest"
    if [ $? -ne 0 ];then
         printInfo "Failed to compare performance test" ERROR && exit 1
    fi
}    # ----------  end of function compare_perf_result  ----------

#=== START ==== ================================================================
#       Start from here
#===============================================================================

#-------------------------------------------------------------------------------
#  Parpare basic environments, like install repo, change hostname of guest etc
#-------------------------------------------------------------------------------
prepare_env

#-------------------------------------------------------------------------------
#   Generate comparsion pair 
#-------------------------------------------------------------------------------
generate_cmp_pair 100001 ${VM_NAME}

#-------------------------------------------------------------------------------
#   Execute performance test 
#-------------------------------------------------------------------------------
execute_perf_run_all "cccc  sysbench_sys"

#-------------------------------------------------------------------------------
#   Compare performance test
#-------------------------------------------------------------------------------
compare_perf_result  Q SLEs-12-sp2 100001

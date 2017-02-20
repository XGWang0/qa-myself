#!/bin/bash
#===============================================================================
#
#          FILE:  vm-perf-lib.sh
# 
#         USAGE:  ./vm-perf-lib.sh 
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
#       CREATED:  02/13/2017 03:32:17 AM EST
#      REVISION:  ---
#===============================================================================


source ./vh-update-lib.sh
sshNoPass="sshpass -e ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 "
getSettings="/usr/share/qa/virtautolib/lib/get-settings.sh"
export vmIP
export vmMac
export vmName
vmUser=`$getSettings vm.user`
vmPass=`$getSettings vm.pass`
export SSHPASS=$vmPass


#===  FUNCTION  ================================================================
#          NAME:  gather_logs
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================
function gather_logs()
{
    _testname=$1
    _vmconfigpath=$2
    _tcffilepath=$3
    _submitmsg=$4
    ((returncode+=`find /var/log/qa/ctcs2/ -name test_results -exec grep "^[0-9] 0" {} \; | wc -l`))

    v_updir=`find /var/log/qa/ctcs2 -type d -name "${_testname}*"|tail -1`
    [ -d $v_updir -a -e /tmp/virt_screenshot.tar.bz2 ] && cp /tmp/virt_screenshot.tar.bz2 $v_updir/

    #-------------------------------------------------------------------------------
    #  Compress libvirt relevant log to ctcs2 root path 
    #-------------------------------------------------------------------------------
    tar cvf $v_updir/libvirt.tar /var/log/libvirt >> /dev/null 2>&1
    if uname -r | grep -iq xen  || [ -e /proc/xen/privcmd ];then
        xl dmesg > $v_updir/xl-dmesg.log
        xm dmesg > $v_updir/xm-dmesg.log
        if [ -d /var/log/xen ];then
                tar cvf $v_updir/var-log-xen.tar /var/log/xen >> /dev/null 2>&1
        fi
    fi

    #-------------------------------------------------------------------------------
    #   Upload system relevant logs
    #-------------------------------------------------------------------------------
    dmesg > $v_updir/dmesg.log
    [ -e "/var/lib/xen/dump/" ]
       tar cvf $v_updir/var-lib-xen-dump.tar /var/lib/xen/dump/ >> /dev/null 2>&1
    [ -e "/var/lib/systemd/coredump/" ] && \
       tar cvf $v_updir/var-lib-systemd-coredump.tar /var/lib/systemd/coredump/ >> /dev/null 2&>1
    
    #-------------------------------------------------------------------------------
    #   Update tcf files and guest config files
    #-------------------------------------------------------------------------------
    [ -e "${_vmconfigpath}" ] && \
       tar cvf $v_updir/guest-xmls.tar ${_vmconfigpath} >> /dev/null 2>&1
    [[ "x$_tcffilepath" = "x" && -f "$_tcffilepath" ]] && \
       tar cvf $v_updir/tcf.tar $_tcffilepath >> /dev/null 2>&1
    
    #-------------------------------------------------------------------------------
    #   Send all logs to QADB   
    #-------------------------------------------------------------------------------
    /usr/share/qa/tools/remote_qa_db_report.pl -b -c "${_submitmsg}"
}    # ----------  end of function gather_relevant_files  ----------


#===  FUNCTION  ================================================================
#          NAME:  
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================
function get_mac_address ()
{
     local vmname=$1
     vmMac=`virsh dumpxml $vmname | grep -i "mac address=" | sed "s/^\s*<mac address='\([^']*\)'.*$/\1/"`
}    # ----------  end of function get_mac_address  ----------

#===  FUNCTION  ================================================================
#          NAME:  
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================
function get_ip_address ()
{
    local timeout=$1
    local tryTimer=0
    while [ $tryTimer -lt $timeout ];do
        # Get ip address through mac address
        ip=`get_ip_by_mac $vmMac`
        ip=${ip##* }
        if [ "$ip" == "mac-err" ];then
            ip=''
        else
            vmIP=$ip && return
        fi
        sleep 5
        ((tryTimer+=5))
    done
    printInfo "Failed to get ip address" ERROR
}    # ----------  end of function get_ip_address  ----------


#===  FUNCTION  ================================================================
#          NAME:  verify_guest_up_via_ssh
#   DESCRIPTION:  Through ssh to connect vm which is used to verify if vm is up
#    PARAMETERS:  param 1: vm name
#                 param 2: duration of verification
#                 param 3: interval time
#                 param 4: save screenshot of connection or not 
#       RETURNS:  0: pass; 1:fail
#===============================================================================

function verify_guest_up_via_ssh() {
    vm=$1
    timeout=$2
    interval=$3
    save_screenshot_flag=$4

    [ -z "$vm" ] && vm=$vmName || vmName=$vm
    [ -z "$timeout" ] && timeout=300
    [ -z "$interval" ] && interval=3
    [ -z "$save_screenshot_flag" ] && save_screenshot_flag="no"

    #-------------------------------------------------------------------------------
    # Get ip address thurn vm name
    #-------------------------------------------------------------------------------
    printInfo "Checking if vm is up or not thru ssh method" INFO
    get_mac_address $vm
    get_ip_address 300
    if `echo $ip | grep -i error > /dev/null`;then
        printInfo "Failed to get mac address" ERROR
        exit 1
    fi
    tryTimer=0
    while [ $tryTimer -lt $timeout ];do
        output=`$sshNoPass $vmUser@$ip "echo 'Check ssh connection state!'" 2>&1`
        ret=$?
        if echo "$output" | grep -iq "Permission denied";then
                echo "$output"
                commands=`echo "$output" | sed -n '/ssh-keygen/p'`
                eval $commands
                sleep 3
                rm /root/.ssh/known_hosts
                sleep 3
                output=`$sshNoPass $vmUser@$ip "echo 'Check ssh connection state!'" 2>&1`
                ret=$?
                echo "$output"
        fi

        #screenshot
        if [ "$save_screenshot_flag" = "yes" ];then
            screenshot $vm
        fi

        #result check
        if [ $ret -ne 0 ];then
            sleep $interval
            ((tryTimer+=$interval))
        else
            printInfo "The vm $vm is up via ssh connection check after ${tryTimer}s." INFO
            break
        fi
    done
    printInfo "VM Name: $vm
          VM User: $vmUser
          VM Pass: $vmPass
          VM Mac : $vmMac
          VM IP  : $vmIP" INFO 

    printInfo "Screenshot for ssh connect is located in /tmp/virt-install_screenshot/:" `ls /tmp/virt-install_screenshot/` INFO

    if [ $ret -eq 0 ];then
        rm /tmp/virt-install_screenshot/${vm}* > /dev/null 2>&1
        return 0
    else
        printInfo "The vm is not up until timeout ${timeout}s is over." ERROR
        return 1
    fi

}

#===  FUNCTION  ================================================================
#          NAME:  
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================
function change_guest_hostname ()
{
    local guesthostname=$1

    # Combine hostname of host to guest hostname
    [ -z "$guesthostname" ] && guesthostname="PERF"
    guesthostname="$HOSTNAME-$guesthostname"
   
    for i in `seq 0 3`
    do
        output=`$sshNoPass $vmUser@$vmIP " echo $guesthostname > /etc/hostname" 2>&1`
        ret=$?
        if [ $ret -eq 0 ];then
            virsh reboot $vmName
            verify_guest_up_via_ssh ${VM_NAME} 20 4 || exit 2
            output1=`$sshNoPass $vmUser@$vmIP " echo \\$HOSTNAME" 2>&1`
            echo $output1
            if [ ${output1} = ${guesthostname} ];then
               printInfo "Successfully modify guest hostname to $guesthostname" INFO
               return 0
           else
               printInfo "The special guest hostname is not set susccessfully, current hostname is $output1" ERROR
               exit 1
           fi
        else echo "$output" | grep -iq "Permission denied"
                 commands=`echo "$output" | sed -n '/ssh-keygen/p'`
                 eval $commands
                 sleep 3
                 rm /root/.ssh/known_hosts
        fi
        exit 1
    done

}    # ----------  end of function change_guest_hostname  ----------


function run_script_within_guest ()
{
    local vmname=$1
    local runscript=$2
    local msg=$3

    run_script_inside_vm ${vmname} ${runscript} NO NO
    ret=$?
    if [ $ret -ne 0 ];then
        printInfo "Failed to $msg"
        exit 1
    else
        printInfo "Successfully $msg"
    fi
}    # ----------  end of function add_qa_repo_to_guest  ----------


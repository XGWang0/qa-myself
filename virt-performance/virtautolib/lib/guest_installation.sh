#!/bin/bash
# ****************************************************************************
# Copyright (c) 2016 Unpublished Work of SUSE. All Rights Reserved.
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
#

source ./vh-update-lib.sh
source ./vm-perf-lib.sh
#-------------------------------------------------------------------------------
#   Guest installation start
#-------------------------------------------------------------------------------
printInfo "Guest Installation Start" BREAKLINE
pushd `dirname $0` >/dev/null

function EXIT() {
	local exitCode=$1
	popd > /dev/null
	exit $exitCode
}

function usage() {
	echo
	echo "Usage: $0 -g GUEST_LIST -f GUEST_CONFIG"
	echo "       -g, the guest list to be tested, for example \"sles-11-sp4-64\""
	echo "       -f, the file as guest installation config, default file is /aaa/bbb/ccc"
	EXIT 1
}

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

    [ -z "$interval" ] && interval=10
    [ -z "$save_screenshot_flag" ] && save_screenshot_flag="no"

    # Get mac address from vm config file for seaching realip address
    printInfo "Get mac address from vm config file" INFO
    mac=`virsh dumpxml $vm | grep -i "mac address=" | sed "s/^\s*<mac address='\([^']*\)'.*$/\1/"`
    sshNoPass="sshpass -e ssh -o StrictHostKeyChecking=no"
    local getSettings="/usr/share/qa/virtautolib/lib/get-settings.sh"
    vmUser=`$getSettings vm.user`
    vmPass=`$getSettings vm.pass`
    export SSHPASS=$vmPass

    #ensure vm ssh is up by accepting connections
    printINFO "Checking if vm is up or not thru ssh method" INFO 
    tryTimer=0
    while [ $tryTimer -lt $timeout ];do
        # Get ip address through mac address
        ip=`get_ip_by_mac $mac`
        ip=${ip##* }
        if [ "$ip" == "mac-err" ];then
                ip=''
        fi
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

    printInfo "Screenshot for ssh connect is located in /tmp/virt-install_screenshot/:" `ls /tmp/virt-install_screenshot/` INFO

    if [ $ret -eq 0 ];then
        rm /tmp/virt-install_screenshot/${vm}*
        return 0
    else
        printInfo "The vm is not up until timeout ${timeout}s is over." ERROR
        return 1
    fi

}

function change_sles10sp4_guest_network_to_virtio_on_kvm_host() {
	if ! uname -r|grep -iq xen && [ ! -e /proc/xen/privcmd ];then
		if virsh list --all | grep -iq sles-10-sp4-64-fv-def-net;then
			virsh dumpxml sles-10-sp4-64-fv-def-net > /tmp/sles-10-sp4-64-fv-def-net.xml
			sed -i 's/rtl8139/virtio/' /tmp/sles-10-sp4-64-fv-def-net.xml
			virsh destroy sles-10-sp4-64-fv-def-net
			virsh undefine sles-10-sp4-64-fv-def-net 
			virsh define /tmp/sles-10-sp4-64-fv-def-net.xml
			virsh create /tmp/sles-10-sp4-64-fv-def-net.xml
			virsh destroy sles-10-sp4-64-fv-def-net
		fi
	fi
}

#get params
while getopts "g:f:" OPTION
do
	case $OPTION in
		g)GUEST_LIST="$OPTARG";;
		f)GUEST_CONFIG="$OPTARG";;
		\?)usage;;
		*)usage;;
	esac
done

#-------------------------------------------------------------------------------
#   Initialize project root folder to store relevant files
#-------------------------------------------------------------------------------
backupRootDir=/tmp/virt-performance/vm_backup
backupVmListFile=${backupRootDir}/vm.list
backupCfgXmlDir=$backupRootDir/vm-config-xmls
backupDiskDir=$backupRootDir/vm-disk-files
exitCode=0

printInfo "Initialize project workspace:  
       Project wrkspace path:$backupVmListFile
       VM config backup path:$backupCfgXmlDir
       Disk file back path:$backupDiskDir" INFO



#-------------------------------------------------------------------------------
#   Guest installation 
#-------------------------------------------------------------------------------
printInfo "Start to install guest" BREAKLINE

install_vm_guests $GUEST_CONFIG "$GUEST_LIST"

ret=$?
if [ $ret -ne 0 ];then
    printInfo "Gest installation failure, check manually" ERROR
fi
((exitCode+=$ret))


#-------------------------------------------------------------------------------
#   Backup vm config, disk file
#-------------------------------------------------------------------------------
printInfo "Backup VM config and disk files" INFO
#backup_vm_guest_data $backupRootDir $backupVmListFile $backupCfgXmlDir $backupDiskDir
if [ $? -ne 0 ];then
    EXIT 2
fi

gather_logs "VmInstall-" "$backupCfgXmlDir" "" "Test result for virtualization guest installation test"

EXIT $exitCode

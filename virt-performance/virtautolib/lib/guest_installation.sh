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

function verify_guest_upgrade_via_susereleasefile() {
	vm=$1
	product_upgrade=$2

	commands='
        realProduct=`sed -n "1p" /etc/SuSE-release`
        if [[ "$realProduct" = "SUSE Linux Enterprise Server"* ]];then
                realProductName="sles"
        fi
        if [[ "$realProduct" = *"x86_64"* ]];then
                realArch="64"
        else
                realArch="32"
        fi
        realVersion=`grep "VERSION" /etc/SuSE-release | sed "s/^.*VERSION = \(.*\)\s*$/\1/"`
        realSp=`grep "PATCHLEVEL" /etc/SuSE-release | sed "s/^.*PATCHLEVEL = \(.*\)\s*$/\1/"`
        realProductFullName="${realProductName}-${realVersion}-sp${realSp}-${realArch}"
        if [ "$realProductFullName" == "$upgrade_product" ];then
            exit 0
        else
            exit 1
        fi
	'
	tmpScript="/tmp/verify_guest_upgrade_via_susereleasefile-$$.sh"
	commands=${commands/\$upgrade_product/$product_upgrade};
	echo "$commands" > $tmpScript
	run_script_inside_vm $vm "$tmpScript" no no
	ret=$?
	rm $tmpScript
	if [ $ret -eq 0 ];then
		echo "The SuSe-release file in guest $vm is correct after guest upgrade."
	else
		echo "The SuSe-release file in guest $vm is wrong after guest upgrade."
	fi
	return $ret
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

function test_single_guest_upgrade() {
	vm=$1
	product_upgrade=$2
	product_upgrade_repo=$3
	logFile=$4

	adminCommand="/usr/share/qa/virtautolib/lib/vm-administration.sh -m $vm"
	#admin before guest upgrade
	$adminCommand
	if [ $? -ne 0 ];then
		echo "  $vm  ---  Fail  ---  Administration before guest upgrade fail." >> $logFile
		return 1
	fi

	#update guest higher than sle10
	guestRelease=`echo $vm | cut -d'-' -f 2`
	if [ $guestRelease -gt 10 ];then
		#update guest to product's update repo to avoid any blocking issue for guest upgrade
		updateGuestScript=/tmp/update-guest-$$.sh
		local getSource="/usr/share/qa/virtautolib/lib/get-source.sh"
		guestUpdateRepo=`$getSource source.virtupdate.${vm%-[fp]v*}`
		cat > $updateGuestScript <<eof
			if ! (zypper lr -u | grep -q guestUpdateRepo);then
				zypper --non-interactive --gpg-auto-import-keys ar $guestUpdateRepo guestUpdateRepo
			fi
			zypper --non-interactive --gpg-auto-import-keys ref guestUpdateRepo
			zypper --non-interactive --gpg-auto-import-keys up
eof
		echo "Debug: the updateGuestScript content is:"
		cat $updateGuestScript
		run_script_inside_vm $vm "$updateGuestScript" no no
		if [ $? -ne 0 ];then
			echo "  $vm  ---  Fail  ---  Guest update to product's update repo without reboot fail." >> $logFile
			return 1
		fi
		
		#special workaround for sle11sp3/sp4 to upgrade to sle12sp2 due to libpango bug
		if [ $guestRelease -eq 11 ];then
			specialWorkaroundScript=/tmp/special-workaround-$$.sh
			local getSource="/usr/share/qa/virtautolib/lib/get-source.sh"
			specialWorkaroundRepo=`$getSource source.virtupdate.sles-11-sp1-64`
			cat > $specialWorkaroundScript <<eof
				if ! (zypper lr -u | grep -q specialWorkaroundRepo);then
					zypper --non-interactive --gpg-auto-import-keys ar $specialWorkaroundRepo specialWorkaroundRepo
				fi
				zypper --non-interactive --gpg-auto-import-keys ref specialWorkaroundRepo
				zypper --non-interactive --gpg-auto-import-keys up pango*
eof
			echo "Debug: the specialWorkaroundScript  content is:"
			cat $specialWorkaroundScript
			run_script_inside_vm $vm "$specialWorkaroundScript" no no
			if [ $? -ne 0 ];then
				echo "  $vm  ---  Fail  ---  Guest special workaround update without reboot fail." >> $logFile
				return 1
			fi
		fi
			
		#reboot
		tmpRebootScript="/tmp/reboot-$$.sh"
		echo "reboot">$tmpRebootScript
		run_script_inside_vm $vm "$tmpRebootScript" no no
		echo "Reboot command is sent to guest $vm."
		rm $tmpRebootScript
		sleep 30

		#verify guest is up after update guest
		timeout=300
		verify_guest_up_via_ssh $vm $timeout
		if [ $? -ne 0 ];then
			echo "  $vm  ---  Fail  ---  Reboot after guest update to update repo and special workarounds fail." >> $logFile
			return 1
		fi
		
	fi

	#kill all zypper process before guest upgrade
	killZypperProcScript=/tmp/kill_zypper_procs-$$.sh
	cat > $killZypperProcScript <<eof
	zypperProcs=\`ps -ef | grep [z]ypper | gawk "{print \\\\\\\$2;}"\`
	[ -z "\$zypperProcs" ] && exit 0
	for proc in \$zypperProcs;do
		kill -9 \$proc
	done
eof
	echo "Debug: killZypperProcScript content is:"
	cat $killZypperProcScript
	run_script_inside_vm $vm "$killZypperProcScript" no no
	if [ $? -ne 0 ];then
		echo "  $vm  ---  Fail  ---  Kill zypper processes before guest upgrade fail.." >> $logFile
		return 1
	fi

	#do guest upgrade
	/usr/share/qa/virtautolib/lib/guest_upgrade.sh $product_upgrade $product_upgrade_repo $vm
	if [ $? -ne 0 ];then
		echo "  $vm  ---  Fail  ---  Guest upgrade without reboot fail." >> $logFile
		return 1
	fi

	#reboot guest
	tmpRebootScript="/tmp/reboot-$$.sh"
	echo "reboot">$tmpRebootScript
	run_script_inside_vm $vm "$tmpRebootScript" no no
	echo "Reboot command is sent to guest $vm."
	rm $tmpRebootScript
	sleep 10

	#wait extra time in case save_screenshot affect the grub2 boot select timer
	sleep 60

	#verify machine is up
	vmRelease=`echo $vm | cut -d'-' -f 2`
	upgradeRelease=`echo $product_upgrade | cut -d'-' -f 2`
	if [ $vmRelease -lt $upgradeRelease ];then
		timeout=3600
	elif [ $vmRelease -eq $upgradeRelease ];then
		timeout=600
	else
		timeout=0
	fi
	echo "Timeout for waiting the machine to be up is ${timeout}s."
	verify_guest_up_via_ssh $vm $timeout 60 yes
    if [ $? -ne 0 ];then
        echo "  $vm  ---  Fail  ---  Reboot after guest upgrade fail." >> $logFile
		return 1
    fi

	#verify guest upgrade via SuSe-release file
	verify_guest_upgrade_via_susereleasefile $vm $product_upgrade
    if [ $? -ne 0 ];then
        echo "  $vm  ---  Fail  ---  Incorrect SuSe-release after guest upgrade." >> $logFile
		return 1
    fi

	#shutdown vm
	virsh destroy $vm

	#admin after guest upgrade
	$adminCommand
    if [ $? -ne 0 ];then
        echo "  $vm  ---  Fail  ---  Administration after guest upgrade fail." >> $logFile
		return 1
    fi
	echo "  $vm  ---  Pass" >> $logFile
}   

function do_full_guest_upgrade_test() {
	product_upgrade=$1
	product_upgrade_repo=$2
	vmList=`virsh list --all --name | sed '/Domain-0/d'`
	retCode=0
	logFile=/tmp/full_guest_upgrade_test-$$.log

	if [ -f $logFile ];then
		rm $logFile
	fi

	#result column meaning
	echo "         Guest Name          --- Result ---  Reason  " > $logFile
	#loop guest list to do guest upgrade test
	for vm in $vmList;do
		test_single_guest_upgrade $vm $product_upgrade $product_upgrade_repo $logFile
		ret=$?
		((retCode+=$ret))
		#to lease resources of the guest if it fails
		if [ $ret -ne 0 ];then
			virsh destroy $vm
			virsh undefine $vm
		fi
	done

	#print result
	echo -e "\n\nOverall guest upgrade result is:"
	cat $logFile
	echo "Test done"

	return $retCode
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

#install_vm_guests $GUEST_CONFIG "$GUEST_LIST"

ret=$?
if [ $ret -ne 0 ];then
    printInfo "Gest installation failure, check manually" ERROR
fi
((exitCode+=$ret))


#-------------------------------------------------------------------------------
#   Backup vm config, disk file
#-------------------------------------------------------------------------------
printInfo "Backup VM config and disk files" INFO
backup_vm_guest_data $backupRootDir $backupVmListFile $backupCfgXmlDir $backupDiskDir
if [ $? -ne 0 ];then
    EXIT 2
fi

EXIT $exitCode

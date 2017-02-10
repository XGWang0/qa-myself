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
#


export LANG=C

#*** SCRUPT ********************************************************************
#   SCRUPT NAME: vm-update_rpms-run.sh
#          DESC: This script is to call ctcs2 script for updating relevant rpms for virtualization test 
#          USAG: vm-update_rpms-run.sh 
#*******************************************************************************


#===  FUNCTION  ================================================================
#          NAME: usage()
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  1
#===============================================================================

function usage() {
    echo ""
    echo "Usage: $0 [-v kvm/xen] [-p product] "
    echo "-v, hypervisor type, xen/kvm supported, default to kvm."
    echo "-t, test type, default std."
    exit 1
}

while getopts "v:p:a:t" OPTIONS
do
    case $OPTIONS in
        v)HYPERVISOR="$OPTARG";;
        t)TESTTYPE="$OPTARG";;
        \?)usage;;
        *)usage;;
    esac
done

#-------------------------------------------------------------------------------
#   Initialize default value of parameters
#-------------------------------------------------------------------------------

[ -z "$HYPERVISOR" ] && HYPERVISOR="kvm"
[ -z "$TESTTYPE" ] && TESTTYPE="std"

CTCS2_DIR=/usr/lib/ctcs2
TCF_DIR=/usr/share/qa/tcf
RUN_NAME=`basename $0`
TCF_SAMPLE_NAME="qa_virtualization-perf-update_rpm-sample.tcf"
TCF_NAME="qa_virtualization-perf-update_rpm.tcf"
TCF_FILE="$TCF_DIR/$TCF_NAME"


#-------------------------------------------------------------------------------
#   Copy new tcf according to tcf sample and replace keywork by real value
#-------------------------------------------------------------------------------
cp /usr/share/qa/tcf/${TCF_SAMPLE_NAME} ${TCF_FILE}
sed -i -e "s/HYPERVISOR/${HYPERVISOR}/" -e "s/TESTTYPE/$TESTTYPE/" ${TCF_FILE}

rm -rf /tmp/virt_screenshot.tar.bz2 /tmp/virt-install_screenshot
rm -rf /var/log/qa/ctcs2/qa_virtualization-perf-update_rpm*

$CTCS2_DIR/tools/run $TCF_FILE

#-------------------------------------------------------------------------------
#   Verify result and get ctcs2 log path
#-------------------------------------------------------------------------------
returncode=0

for file in `find /var/log/qa/ctcs2/ -name test_results`; do
	[ -z "$(cat $file)" ] && ((returncode+=1))
done

((returncode+=`find /var/log/qa/ctcs2/ -name test_results -exec grep "^[0-9] 0" {} \; | wc -l`))

v_updir=`find /var/log/qa/ctcs2 -type d -name "qa_virtualization-perf-update_rpm*"|tail -1`
[ -d $v_updir -a -e /tmp/virt_screenshot.tar.bz2 ] && cp /tmp/virt_screenshot.tar.bz2 $v_updir/

#-------------------------------------------------------------------------------
#   Generate hypervisor relevant logs
#-------------------------------------------------------------------------------
tarlogpath=${v_updir}/gather_log.debug
echo "aaaaaaaaaaaaaaa" >> $tarlogpath 2>&1
tar cvf $v_updir/libvirt.tar /var/log/libvirt >> $tarlogpath 2>&1
if uname -r | grep -iq xen  || [ -e /proc/xen/privcmd ];then
	xl dmesg > $v_updir/xl-dmesg.log
	xm dmesg > $v_updir/xm-dmesg.log
	if [ -d /var/log/xen ];then
		tar cvf $v_updir/var-log-xen.tar /var/log/xen >> $tarlogpath 2>&1
	fi
fi

#-------------------------------------------------------------------------------
#   Upload system relevant logs
#-------------------------------------------------------------------------------
dmesg > $v_updir/dmesg.log
[ -e "/var/lib/xen/dump/" ]
   tar cvf $v_updir/var-lib-xen-dump.tar /var/lib/xen/dump/ >> $tarlogpath 2>&1
[ -e "/var/lib/systemd/coredump/" ] && \
   tar cvf $v_updir/var-lib-systemd-coredump.tar /var/lib/systemd/coredump/ >> $tarlogpath 2&>1

#-------------------------------------------------------------------------------
#   Update tcf files and guest config files
#-------------------------------------------------------------------------------
[ -e "/tmp/vm_backup/vm-config-xmls" ] && \
   tar cvf $v_updir/guest-xmls.tar /tmp/vm_backup/vm-config-xmls >> $tarlogpath 2>&1
[ -e "/usr/share/qa/tcf/qa_virtualization-perf-update_rpm.tcf" ] && \
   tar cvf $v_updir/tcf.tar /usr/share/qa/tcf/qa_virtualization-perf-update_rpm.tcf >> $tarlogpath 2>&1

#-------------------------------------------------------------------------------
#   Send all logs to QADB   
#-------------------------------------------------------------------------------
/usr/share/qa/tools/remote_qa_db_report.pl -b -c "Test result for virtualization host rpms upgrade test: $TCF_FILE."

exit $returncode

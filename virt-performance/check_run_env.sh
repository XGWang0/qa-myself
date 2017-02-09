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


#*** SCRUPT ********************************************************************
#   SCRUPT NAME: check_run_env.sh
#          DESC: This script is to check rurrent OS running ENV, contain 
#                 hypervisor type, product version, architecture etc.
#          USAG: check_run_env.sh -v [HYAPERVISOR kvm/xen] -p PRODUCT i
#                                 -a ARCH -t [TEST_TYPE std/dev]
#       EXAMPLE: check_run_env.sh -v kvm -p sles-12-sp2 -a 64 -t std
#*******************************************************************************

source /usr/share/qa/virtautolib/lib/virtlib

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
    echo "-p, product name, default to sles-12-sp1-64"
    echo "-t, test type, default std."
    exit 1
}

while getopts "v:p:a:t" OPTIONS
do
    case $OPTIONS in
        v)HYPERVISOR="$OPTARG";;
        p)PRODUCT="$OPTARG";;
        t)TESTTYPE="$OPTARG";;
        \?)usage;;
        *)usage;;
    esac
done


printInfo "OS ENV CHECKING AND RPMS UPGRADE PHASE START" BREAKLINE
#-------------------------------------------------------------------------------
#   Initialize default value of parameters
#-------------------------------------------------------------------------------

[ -z "$HYPERVISOR" ] && HYPERVISOR="kvm"
[ -z "$PRODUCT" ] && PRODUCT="sles-12-sp1-64"
[ -z "$TESTTYPE" ] && TESTTYPE="std"

#===  FUNCTION  ================================================================
#          NAME:  check_os_env
#   DESCRIPTION:  check hypervisor type, os version etc
#    PARAMETERS:  
#       RETURNS:  0 : success
#                 1 : incorrect hypervisor type
#                 2 : unexpected os version
#===============================================================================
function check_os_env ()
{
        _product=`sed -n '1p' /etc/SuSE-release`                      
        if [[ "$_product" = "SUSE Linux Enterprise Server"* ]];then   
                _roductName="sles"
        fi
        if [[ "$_product" = *"x86_64"* ]];then                        
                _arch="64"
        else    
                _arch="32"                                            
        fi
        _version=`grep "VERSION" /etc/SuSE-release | sed 's/^.*VERSION = \(.*\)\s*$/\1/'`
        _patch=`grep "PATCHLEVEL" /etc/SuSE-release | sed 's/^.*PATCHLEVEL = \(.*\)\s*$/\1/'`
        _product_full_name="${_roductName}-${_version}-sp${_patch}-${_arch}"

        if uname -r | grep xen >/dev/null && [ -e /proc/xen/privcmd ];then
                _hypervisor="xen"
        else
                _hypervisor="kvm"
        fi

        printInfo "Local OS env:" INFO
        printInfo "PRODUCT:$_roductName"
        printInfo "VERSION:$_version"
        printInfo "PATCH:$_patch"
        printInfo "HYPERVISOR:$_hypervisor"

        if [ ! "`echo ${HYPERVISOR} | tr [A-Z] [a-z]`" = "$_hypervisor" ];then
                echo "Error: You aim to run ${HYPERVISOR} test, but you are on $_hypervisor kernel." >&2
                exit 1
        fi
        if [ ! "`echo ${PRODUCT} | tr [A-Z] [a-z]`" = "${_product_full_name}" ];then
                echo "Error: You aim to run test on product ${PRODUCT}, but you are on ${_product_full_name} platform." >&2
                exit 2
        fi
        
}    # ----------  end of function check_os_env  ----------


#===  FUNCTION  ================================================================
#          NAME:  update_rpms
#   DESCRIPTION:  
#    PARAMETERS:  std/dev
#       RETURNS:  0  : pass
#                 ! 0 : fail
#===============================================================================
function update_rpms ()
{
    if [ $TESTTYPE = "std" ];then
        update_virt_rpms off on off
    else
        update_virt_rpms off off on
    fi
}    # ----------  end of function update_rpms  ----------


printInfo "Check current OS environment" BANNER
check_os_env

printInfo "Update all relevant rpm"  BANNER
update_rpms
ret=$?
printInfo "OS ENV CHECKING AND RPMS UPGRADE PHASE END" BREAKLINE


exit $ret

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

function get_full_hostname ()
{
    name=`hostname`
    case $name in
        apac2*)
            name="${name}."
            name=${name/.*/".bej.suse.com"}
            ;;
        ix64ph10*)
            name="${name}."
            name=${name/.*/".qa.suse.de"}
            ;;
        *)
            :
            ;;
    esac
    echo ${name}
}    # ----------  end of function get_full_hostname  ----------

function cmp_perf_result ()
{
     local comparsion_type=$1
     local product=`echo $2 | tr [a-z] [A-Z]`
     local tp_num=$3

     [ -z "$kernel" ] && kernel=`uname -r`
     output=`/usr/share/qa/tools/product.pl`
     if echo $output | grep -i $product;then
         build=`echo $output | sed "s/${product}-//"`
     fi
     [ -n "$build" ] && verify_build ${build} || (echo "[ERROR]: Failed to get build info for creating test plan for performance test" && exit 1)
     fullhostname=$(get_full_hostname)
     if [ "$comparsion_type" = "Q" ];then
         echo "[INFO ]: Execute comparvison operation with [/usr/share/qa/perfcom/perfcmd.py compare-run -a x86_64 -r $project -b ${build} -k ${kernel} -m ${fullhostname} -n ${tp_num}]"
         /usr/share/qa/perfcom/perfcmd.py compare-run -a x86_64 -r $product -b ${build} -k ${kernel} -m ${fullhostname} -n ${tp_num}
     else
         echo "[INFO ]: Skip comparvison operation due to current perf run is reference distro object."
     fi
}    # ----------  end of function create_distro_pair  ----------


function verify_build ()
{
    local build=$1
    local CONST_BUILD_SCOPE="GA GM GMC BETA ALPHA RC"
    for b in $CONST_BUILD_SCOPE
    do
        if [[ "${build}" =~ "${b}"[0-9]* ]];then
            return 0
        fi
    done
    return 1
}    # ----------  end of function verify_build  ----------


#create_tp  60008 sles-12-sp1
cmp_perf_result Q sles-12-sp2 100001

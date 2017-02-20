#!/bin/bash
#===============================================================================
#
#          FILE:  define_qaset_env.sh
# 
#         USAGE:  ./define_qaset_env.sh 
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
#       CREATED:  02/15/2017 03:38:37 AM EST
#      REVISION:  ---
#===============================================================================


#===  FUNCTION  ================================================================
#          NAME:  
#   DESCRIPTION:  
#    PARAMETERS:  
#       RETURNS:  
#===============================================================================
function init_distro ()
{
    arch=x86_64
    release=SLES-12-SP2
    build=RC1
    kernel=4.4
    testplan=$1
}    # ----------  end of function init_distro  ----------

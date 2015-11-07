#!/bin/bash - 

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

set -a




print_full_usage()
{
        echo "Purpose: This program will deploy jenkins jobs for virtualization automatic test"
        echo
        echo "Usage: $0 --help -h -help | -j -u -p"
        #echo "Usage: $0 --help -h -help | -j -u -p -t -s"
        echo
        echo "Man: "
        echo
        echo " -h,-help,--help"
	echo "        - Prints the full usage"
	echo 
        echo " -j <jenkins home path>"
	echo "        - The jenkins home path or installation path"
	echo "        - EXAMPLE: var/lib/jenkins"
	echo 
        echo " -u <jenins url>"
	echo "        - The url of jenkins on websit"
	echo "        - EXAMPLE: http://127.0.0.1:8080/"
	echo 
        echo " -p <project name>"
	echo "        - The project name you want to create and delpoy jenkins jobs in it"
	echo "        - EXAMPLE: VIRTUALIZATION"
        echo 
#        echo " -t <job name>"
#	echo "        - The job name that you want to deploy it to jenkins server"
#	echo "        - EXAMPLE: 01_InstallingGuest;ALL"
#	echo "        - If you want to deploy all jobs on jenkins, pass All to this parameter"
#        echo 
#        echo " -s <jenkins slave>"
#	echo "        - The slave name that you want to run job"
#	echo "        - EXAMPLE: hamsta_slave, 147.2.207.30"
#	echo 
        echo "Examples:"
#        echo "        $0 -j /var/lib/jenkins -u http://127.0.0.1:8080/ -p VIRTUALIZATION -t 01_InstallingGuest|ALL -s hamsta_slave"
        echo "        $0 -j /var/lib/jenkins -u http://127.0.0.1:8080/ -p VIRTUALIZATION "
        popd > /dev/null; exit 1

}	# ----------  end of function print_full_usage  ----------


print_usage()
{
        echo "Purpose: This program will deploy jenkins jobs for virtualization automatic test"
        echo
        #echo "Usage: $0 --help -h -help | -j -u -p -t"
        echo "Usage: $0 --help -h -help | -j -u -p"
        echo
        echo "Man: "
        echo
        echo " -h,-help,--help - Prints the full usage"
        echo " -j <jenkins home path>"
        echo " -u <jenins url>"
        echo " -p <project name>"
#        echo " -t <job name>"
#        echo " -s <slave name>"
        echo 
        echo "Examples:"
#        echo "        $0 -j /var/lib/jenkins -u http://127.0.0.1:8080/ -p VIRTUALIZATION -t 01_InstallingGuest|ALL -s hamsta_slave"
        echo "        $0 -j /var/lib/jenkins -u http://127.0.0.1:8080/ -p VIRTUALIZATION "
        popd > /dev/null; exit 1

}	# ----------  end of function print_usage  ----------




#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  printOutput
#   DESCRIPTION:  display normal output to console
#    PARAMETERS:  1:message level (N:normal messages;
#                                  E:error messages; W:warning messages)
#                 2:messages
#                 3:return code
#       RETURNS:  parameters 3 value
#-------------------------------------------------------------------------------
printOutput ()
{
	MSG_LEVEL=$1
	MSG_CONT=$2
	RETURN_CODE=$3

	if [ ${MSG_LEVEL} = "E" ]  ; then
		echo "ERROR:${MSG_CONT}"
	elif [ ${MSG_LEVEL} = "W" ]  ; then
		echo "WARN :${MSG_CONT}"
	else
		echo "INFO :${MSG_CONT}"
	fi

	return ${RETURN_CODE}
	
}	# ----------  end of function printOutput  ----------


#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  downloadPlugin
#   DESCRIPTION:  download plugin for jenkins
#    PARAMETERS:  1:jenkins home path; 2:plugin name
#       RETURNS:  Null
#-------------------------------------------------------------------------------

downloadPlugin ()
{
	JENKINS_HOME=$1
	PLUGIN_NAME=$2

	JENKINS_PLUGIN_PATH=${JENKINS_HOME}/plugins
	PLUGIN_DOWNLOAD_WEBSITE=http://updates.jenkins-ci.org/download/plugins

	if [ -e ${JENKINS_PLUGIN_PATH} ] ; then
		cd ${JENKINS_PLUGIN_PATH}
		
		if [ -e ${PLUGIN_NAME} ] ; then
			printOutput N "Plugin ${PLUGIN_NAME} exists on jekins home" 0
		else
			curl -O ${PLUGIN_DOWNLOAD_WEBSITE}/${PLUGIN_NAME}
				
			if [ $? -eq 0 ]  ; then
				printOutput N "Download plugin ${PLUGIN_NAME} successfully" 0
			else
				printOutput W "Failed to download plugin ${PLUGIN_NAME}" 0
				while :
				do
					echo -n "Would you like to continue?(Y/N)" && read INPUT_WORD
					
					if [ -n "${INPUT_WORD}" ]; then
						if [ "${INPUT_WORD}" = "Y" ] ; then
							break
						elif [ "${INPUT_WORD}" = "N" ] ; then
							exit 10
						fi
					else
						continue
					fi
				done
				
			fi
		fi
	else
		printOutput E "Jenkins plugins folder [${JENKINS_PLUGIN_PATH}] does not exist" 10
		exit $?
	fi

}	# ----------  end of function downloadPlugin  ----------


#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  modifySlave
#   DESCRIPTION:  Replace actual slave name in job config file
#    PARAMETERS:  1: job config file; 2: slave name
#       RETURNS:  Null
#-------------------------------------------------------------------------------

modifySlave ()
{
	CONFIG_FILE=$1
	SLAVE=$2
	sed -i "s:\(  <assignedNode>\)147.2.207.30\(</assignedNode>\):\1${SLAVE}\2:g" ${CONFIG_FILE}
	
	printOutput N "Change the acutal slave name in job config file[${CONFIG_FILE}]" 0
}	# ----------  end of function modifySlave  ----------

#---  FUNCTION  ----------------------------------------------------------------
#          NAME:  deployJenkinsFolder
#   DESCRIPTION:  Deploy jenkins folder to jenkins home
#    PARAMETERS:  1:jenkins path where creates folder
#                 2:jenkins url
#                 3:folder name
#       RETURNS:  Null
#-------------------------------------------------------------------------------

deployJenkinsFolder ()
{

	JENKINS_URL=$1
	JENKINS_HOME=$2
	PROJECT_NAME=$3

	JENKINS_FOLDER_PATH=${JENKINS_HOME}/jobs/
	JENKINS_CONFIG_PATH=${CURRENT_PATH}/jenkins_cfg_files/jobs/

	if [ -e ${JENKINS_FOLDER_PATH} ]; then
		:
	else
		mkdir -p ${JENKINS_FOLDER_PATH}/jobs
	fi
	cd $JENKINS_CONFIG_PATH
	config_list=`find . -name config.xml`

	while read line
        do
                if [ -n "${PROJECT_NAME}" ];then
                        if `echo $line | grep ${PROJECT_NAME}> /dev/null`;then
                                cp --parents $line $JENKINS_FOLDER_PATH
                        fi
                elif [ -z "${PROJECT_NAME}" ];then
                        cp --parents $line $JENKINS_FOLDER_PATH
                fi
        done<<<"${config_list}"
	chown -R jenkins:jenkins ${JENKINS_FOLDER_PATH}
	curl -X POST ${JENKINS_URL}/reload
	
}	# ----------  end of function deployJenkinsFolder  ----------



#-------------------------------------------------------------------------------
#                            Porgranm Entrance                                 
#-------------------------------------------------------------------------------
if [ $# -eq 1 ]
then
        if [ "${1}" == "--help" ] || [ "${1}" == "-help" ] || [ "${1}" == "-h" ]
        then
                print_full_usage
                popd > /dev/null; exit 1
        fi
elif [ $# -ne 6 ];then
	print_full_usage
	popd > /dev/null; exit 1
fi
while getopts "j:p:u:" OPTIONS; do  
  case $OPTIONS in  
    j)  
      JENKINS_HOME=$OPTARG
      ;;
    p)
      PROJECT_NAME=$OPTARG
      ;;  
    u)
      JENKINS_URL=$OPTARG
      ;;  
    \?)  
      printOutput W "Invalid parameters !!" 1
      print_usage; exit 1
      ;;  
  esac  
done  

CURRENT_PATH=`pwd`
#JENKINS_HOME=/var/lib/jenkins
PLUGIN_LIST="ansicolor.jpi cucumber-reports.jpi extended-choice-parameter.jpi scripttrigger.jpi email-ext.jpi cloudbees-folder.jpi"


for PLUGIN in ${PLUGIN_LIST}
do
	downloadPlugin ${JENKINS_HOME} ${PLUGIN}
done

deployJenkinsFolder  ${JENKINS_URL} ${JENKINS_HOME} ${PROJECT_NAME}

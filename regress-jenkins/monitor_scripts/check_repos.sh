#!/bin/bash


ARCH_LIST="i386 ia64 x86_64"
BASIC_REPO=http://147.2.207.1/dist/install/SLP/SLES-11-SP4-LATEST
CURRPATH=./

# download_changelog(REPO OUTPUT)
download_filelist() {
  REPO=$1
  LOGFILE=$2
  RET=0

  if (wget -q -O $LOGFILE ${REPO}/ChangeLog); then
    RET=0
  else
    RET=1
  fi
  return $RET
}

# trigger jenkins job
trigger_Jenkins() {
    ARCH=$1
    REPO=$2
    
    lowerarch=`echo ${ARCH} | tr [[:upper:]] [[:lower:]]` 
    echo "$JENKINS_URL/job/REGRESSIONTEST/job/SLES-11-SP4/job/${ARCH}/job/02_InstallHost/buildWithParameters?REPOSITORY=$2&ARCH=${lowerarch}"
    wget -O - -q  "$JENKINS_URL/job/REGRESSIONTEST/job/SLES-11-SP4/job/${ARCH}/job/02_InstallHost/buildWithParameters?REPOSITORY=$2&ARCH=${lowerarch}" > /dev/null
}


#### main enterance ####

if [ -n "$1" ];then
    BASIC_REPO=$1
    if [ -n "$2" ];then
        CURRPATH=$2
    fi
else
        :
fi

for ARCH in $ARCH_LIST; do
    REL_REPO=${BASIC_REPO}/${ARCH}/DVD1/
      if ! [ -e "./repo_info" ];then
          mkdir repo_info
      fi

      REPO_CURR=repo_info/repo_curr_${ARCH}
      REPO_LAST=repo_info/repo_last_${ARCH}

    # Download changelog of repo
    echo "[INFO] Retrieving changelog for ${ARCH} on ${BASIC_REPO}"
    download_filelist ${REL_REPO} ${REPO_CURR}
    # compare last to curr
    if [ ! -e "$REPO_LAST" ]; then
      echo "Triggering jenkins job for ${ARCH}: Missing previous cangelog"
      trigger_Jenkins ${ARCH} ${REL_REPO}
    else
      if `diff -i -E -Z -w -B ${REPO_CURR} ${REPO_LAST} > /dev/null` ;then
        echo "There is no change from last check, do not need to trigger"
      else
        trigger_Jenkins ${ARCH} ${REL_REPO}
      fi
    fi
    cp ${REPO_CURR} ${REPO_LAST}

done


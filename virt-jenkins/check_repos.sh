#!/bin/bash

. ./repos.h


OS_LIST="SLE11 SLE12 OS13"
SP_LIST="SP0 SP1 SP2 SP3 SP4"


# download_filelist(REPO OUTPUT)
download_filelist() {
  REPO=$1
  OUTPUT=$2
  RET=0
  XML=$(mktemp /tmp/repomd.xml.XXXXX)
  FLIST=$(mktemp /tmp/repodata.XXXXX)
  if (wget -q -O $XML ${REPO}/repodata/repomd.xml); then
    declare -i filelists_nr=`sed -n -e '/data type="filelists"/=' $XML`+3
    filelists=$(basename $(awk -F\" "NR==$filelists_nr {print \$2}" $XML))
    if (wget -q -O $FLIST ${REPO}/repodata/$filelists); then
      zcat $FLIST > $OUTPUT
      rm $FLIST
    else
      #echo "${REPO}/repodata/$filelists not found!"
      RET=1
    fi
    rm $XML
  else
    #echo "${REPO}/repodata/repomd.xml not found!"
    RET=1
  fi
  return $RET
}


# check_for_updates(PACKAGE CURRENT LAST)
check_for_updates() {
  PACKAGE=$1
  CURRENT=$2
  LAST=$3

  # Get current pkgid
  CURR_PKGID=`grep -E "name=\"$PACKAGE\" arch=\"(noarch|x86_64)\"" $CURRENT | awk '{print $2}' | awk -F "\"" '{print $2}'`
  if [ -z "$CURR_PKGID" ]; then
    echo "[WARNING] Package $PACKAGE not found in repo"
    continue
  fi

  # Get last pkgid
  LAST_PKGID=`grep -E "name=\"$PACKAGE\" arch=\"(noarch|x86_64)\"" $LAST | awk '{print $2}' | awk -F "\"" '{print $2}'`
  [ -z "$LAST_PKGID" ] && LAST_PKGID="none"

  if [ "$LAST_PKGID" == "$CURR_PKGID" ];then
    echo "[INFO] The $PKG package does not need to be updated"
  else
    echo "Detected package change ($PACKAGE)"
    return 0
  fi

  return 1
}


# trigger (OS_VER SP_VER PACKAGE CURRENT LAST CAUSE)
trigger() {
  OS_VER=$1
  SP_VER=$2
  PACKAGE=$3
  CURRENT=$4
  LAST=$5
  VIRT_TYPE=$6
  CAUSE=$7
  TRIGGER_LOG=repo_info/trigger_${OS_VER}_${SP_VER}.log
  echo "Test triggered on $(date +'%A, %x at %X')" > $TRIGGER_LOG
  echo "" >> $TRIGGER_LOG
  if [ "$PACKAGE" != "" ]; then
    PKG_LINENUM=`expr $(grep -nE "name=\"$PACKAGE\" arch=\"(noarch|x86_64)\"" $CURRENT | awk -F ":" '{print $1}') + 1`
    VER=$(awk -F"\"" 'NR=='$PKG_LINENUM' {print $4}' $CURRENT)
    REL=$(awk -F"\"" 'NR=='$PKG_LINENUM' {print $6}' $CURRENT)
    CURR_PKGVER="$VER-$REL"
    PKG_LINENUM=`expr $(grep -nE "name=\"$PACKAGE\" arch=\"(noarch|x86_64)\"" $LAST | awk -F ":" '{print $1}') + 1`
    VER=$(awk -F"\"" 'NR=='$PKG_LINENUM' {print $4}' $LAST)
    REL=$(awk -F"\"" 'NR=='$PKG_LINENUM' {print $6}' $LAST)
    LAST_PKGVER="$VER-$REL"
    echo "[INFO] Found newer $PACKAGE package ($CURR_PKGVER), triggering build"
    echo "  Package:     $PACKAGE" >> $TRIGGER_LOG
    echo "  New version: $CURR_PKGVER" >> $TRIGGER_LOG
    echo "  Old version: $LAST_PKGVER" >> $TRIGGER_LOG
    echo "" >> $TRIGGER_LOG
  fi
  # After triggering a test, save current filelist as last filelist
  cp $CURRENT $LAST

  # wget/curl to start update project on any node with the specified label
  PARAM="SLE11_SP4_KVM"
  RET=0

  if [ ${VIRT_TYPE} = "COM" ];then
    PARAM="${OS_VER}_${SP_VER}_KVM,${OS_VER}_${SP_VER}_XEN"
    RET=5
  elif [ ${VIRT_TYPE} = "XEN" ];then
    PARAM="${OS_VER}_${SP_VER}_XEN"
    RET=3
  elif [ ${VIRT_TYPE} = "KVM" ];then
    PARAM="${OS_VER}_${SP_VER}_KVM"
    RET=1
  fi
  #wget -O - -q "$JENKINS_URL/job/zzTesting/job/01_update_slave/buildWithParameters?LABEL=${OS_VER}_${SP_VER}" > /dev/null
  wget -O - -q  "$JENKINS_URL/job/VIRTUALIZATION/job/01_InstallingGuest/job/02_execute_test/buildWithParameters?PRODUCT=${PARAM}&UPGRADE=NO" > /dev/null
  echo "$PARAM should be trigger"
  return $RET
}


#### main enterance ####

if [[ -n "$1" && -n "$2" ]];then
        OS_LIST=`echo $1 | tr [:lower:] [:upper:] | sed 's/,/ /g'`
        SP_LIST=`echo $2 | tr [:lower:] [:upper:] | sed 's/,/ /g'`
else
        :
fi

for DIST in $OS_LIST; do
  for PATCH in $SP_LIST; do
    eval VIRT_REPO=VIRT_${DIST}_${PATCH}
    eval TEST_REPO=VIRT_TEST_${DIST}_${PATCH}
    if [ -n "${!VIRT_REPO}" ]; then
      if ! [ -e "repo_info" ];then
          mkdir repo_info
      fi

      REPO_CURR=repo_info/repo_curr_${DIST}_${PATCH}
      REPO_LAST=repo_info/repo_last_${DIST}_${PATCH}
      # Download and store repository pkgids
      echo "[INFO] Retrieving filelist for ${DIST} ${PATCH}"
      if download_filelist ${!VIRT_REPO} $REPO_CURR; then
        if [ "$VIRT_REPO" != "$TEST_REPO" ]; then
          echo "[INFO] Retrieving filelist for ${DIST} ${PATCH} (testrepo)"
          download_filelist ${!TEST_REPO} ${REPO_CURR}_tmp
          if [ -e ${REPO_CURR}_tmp ]; then
            cat ${REPO_CURR}_tmp >> ${REPO_CURR}
            rm ${REPO_CURR}_tmp
          fi
        fi
        # generate package list
        if [ ! "${DIST/11}" = "$DIST" ]; then
          PKG_COM_LIST="$LIBVIRT11_COMN_COMPONENTS_LIST"
          PKG_XEN_LIST="$LIBVIRT11_XEN_SPECIFIC_LIST"
          PKG_KVM_LIST="$LIBVIRT11_KVM_SPECIFIC_LIST"
        else
          PKG_COM_LIST="$LIBVIRT12_COMN_COMPONENTS_LIST"
          PKG_XEN_LIST="$LIBVIRT12_XEN_SPECIFIC_LIST"
          PKG_KVM_LIST="$LIBVIRT12_KVM_SPECIFIC_LIST"
        fi
        # compare last to curr
        if [ ! -e "$REPO_LAST" ]; then
          echo "Triggering update for $DIST $PATCH: Missing previous repo filelist"
          trigger "$DIST" "$PATCH" "" "$REPO_CURR" "$REPO_LAST" "COM" "No last filelist"
        else
          P_RET=0
          for PKG_LIST in PKG_COM_LIST PKG_XEN_LIST PKG_KVM_LIST;do
              for PKG in ${!PKG_LIST}; do
                if check_for_updates $PKG $REPO_CURR $REPO_LAST; then
                  echo "Triggering update for $DIST $PATCH: Detected package change in $PKG"
                  if [ ${PKG_LIST} = PKG_COM_LIST ];then
                    trigger "$DIST" "$PATCH" "$PKG" "$REPO_CURR" "$REPO_LAST" "COM" "Detected package change"
                  elif [ ${PKG_LIST} = PKG_XEN_LIST ];then
                    trigger "$DIST" "$PATCH" "$PKG" "$REPO_CURR" "$REPO_LAST" "XEN" "Detected package change"
                  elif [ ${PKG_LIST} = PKG_KVM_LIST ];then
                    trigger "$DIST" "$PATCH" "$PKG" "$REPO_CURR" "$REPO_LAST" "KVM" "Detected package change"
                  fi
                  P_RET=$?
                  break
                fi
              done
              if [ ${P_RET} -eq 5 ];then
                break
              fi
          done
        fi
      else
        echo "Skipping update for $DIST $PATCH: No repo data found"
      fi
    else
      echo "Skipping update for $DIST $PATCH: No repo data found in repos list"
    fi
  done
done
exit 0

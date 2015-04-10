#QA repository definitions
IBS_QA="http://download.suse.de/ibs/QA:/Head:/Devel"
QA_SLE11_SP1="${IBS_QA}/SUSE_SLE-11-SP1_GA/"
QA_SLE11_SP2="${IBS_QA}/SUSE_SLE-11-SP2_GA/"
QA_SLE11_SP3="${IBS_QA}/SLE-11-SP3/"
QA_SLE11_SP4="${IBS_QA}/SLE_11_SP4/"
QA_SLE12_SP0="${IBS_QA}/SLE-12/"
QA_OS13_SP2="${IBS_QA}/openSUSE_13.2/"

#Core repository definitions
OBS="http://download.opensuse.org/repositories/Virtualization"
OBS_TEST="http://download.opensuse.org/repositories/Virtualization:/Tests"
IBS="http://download.suse.de/ibs/Devel:/Virt:"
IBS_TEST="http://download.suse.de/ibs/Devel:/Virt:/Tests"

VIRT_SLE11_SP1="${IBS}/SLE-11-SP1/SLE_11_SP1_Update"
VIRT_TEST_SLE11_SP1="${IBS_TEST}/SLE_11_SP1"
VIRT_SLE11_SP2="${IBS}/SLE-11-SP2/SLE_11_SP2_GA"
VIRT_TEST_SLE11_SP2="${IBS_TEST}/SLE_11_SP2"
VIRT_SLE11_SP3="${IBS}/SLE-11-SP3/SLE_11_SP3"
VIRT_TEST_SLE11_SP3="${IBS_TEST}/SLE_11_SP3"
VIRT_SLE11_SP4="${IBS}/SLE-11-SP4/SLE_11_SP4"
VIRT_TEST_SLE11_SP4="${IBS_TEST}/SLE_11_SP4"
VIRT_SLE12_SP0="${IBS}/SLE-12/SUSE_SLE-12_GA_standard"
VIRT_TEST_SLE12_SP0="${IBS_TEST}/SLE_12"

VIRT_OS13_SP2="${OBS}/openSUSE_13.2"
VIRT_TEST_OS13_SP2="${OBS_TEST}/openSUSE_13.2"


#Common component list for kvm and xen

L_MAIN="libvirt"
L_CLIENT="libvirt-client"
L_PYTHON="libvirt-python"
L_DAEMON="libvirt-daemon"
L_DEVEL="libvirt-devel"
L_DOC="libvirt-doc" #This package may be not necessary
L_L_SANLOCK="libvirt-lock-sanlock"

V_MANAGER="virt-manager"
V_INSTALL="vm-install"
TCK="perl-Sys-Virt-TCK"
QA="qa_test_virtualization"

## Only for sel12
L_D_DNETWORK="libvirt-daemon-driver-network"
L_D_DQEMU="libvirt-daemon-driver-qemu"
L_D_DIF="libvirt-daemon-driver-interface"
L_D_DNWFILTER="libvirt-daemon-driver-nwfilter"
L_D_DSECRET="libvirt-daemon-driver-secret"
L_D_DNODEDEV="libvirt-daemon-driver-nodedev"
L_D_DSTORAGE="libvirt-daemon-driver-storage"
L_D_QEMU="libvirt-daemon-qemu"
Q_MAIN="qemu"
LXC="libvirt-daemon-driver-lxc libcap-ng-utils"

LIBVIRT11_COMN_COMPONENTS_LIST="$L_MAIN $L_CLIENT $L_PYTHON $L_DAEMON $L_DEVEL $L_DOC $L_L_SANLOCK $V_MANAGER $V_INSTALL $TCK $QA"
LIBVIRT12_COMN_COMPONENTS_LIST="$LIBVIRT11_COMN_COMPONENTS_LIST $L_D_DNETWORK $L_D_DQEMU $L_D_DIF $L_D_DNWFILTER $L_D_DSECRET $L_D_DNODEDEV $L_D_DSTORAGE $L_D_QEMU $Q_MAIN $LXC"

#XEN specific
X_XEN="xen"
X_K_XEN="kernel-xen"
X_TOOL="xen-tools"
X_LIBS="xen-libs"
X_DEVEL="xen-devel"
X_DOC_HTML="xen-doc-html" #This package may be not necessary
X_K_DEFAULT="xen-kmp-default"
X_K_TRACE="xen-kmp-trace"
X_T_DOMU="xen-tools-domU"
#X_L_32BIT="xen-libs-32bit" #This package should not be in.

LIBVIRT11_XEN_SPECIFIC_LIST="$X_XEN $X_K_XEN $X_TOOL $X_LIBS $X_DEVEL $X_DOC_HTML $X_K_DEFAULT $X_K_TRACE $X_T_DOMU"
LIBVIRT12_XEN_SPECIFIC_LIST="$LIBVIRT11_XEN_SPECIFIC_LIST"

#KVM specific
Q_QEMU="qemu-x86"
K_KVM="kvm"
Q_TOOLS="qemu-tools" #Only for sle12
K_DEFAULT="kernel-default"
Q_G_AGENT="qemu-guest-agent"

LIBVIRT11_KVM_SPECIFIC_LIST="$Q_QEMU $K_KVM $K_DEFAULT $Q_G_AGENT"
LIBVIRT12_KVM_SPECIFIC_LIST="$LIBVIRT11_KVM_SPECIFIC_LIST $Q_TOOLS"



#LIBVIRT11_COMPONENTS_LIST="$L_MAIN $L_CLIENT $TCK $QA"
#LIBVIRT12_COMPONENTS_LIST="$L_MAIN $L_CLIENT $L_DAEMON $L_D_DNETWORK $L_D_DQEMU $L_D_DIF $L_D_DNWFILTER $L_D_DSECRET $L_D_DNODEDEV $L_D_DSTORAGE $L_D_QEMU $Q_MAIN $LXC $TCK $QA"

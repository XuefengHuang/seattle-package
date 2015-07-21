#
# Copyright (C) 2006-2011 OpenWrt.org
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=seattle
PKG_VERSION=1.0
PKG_RELEASE:=1

PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)
PKG_INSTALL_DIR:=$(PKG_BUILD_DIR)/ipkg-install

include $(INCLUDE_DIR)/package.mk

define Package/seattle
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Seattle Testbed
  URL:= https://seattle.poly.edu/html/
  DEPENDS:=+python +libpthread +zlib +libffi
endef

define Package/seattle/description
        Seattle is a platform for networking and distributed systems research.
        Seattle runs on end-user systems in a safe and contained manner, with 
        support for several platforms. Users install and run Seattle with minimal 
        impact on system security and performance. Sandboxes are established on the 
        user's computer to limit the consumption of resources such as CPU, memory, storage 
        space, and network bandwidth.
endef

define Build/Compile

endef

define Package/seattle/install
	$(INSTALL_DIR) $(1)/root/seattle
	$(CP) -r ./files/seattle/* $(1)/root/seattle
	$(INSTALL_DIR) $(1)/etc/init.d
	$(CP) ./files/etc/init.d/seattle $(1)/etc/init.d/seattle         
endef

define Package/seattle/postinst
#!/bin/sh
if [ -z "$${IPKG_INSTROOT}" ]; then
	chmod +x /etc/init.d/seattle
	/etc/init.d/seattle enable
	$(1)/root/seattle/install.sh --percent 40
fi
         
endef

define Package/seattle/prerm
#!/bin/sh
$(1)/root/seattle/uninstall.sh
rm -r $(1)/root/seattle/
rm $(1)/etc/init.d/seattle
rm $(1)/etc/rc.d/S99seattle
endef

$(eval $(call BuildPackage,seattle))

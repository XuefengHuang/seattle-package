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
  DEPENDS:=+python +libpthread +zlib +libffi +coreutils-nohup
endef

define Build/Compile
endef

define Package/seattle/install
	$(INSTALL_DIR) $(1)/root/seattle
	$(CP) -r ./files/* $(1)/root/seattle
endef

$(eval $(call BuildPackage,seattle))

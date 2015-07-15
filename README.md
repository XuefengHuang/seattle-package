# Seattle-OpenWRT

[Seattle](https://seattle.poly.edu/html/) is an
open research and educational testbed that utilizes computational
resources provided by end users on their existing devices.
This project offers an OpenWRT package for Seattle.

# How to create an OpenWRT package for Seattle
### 1. Get OpenWRT SDK
barrier_breaker: https://downloads.openwrt.org/barrier_breaker/14.07/ar71xx/generic/ <br />
chaos_calmer: https://downloads.openwrt.org/chaos_calmer/15.05-rc2/ar71xx/generic/ <br />
Then you need to extract the tarball.

### 2. Download Seattle codes and Makefile
Assuming that your SDK parent(root) directory is as below
`OpenWrt-SDK-ar71xx-for-linux-x86_64-gcc-4.8-linaro_uClibc-0.9.33.2`

<pre>
cd OpenWrt-SDK-ar71xx-for-Linux-i686-gcc-4.3.3+cs_uClibc-0.9.30.1/package
git clone https://github.com/XuefengHuang/seattle-package.git
mv seattle-package seattle
</pre>

### 3. Execute make
Now, go to your OpenWRT SDK directory and simply execute 'make', then all build start.

<pre>
cd ..
make clean && make world
</pre>

If you get errors like `awk: include/scan.awk: line 21: function asort never defined`, you need to install `gawk`.

### 4. Check package
When your build is sucessfully completed, You can find the build package (seattle_1.0-1_ar71xx.ipk) in below folder
`OpenWrt-SDK-ar71xx-for-linux-x86_64-gcc-4.8-linaro_uClibc-0.9.33.2/bin/ar71xx/packages`(barrier_breaker) or `OpenWrt-SDK-ar71xx-for-linux-x86_64-gcc-4.8-linaro_uClibc-0.9.33.2/bin/ar71xx/packages/base`(chaos_calmer)

### 5. Copy your package to Router
Copy this ipk package (in this example seattle_1.0-1_ar71xx.ipk file) to router by any useful tool such as SCP.

### 6. Install your package
<pre>
opkg install seattle_1.0-1_ar71xx.ipk
</pre>

### 7. Uninstall your package
<pre>
opkg remove seattle
</pre>

# Build an OpenWRT image include Seattle
These steps were tested using OpenWRT-"Barrier Breaker" (14.07):
For building OpenWrt on Debian, you need to install these packages:
<pre>
apt-get install git subversion g++ libncurses5-dev gawk zlib1g-dev build-essential gettext unzip file
</pre>
Now build OpenWrt:
<pre>
git clone git://git.openwrt.org/14.07/openwrt.git
cd openwrt

./scripts/feeds update -a
./scripts/feeds install -a

git clone https://github.com/XuefengHuang/seattle-package.git
mv seattle-package seattle
cp -rf seattle/ package/
rm -rf seattle/

make defconfig
make menuconfig
</pre>

At this point select the appropiate "Target System" and "Target Profile" depending on what target chipset/router you want to build for. Also mark the Seattle package under "Network". You also need to mark the dependencies, such as python, libpthread...

Now compile/build everything:
<pre>
make
</pre>

The images and all *.ipk packages are now inside the bin/ folder. You can install the Seattle .ipk using "opkg install <ipkg-file>" on the router.

For details please check the OpenWRT documentation.

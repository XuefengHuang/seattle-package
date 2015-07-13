# Seattle-OpenWRT

[Seattle](https://seattle.poly.edu/html/) is an
open research and educational testbed that utilizes computational
resources provided by end users on their existing devices.
This project offers an OpenWRT package for Seattle.

# How to create an OpenWRT package for Seattle
### 1. Get OpenWRT SDK
barrier_breaker: https://downloads.openwrt.org/barrier_breaker/14.07/ar71xx/generic/ <br />
chaos_calmer: https://downloads.openwrt.org/chaos_calmer/15.05-rc2/ar71xx/generic/ <br />
Then you need to extract the tar ball.

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

### 4. Check package
When your build is sucessfully completed, You can find the build package (seattle_1.0-1_ar71xx.ipk) in below folder
`OpenWrt-SDK-ar71xx-for-linux-x86_64-gcc-4.8-linaro_uClibc-0.9.33.2/bin/ar71xx/packages`

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

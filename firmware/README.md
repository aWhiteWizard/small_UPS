# firmware/ — STM32 固件与开发环境（T-0022 工具链 / T-0023 HAL+占位 MCU）

本目录已落地 STM32 固件开发环境：交叉编译工具链、CMSIS + HAL、CMake/Ninja 构建、
OpenOCD 烧写调试链路、串口工具，以及一个可编译出 `.elf/.bin/.hex` 的最小点灯工程。
本单（T-0023）补齐 HAL/LL 集成、仓库内可审阅的启动文件、带注释的链接脚本与 HAL 配置。
工具链与 SDK 只落在本机 `<repo>/.tools/`，**不入库**（见根 `.gitignore` 的 `.tools/`）。

> 拆单归属（2026-11-18）：T-0022 负责工具链与构建（§2–§4 的环境部分）；T-0023 负责 HAL/占位 MCU、启动文件、链接脚本与 HAL 配置（§4–§6）；T-0024 负责烧写/串口与从零复现。现有底座由母单 T-0002 落地。

## 1. 状态与范围

- 目标 MCU：**型号待定**；本单按占位型号 **STM32G071KBUx**（Cortex-M0+，128 KiB Flash / 36 KiB SRAM，UFQFPN32）跑通。
- 已验证：HAL/CMSIS 集成、本地启动文件、链接脚本布局断言、CMake 配置、编译、链接、`.bin/.hex` 生成、ELF/向量表检查。
- **未验证**：真实开发板烧写/点灯。本执行环境没有 ST-Link 与目标板，`flash.ps1` 只做链路与命令落地。
- 本工程不实现 PSU 控制、I2C、保护逻辑；这些留给后续固件工单。

## 2. 环境清单（Windows 10/11 x64）

所有组件由 `firmware/tools/bootstrap.ps1` 安装到 `<repo>/.tools/`，不写系统 PATH、不改注册表。

| 组件 | 固定版本 | 安装包 / 落盘路径 | 版本校验命令 |
|---|---|---|---|
| arm-none-eabi-gcc | 15.2.1（xPack 15.2.1-1.1） | `xpack-arm-none-eabi-gcc-15.2.1-1.1-win32-x64.zip` → `.tools\arm-gcc\` | `.tools\arm-gcc\bin\arm-none-eabi-gcc.exe --version` |
| CMSIS Core | v5.9.0 | `git clone --branch v5.9.0` → `.tools\stm32cube\cmsis_core` | `git -C .tools\stm32cube\cmsis_core describe --tags` |
| CMSIS Device G0 | v1.4.5 | `git clone --branch v1.4.5` → `.tools\stm32cube\cmsis_device_g0` | `git -C .tools\stm32cube\cmsis_device_g0 describe --tags` |
| STM32G0 HAL | v1.4.7 | `git clone --branch v1.4.7` → `.tools\stm32cube\stm32g0xx_hal_driver` | `git -C .tools\stm32cube\stm32g0xx_hal_driver describe --tags` |
| CMake | 3.31.9 | `xpack-cmake-3.31.9-1-win32-x64.zip` → `.tools\cmake\` | `.tools\cmake\bin\cmake.exe --version` |
| Ninja | 1.13.2 | `ninja-win.zip` → `.tools\ninja\ninja.exe` | `.tools\ninja\ninja.exe --version` |
| OpenOCD（ST-Link/SWD） | 0.12.0+dev（xPack v0.12.0-7） | `xpack-openocd-0.12.0-7-win32-x64.zip` → `.tools\openocd\` | `.tools\openocd\bin\openocd.exe --version` |
| PuTTY（串口终端） | 0.85 | `putty.exe`（官方 latest/w64）→ `.tools\putty\putty.exe` | `(Get-Item .tools\putty\putty.exe).VersionInfo.ProductVersion` |
| ST-Link USB 驱动 | STSW-LINK009（真实硬件才需要） | ST 官网安装包，默认 `C:\Program Files (x86)\STMicroelectronics\` | 设备管理器出现 `STMicroelectronics STLink`；无板时不适用 |
| Git / curl / tar | Windows 自带 curl/tar；Git 需预装 | 系统 `PATH` | `git --version`；`curl.exe --version`；`tar.exe --version` |

说明：

- `arm-none-eabi-g++/gdb/objcopy/size/readelf/nm` 随同一 GCC 包提供，无需单独安装。
- OpenOCD 脚本目录为 `.tools\openocd\openocd\scripts\`（xPack 包布局），`flash.ps1` 已自动带 `-s`。
- 本机实测版本行：`arm-none-eabi-gcc.exe (xPack GNU Arm Embedded GCC x86_64) 15.2.1 20251203`。
- 一键逐项校验（只读，不下载、不连硬件）：`powershell -ExecutionPolicy Bypass -File firmware/tools/check-env.ps1`，exit 0 表示上表固定版本全部命中。

## 3. 从零复现（命令原文）

前置：Windows 10/11 x64、Git，能访问 GitHub；下载约 360 MB，解压后 `.tools/` 约 1.9 GB。

```powershell
# 在仓库根目录执行
powershell -ExecutionPolicy Bypass -File firmware/tools/bootstrap.ps1

# 编译
powershell -ExecutionPolicy Bypass -File firmware/build.ps1

# 需要清空 build/ 时
powershell -ExecutionPolicy Bypass -File firmware/build.ps1 -Clean
```

- `bootstrap.ps1` 幂等：已存在的组件跳过；`-Force` 强制重下重装；`-ToolsDir <path>` 改工具根目录。
- `build.ps1` 只在当前进程内把 `.tools\arm-gcc\bin`、`.tools\cmake\bin`、`.tools\ninja` 前置到 `PATH`。
- 工具链与 HAL 版本都写死在 `bootstrap.ps1` 的 URL/tag 中；不要用 `latest` 保证可复现。
- 脚本为 ASCII-only，Windows PowerShell 5.1 可直接解析（无 BOM 的 UTF-8 中文脚本在 5.1 下会乱码报错）。

## 4. 最小工程与构建结果

源文件：

```text
firmware/
├── CMakeLists.txt                      # 构建入口（C + ASM）
├── cmake/arm-none-eabi-gcc.cmake       # 交叉编译工具链文件
├── linker/STM32G071KBUx_FLASH.ld       # 占位型号链接脚本（128K/36K，带布局断言）
├── startup/startup_stm32g071xx.s       # 本地启动文件（向量表/复位/weak 别名）
├── include/stm32g0xx_hal_conf.h        # 最小 HAL 模块集
├── src/main.c                          # PA5 1 Hz 翻转
├── src/stm32g0xx_it.c                  # SysTick -> HAL_IncTick
├── build.ps1 / flash.ps1
└── tools/bootstrap.ps1
```

构建配置：`-mcpu=cortex-m0plus -mthumb -mfloat-abi=soft -Os -g3`，链接
`-specs=nano.specs -specs=nosys.specs -Wl,--gc-sections`。

HAL 子集：`stm32g0xx_hal.c` / `hal_cortex.c` / `hal_gpio.c` + CMSIS `system_stm32g0xx.c`；
LL 头文件随 HAL 包提供（header-only），当前点灯只用 HAL，后续可直接 include
`stm32g0xx_ll_*.h`，不需要额外 `.c` 或配置开关。

实测输出（2026-11-18，本机）：

```text
TOOLCHAIN: arm-none-eabi-gcc.exe (xPack GNU Arm Embedded GCC x86_64) 15.2.1 20251203
CMAKE:     cmake version 3.31.9
NINJA:     1.13.2
...
[8/8] Linking C executable psu_minimal.elf
Memory region         Used Size  Region Size  %age Used
             RAM:        1584 B        36 KB      4.30%
           FLASH:        1544 B       128 KB      1.18%
   text    data     bss     dec     hex filename
   1524      20    1572    3116     c2c .../build/psu_minimal.elf
```

产物：

| 文件 | 大小 | 说明 |
|---|---|---|
| `firmware/build/psu_minimal.elf` | 665,456 B | 含调试信息（本地启动文件路径使 ELF 略大） |
| `firmware/build/psu_minimal.bin` | 1,544 B | 与 FLASH Used Size 一致 |
| `firmware/build/psu_minimal.hex` | 4,426 B | Intel HEX |

自检：`.bin` 前 8 字节 `00 90 00 20 75 02 00 08`，即初始 SP=`0x20009000`、
Reset_Handler=`0x08000275`（Thumb 位）；`.isr_vector` 位于 `0x08000000`、大小 `0xbc`（188 B），
`.text` 从 `0x080000bc` 开始；ELF 为 2 个 LOAD 段（R E / RW），无 RWX 段。

## 5. 烧写、调试与串口

真实硬件接线：ST-Link 的 SWDIO/SWCLK/GND/3V3 接目标板对应脚，BOOT0 拉低。

```powershell
# 一键烧写（需要先接 ST-Link 与目标板）
powershell -ExecutionPolicy Bypass -File firmware/flash.ps1

# flash.ps1 等价的 OpenOCD 原文
.\.tools\openocd\bin\openocd.exe -s .\.tools\openocd\openocd\scripts `
  -f interface/stlink.cfg -f target/stm32g0x.cfg `
  -c "program firmware/build/psu_minimal.elf verify reset exit"
```

- 调试：先 `openocd ... -c "gdb_port 3333"`，再 `arm-none-eabi-gdb firmware/build/psu_minimal.elf`，
  GDB 内 `target extended-remote :3333`。
- 串口：`.\.tools\putty\putty.exe -serial COM3 -sercfg 115200,8,n,1,X`。
  当前最小工程**没有初始化 UART**，PuTTY 只是工具链就绪证明，串口输出待后续工单。
- 本环境无硬件，上述烧写命令未实际执行；OpenOCD 版本与脚本路径已校验。

## 6. 启动文件、链接脚本与占位型号切换点

### 6.1 启动文件与向量表（`firmware/startup/startup_stm32g071xx.s`）

- 本地维护的 CMSIS 模板副本（STM32CubeG0 v1.4.5，Apache-2.0，文件头保留版权），
  增加中文注释与 `WEAK_DEFAULT` 宏；复位流程、向量表顺序与模板一致。
- 向量表 `.isr_vector` 位于 FLASH 起始 `0x08000000`（`_svector`，188 B = 47 字）：
  第 0 字 `_estack=0x20009000`（初始 MSP），第 1 字 `Reset_Handler`（Thumb），
  之后是 16 个系统向量 + 31 个 IRQ；未实现中断弱别名到 `Default_Handler` 死循环。
- 复位流程：设 MSP → `SystemInit()` → `.data` 从 `_sidata` 复制到 RAM → `.bss` 清零
  → `__libc_init_array()` → `main()`。`SysTick_Handler` 由 `src/stm32g0xx_it.c` 强符号覆盖。
- 从主 Flash 启动（BOOT0 拉低）时 VTOR=0，G0 的 `MEM_MODE=00` 将主 Flash 映射到
  `0x00000000`，故 CPU 从 0 地址看到的就是 `0x08000000` 处的同一张表；以后加
  bootloader/改 VTOR 时应显式设为 `0x08000000`。

### 6.2 链接脚本内存布局（`firmware/linker/STM32G071KBUx_FLASH.ld`）

| 区域 | 地址 / 大小 | 说明 |
|---|---|---|
| FLASH | 0x08000000 / 128 KiB | `.isr_vector` 固定在最前，后接 `.text/.rodata/.ARM*/.init_array` 与 `.data` 初值 |
| SRAM | 0x20000000 / 36 KiB | `.data` VMA → `.bss` → 最小堆 0x200 + 栈 0x400 保留区 |
| `_estack` | 0x20009000 | RAM 顶端、向量表[0]、初始 MSP，向下增长 |

- `_sidata` 是 `.data` 在 FLASH 的 LMA；`_sdata/_edata`、`_sbss/_ebss` 供启动文件使用。
- 文末 `ASSERT(_svector == ORIGIN(FLASH))` 与 `ASSERT(_estack == ORIGIN(RAM)+LENGTH(RAM))`
  在链接期锁定向量表位置和初始 MSP；改内存布局若破坏契约会直接链接失败。
- `.isr_vector`/`.text` 走 `PT_LOAD FLAGS(5)`（R+X），`.data/.bss` 走 `FLAGS(6)`（RW），
  避免新版 ld 的 RWX 警告。

### 6.3 占位型号与切换点（型号待定）

当前按 **STM32G071KBUx**（Cortex-M0+，128 KiB Flash / 36 KiB SRAM，UFQFPN32）跑通；
需求尚未冻结 MCU 型号。换正式型号时按下表逐项切换，缺一项会链接失败或跑飞：

| # | 切换点 | 文件 | 要改什么 |
|---|---|---|---|
| 1 | 链接脚本 | `firmware/linker/STM32G071KBUx_FLASH.ld` | `MEMORY` 的 FLASH/RAM 起始与容量；可随封装改文件名，并同步 `CMakeLists.txt` 的 `LINKER_SCRIPT` |
| 2 | 启动文件 | `firmware/startup/startup_stm32g071xx.s` | `.cpu`（G0=cortex-m0plus，G4=cortex-m4）、向量表条目/IRQ 表、复位流程；文件名与 `CMakeLists.txt` 的 `STARTUP` 同步 |
| 3 | 设备宏/内核 | `firmware/CMakeLists.txt` | `STM32G071xx` → 新系列宏；`-mcpu`/`-mfloat-abi`（G4 带 FPU 时补 `-mfpu`） |
| 4 | HAL 配置 | `firmware/include/stm32g0xx_hal_conf.h` | 模块开关（当前 CORTEX/FLASH/GPIO/RCC）、HSE/HSI/LSE 值与启动超时；换系列时模板改为 `stm32gXxx_hal_conf.h` |
| 5 | HAL/CMSIS 包 | `firmware/tools/bootstrap.ps1` | `cmsis_device_g0` / `stm32g0xx_hal_driver` 仓库与 tag；换系列时改为 `cmsis_device_g4` / `stm32g4xx_hal_driver` |
| 6 | 引脚/时钟 | `firmware/src/main.c`、`firmware/src/stm32g0xx_it.c` | LED 引脚（占位 PA5）与时钟；PSU 的 EN/ALERT/I2C 以冻结针脚表为准 |

> 风险：需求 §4.2.6 提到调试板 USB-C 走 STM32G431 内置 USB FS；若最终选 G431CB，
> 除上表外还要换 G4 HAL 包、启用 USB 时钟/引脚，并重新核对 Flash/SRAM 容量。

## 7. 仓库体积与忽略规则

```text
git check-ignore -v .tools\arm-gcc\bin\arm-none-eabi-gcc.exe
  .gitignore:16:.tools/   ".tools\\arm-gcc\\bin\\arm-none-eabi-gcc.exe"
git check-ignore -v firmware\build\psu_minimal.elf
  .gitignore:14:build/    "firmware\\build\\psu_minimal.elf"
```

- `.tools/` 实测约 1.9 GB、`firmware/build/` 约 5 MB，均在 git 外；跟踪文件数/仓库体积以
  `git ls-files | Measure-Object -Line` 与 `git count-objects -vH` 实测为准（T-0022 的
  167/246 KiB 是母单落地时快照，后续 .agent 证据入库会增加）。
- 入库只有配置/源码/文档；`git ls-files` 中无 `.exe/.a/.o/.elf/.bin/.hex`。
- 完整证据见 `.agent/evidence/T-0023-p0-*.txt`（本单）；T-0022/T-0002 证据仅追溯。

## 8. 已知限制

- 无目标板，未做上板点灯与烧写验证；烧写链路只到工具/脚本/命令层。
- 启动文件是本地维护副本；升级 CMSIS Device G0 包时需比对模板的向量表/新增 IRQ，不能只改 HAL tag。
- 时钟保持复位默认 HSI 16 MHz，未配 PLL；HAL 只启用 CORTEX/FLASH/GPIO/RCC 头文件与 3 个 `.c`。
- 链接期 newlib 会报 `_close/_lseek/_read/_write is not implemented` 警告，这是 `nosys.specs`
  的预期行为（本工程不使用这些系统调用）。
- 首次构建必须联网拉取固定版本工具链/HAL；离线机器需预先准备 `.tools/` 缓存。

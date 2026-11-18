# firmware/ — STM32 固件与开发环境（T-0022 工具链 / T-0023 HAL+占位 MCU / T-0024 烧写串口与复现）

本目录已落地 STM32 固件开发环境：交叉编译工具链、CMSIS + HAL、CMake/Ninja 构建、
OpenOCD 烧写调试链路、串口工具，以及一个可编译出 `.elf/.bin/.hex` 的最小点灯工程。
工具链与 SDK 只落在本机 `<repo>/.tools/`，**不入库**（见根 `.gitignore` 的 `.tools/`）。

> 拆单归属（2026-11-18）：T-0022 负责工具链与构建（§2–§4 的环境部分）；T-0023 负责 HAL/占位 MCU、启动文件、链接脚本与 HAL 配置（§4–§6）；T-0024 负责烧写/串口与从零复现。现有底座由母单 T-0002 落地。

## 1. 状态与范围

- 目标 MCU：**型号待定**；本单按占位型号 **STM32G071KBUx**（Cortex-M0+，128 KiB Flash / 36 KiB SRAM，UFQFPN32）跑通。
- 已验证：HAL/CMSIS 集成、本地启动文件、链接脚本布局断言、CMake 配置、编译、链接、`.bin/.hex` 生成、ELF/向量表检查；OpenOCD 可执行、ST-Link 接口与 `stm32g0x` 目标脚本路径存在；串口枚举/自检脚本可用。
- **未验证**：真实开发板烧写/点灯/复位。本执行环境没有 ST-Link 与目标板（`usbipd list` 无 ST-Link，COM 端口为 0）；`flash.ps1` 真实运行时在 `Error: open failed` 处明确失败，不会伪装成功。
- 串口：占位工程**没有初始化 UART**，因此没有目标板输出可读；`serial.ps1` 只完成端口枚举、打开/读取/时间戳与无硬件自检，UART 输出待后续固件工单。

| 验收项 | 状态 | 证据 |
|---|---|---|
| 工具链 / 构建 | 已验证 | `check-env.ps1` 10/10、`build.ps1 -Clean` exit 0 |
| ST-Link/OpenOCD 命令 | 已执行，未接板失败 | OpenOCD 0.12.0 输出 `Error: open failed`（§5.3） |
| 串口工具 | 自检通过，本机 0 端口 | `serial.ps1 -List` / `-SelfTest`（§5.4） |
| 上板点灯 / 复位运行 | 未验证（缺硬件） | 需接 ST-Link + STM32G071 后重跑 `flash.ps1` |

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
| 串口读取/枚举 | Windows PowerShell 5.1 内置 `System.IO.Ports` | 仓库脚本 `firmware/tools/serial.ps1`（无需安装） | `powershell -File firmware/tools/serial.ps1 -List` |
| ST-Link USB 驱动 | STSW-LINK009（真实硬件才需要） | ST 官网安装包，默认 `C:\Program Files (x86)\STMicroelectronics\` | 设备管理器出现 `STMicroelectronics STLink`；无板时不适用 |
| Git / curl / tar | Windows 自带 curl/tar；Git 需预装 | 系统 `PATH` | `git --version`；`curl.exe --version`；`tar.exe --version` |

说明：

- `arm-none-eabi-g++/gdb/objcopy/size/readelf/nm` 随同一 GCC 包提供；OpenOCD 脚本目录为
  `.tools\openocd\openocd\scripts\`（xPack 布局），`flash.ps1` 已自动带 `-s`。
- 一键逐项校验（只读，不下载、不连硬件）：`powershell -ExecutionPolicy Bypass -File firmware/tools/check-env.ps1`，exit 0 表示上表固定版本及 `System.IO.Ports`、OpenOCD 的 `stlink.cfg`/`stm32g0x.cfg` 全部命中（10/10）。

## 3. 从零复现（Windows 10/11 x64）

### 3.1 安装包与路径约定

| 组件 | 安装包 / 获取方式 | 默认路径 | 是否必需 |
|---|---|---|---|
| Git for Windows | `Git-2.x-64-bit.exe`（git-scm.com） | `C:\Program Files\Git\cmd\git.exe` | 必需（clone、拉 CMSIS/HAL） |
| Windows PowerShell | 系统自带 5.1 | `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe` | 必需 |
| ARM GCC / CMake / Ninja / OpenOCD / PuTTY | `firmware/tools/bootstrap.ps1` 固定 URL 下载 | `<repo>\.tools\...` | 必需（脚本自动装） |
| ST-Link USB 驱动 | STSW-LINK009（ST 官网） | `C:\Program Files (x86)\STMicroelectronics\` | 仅真实烧写 |
| 目标板 | STM32G071KBUx（或后续定版 MCU） + SWD 排针 | — | 仅真实烧写 |

- 下载约 360 MB；`.tools/` 解压后约 1.9 GB；`firmware/build/` 约 5 MB。三者均在 git 外。
- 不需要 Python、Java、Keil、STM32CubeIDE；不写系统 PATH、不改注册表。

### 3.2 从零命令（复制即可）

```powershell
git clone https://github.com/aWhiteWizard/small_UPS.git small_UPS
cd small_UPS
git checkout master

# 1) 下载并解压固定版本工具链/CMSIS/HAL/OpenOCD/PuTTY 到 .tools\（幂等）
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/bootstrap.ps1

# 2) 逐项校验（不连硬件）：期望 10/10、CHECK-ENV: PASS、exit 0
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/check-env.ps1

# 3) 编译：期望 [8/8] Linking C executable psu_minimal.elf、exit 0
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/build.ps1 -Clean

# 4) 空跑烧写命令（不需要接板）
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/flash.ps1 -DryRun
```

真实上板：按 §5.1 接好 ST-Link 与目标板，再执行 `powershell -NoProfile -ExecutionPolicy Bypass -File firmware/flash.ps1`。

### 3.3 环境变量与 PATH

- 不要求系统环境变量：`build.ps1` 仅在子进程前置 `.tools\arm-gcc\bin`、`.tools\cmake\bin`、
  `.tools\ninja`；`flash.ps1` 用绝对路径调 OpenOCD 并 `-s` 指定脚本目录，无需 `OPENOCD_SCRIPTS`。
- 自定义工具根：`bootstrap.ps1 -ToolsDir D:\tools\psu` + `check-env.ps1 -ToolsDir ...`；默认 `<repo>\.tools`。
- 代理：在 bootstrap 窗口设 `HTTP_PROXY`/`HTTPS_PROXY`；首次 clone 后 `.tools/`、`firmware/build/`
  不存在正常，由脚本生成。

### 3.4 复现判定

1. `check-env.ps1` 最后一行 `CHECK-ENV: PASS` 且 10 行全 `True`。
2. `build.ps1 -Clean` 最后出现 `[8/8] Linking C executable psu_minimal.elf`，并列出
   `psu_minimal.elf/.bin/.hex`。
3. `flash.ps1 -DryRun` 打印 `FLASH: DRYRUN` 与完整 OpenOCD 命令。
4. 接板后 `flash.ps1` 出现 `** Programming Finished **`、`** Verified OK **`、
   `** Resetting Target **`，最后 `FLASH: PASS`、exit 0（本机无板，见 §5.3）。

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
├── build.ps1 / flash.ps1               # 构建 / 烧写+校验+复位+日志
└── tools/
    ├── bootstrap.ps1                   # 固定版本工具链/CMSIS/HAL/OpenOCD/PuTTY
    ├── check-env.ps1                   # 10 项只读校验（含串口 API/OpenOCD 配置）
    └── serial.ps1                      # COM 枚举、读取、时间戳日志、自检
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

### 5.1 接线与供电

| ST-Link | 目标板（SWD 排针） | 说明 |
|---|---|---|
| SWDIO | SWDIO | 必须 |
| SWCLK | SWCLK | 必须 |
| GND | GND | **必须共地** |
| 3V3 | 3V3（参考） | 仅作电平参考；目标板是否由 ST-Link 供电以板子电流为准，禁止反灌 |
| NRST（可选） | NRST | 复位异常时接；OpenOCD 默认用 SYSRESETREQ |

BOOT0 拉低（从主 Flash 启动）；目标板 3.3 V 电平；上电前确认无短路。SWD 排针只用于首烧/救援（需求 §3.5.10），不要从面板引出。

### 5.2 烧写命令与成功标志

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/flash.ps1 -DryRun

# 接板后真实烧写：program + verify + reset + exit
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/flash.ps1
```

`flash.ps1` 等价的 OpenOCD 原文（脚本会自动加引号并写日志）：

```powershell
.\.tools\openocd\bin\openocd.exe -s .\.tools\openocd\openocd\scripts `
  -f interface/stlink.cfg -f target/stm32g0x.cfg `
  -c "program {firmware\build\psu_minimal.elf} verify reset exit"
```

接板成功时应看到（具体行随 OpenOCD 版本略有差异）：
`Info : STLINK ...`、`Info : Target voltage: ...`、`Info : [stm32g0x.cfg:...]`、
`** Programming Started **`、`** Programming Finished **`、`** Verified OK **`、
`** Resetting Target **`，脚本最后输出 `FLASH: PASS`、exit 0。原始日志在
`firmware/build/flash-<时间戳>.log`（git 忽略）。

### 5.3 本机实测（无 ST-Link / 无目标板，不能冒充成功）

本执行环境 `usbipd list` 只有触摸板/蓝牙/摄像头，无 ST-Link；`serial.ps1 -List` 为 0 端口。按 §5.2 真实运行 `flash.ps1` 的实际输出（原文，exit 1）：

```text
xPack Open On-Chip Debugger 0.12.0+dev-02228-ge5888bda3-dirty (2025-10-04-22:44)
Warn : DEPRECATED: auto-selecting transport "swd (dapdirect)". ...
Error: open failed
** OpenOCD init failed **
FLASH: FAIL (no ST-Link probe or target board detected)
```

结论：命令、OpenOCD、ST-Link 接口与 `stm32g0x` 目标脚本均正确加载；**失败点是 USB 探针未插入**。验收 #1 的「识别到芯片/写入成功/复位运行」必须在接板后重跑并保留日志，本机不能判定通过。

### 5.4 串口工具与占位工程说明

```powershell
# 枚举 COM（无板时应为 0）
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -List

# 读 10 秒，逐行加时间戳并写 firmware/build/serial-*.log
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -Port COM3 -Seconds 10

# 发一行再读（例如后续命令协议）
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -Port COM3 -Send "ping" -Seconds 3

# 无硬件自检：验证枚举/格式化/退出码，不打开串口
powershell -NoProfile -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -SelfTest
```

**占位工程无需串口的理由**：当前 `src/main.c` 只做 PA5 1 Hz 翻转，未初始化 USART；需求中 UART（B28/B29）是后续本体↔调试板协议通道。因此本单不能“读到目标板输出”，只验证 PC 侧工具（枚举、打开、读取、时间戳、日志、无硬件自检），UART 输出待后续固件工单。

### 5.5 GDB 调试

```powershell
# 终端 A：OpenOCD 常驻（不烧写）
.\.tools\openocd\bin\openocd.exe -s .\.tools\openocd\openocd\scripts `
  -f interface/stlink.cfg -f target/stm32g0x.cfg -c "gdb_port 3333"

# 终端 B（当前进程 PATH 加 .tools\arm-gcc\bin）
arm-none-eabi-gdb firmware\build\psu_minimal.elf
# (gdb) target extended-remote :3333; monitor reset halt; load; continue
```


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

- `.tools/` 实测约 1.9 GB、`firmware/build/` 约 5 MB（含 `flash-*.log`、`serial-*.log`），均在 git 外；
  跟踪文件数/仓库体积以 `git ls-files | Measure-Object -Line` 与 `git count-objects -vH` 实测为准
  （T-0022 的 167/246 KiB 是母单落地时快照，后续 .agent 证据入库会增加）。
- 入库只有配置/源码/文档；`git ls-files` 中无 `.exe/.a/.o/.elf/.bin/.hex`。
- 本单完整证据见 `.agent/evidence/T-0024-p0-*.txt`；`T-0024-p1-*.log` 与串口/烧写运行日志不入库。

## 8. 已知限制

- 本执行环境无 ST-Link、无目标板、无 COM 口：烧写实际停在 `Error: open failed`，**未完成**“识别到芯片/写入成功/复位运行”；串口只验证了 PC 侧工具与自检。需接板后重跑并保留日志。
- 占位工程未初始化 UART，因此没有目标板串口输出；UART 协议与输出属后续固件工单。
- 启动文件是本地维护副本；升级 CMSIS Device G0 包时需比对模板的向量表/新增 IRQ，不能只改 HAL tag。
- 时钟保持复位默认 HSI 16 MHz，未配 PLL；HAL 只启用 CORTEX/FLASH/GPIO/RCC 头文件与 3 个 `.c`。
- 链接期 newlib 会报 `_close/_lseek/_read/_write is not implemented` 警告，这是 `nosys.specs`
  的预期行为（本工程不使用这些系统调用）。
- 首次构建必须联网拉取固定版本工具链/HAL；离线机器需预先准备 `.tools/` 缓存。

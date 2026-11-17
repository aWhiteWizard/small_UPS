# firmware/ — 固件源码

用途：存放电源本体与调试板的 STM32 固件源码、构建脚本和单元测试。

约定：

- 本目录入库；构建产物（`build/`、`*.o`、`*.elf`、`*.bin`、`*.hex`、`*.map` 等）由根 `.gitignore` 排除。
- 工具链、HAL/LL、链接脚本与启动文件在 T-0002 落地；本单只建立目录约定。
- 源文件建议按目标划分：`firmware/psu/`（电源本体）、`firmware/debug-board/`（调试板）、`firmware/common/`（共享协议/驱动）、`firmware/tests/`（单元测试）。
- 寄存器表、故障码、针脚定义以冻结版需求文档为准，不在固件里私自定义。
- 不提交工具链二进制、SDK 整包、烧写镜像与本地 IDE 配置。

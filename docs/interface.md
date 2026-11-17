# 接口（骨架）

> 阶段：骨架占位（T-0015）；§1–§5 中填充单为 T-0006 的行已填写（2026-11-18），其余节点仍为「待填（来源：T-00xx）」。
> 填充单：T-0010（针脚/连接器设计）、T-0006（寄存器/时序/升级实现）、T-0009（主机侧时序）、T-0016（需求并章）。
> 需求关系：`.agent/requirements.md`（下称 R，v0.3 五章版）为需求唯一入口；本文档只做设计展开，不复制需求正文，冲突以需求为准。
> 引用缺口：T-0006 已把上电/掉电/使能/升级/保护/校准时序补入 R §2.4、§3.3、§3.4；D 侧主机时序仍由 T-0009 填。

## 1. 针脚表引用

| 引用项 | 需求文档章节 | 设计展开（填充单） |
|---|---|---|
| 机械与工艺基线 | R §2.1.1 | 待填（来源：T-0010） |
| 64 针定义（A/B 各 32） | R §2.1.2 | 待填（来源：T-0010） |
| 每类针用途与方向 | R §2.1.3 | 待填（来源：T-0010） |
| 插拔与短针时序 | R §2.1.4 | 见 §1.1（短针/插反检测、继电器互锁） |

### 1.1 短针与插拔检测设计

- 短针回路：B22 12V → 继电器线圈 → A23/B23 短针 → 地；短针丢失时线圈硬件失电、继电器立即释放，不依赖 MCU。MCU 检测 B22 <10V 并去抖 20ms 后锁存 SHORT_PIN_LOST；软使能同时清 0。
- 插反检测：信号/低压针 21–29 任一脚 >16V 持续 1ms → 硬件比较器拉低 EN/继电器驱动并锁存 REVERSE_INSERT；软件只上报与清位，不单独释放硬件锁存。
- 插合顺序：GND 护边 → 信号/12V → 短针。短针未到位时 SHORT_PIN=0，写 OUTPUT_ENABLE=1 被忽略并回原因；OUT_ON=1 时固件不置“可拔出”。
- 拔出前必须 RELAY_STATE=0 且 VOUT_ZERO=1；EN 丢失或短针丢失立即走 §3.2 的 S6 关断序列，禁止带电插拔。

## 2. 寄存器表引用

| 引用项 | 需求文档章节 | 设计展开（填充单） |
|---|---|---|
| 寄存器映射 | R §3.3.1 | 见 §2.1（影子/COMMIT、只读快照、保留读 0） |
| 输出状态位定义 | R §3.3.2 | 见 §2.1、§3.2（状态位 = 实际状态，不是命令回显） |
| 故障码 | R §3.3.3 | 见 §3.3（检测路径/响应时间/恢复） |
| 故障锁存位 | R §3.3.4 | 见 §3.3（硬件锁存 + 软件镜像） |
| 故障清除 | R §3.3.5 | 见 §3.3（读码→源消失→CLEAR→重新使能） |
| 关键寄存器语义 | R §3.3.6 | 见 §2.1、§3.4、§3.5 |
| 掉电保持边界 | R §3.3.7 | 见 §2.1、§5.1（仅 COMMIT 写 EEPROM） |

### 2.1 寄存器实现约束

- 地址/位定义以 R §3.3.1–§3.3.4 为唯一表，固件不另建第二张表；未列地址读 0、写忽略；保留位写 0，不得驱动 SHARE/SYNC。
- 多字节小端，16/32 位读写用临界区保证原子；V/I 设定写影子，COMMIT=0x5A 后原子切换。输出 ON 时 COMMIT 触发 §3.4 软变化，不直接跳变。
- 只读寄存器（MEAS/STATUS/FAULT/RELAY_STATE/VOUT_ZERO/版本）由 1ms 状态任务刷新快照；FAULT_CODE 取最高优先级，FAULT_FLAGS 保留全部锁存位，不因显示低优先级码丢位。
- CLEAR/OUTPUT_ENABLE/HEARTBEAT/CAL 为命令寄存器：读回 0；CLEAR 只认 0xA5、COMMIT 只认 0x5A；非法写忽略并置原因位。CLEAR 同时清软使能，输出保持 OFF。
- EEPROM 只存已 COMMIT 的 V/I 与校准表；上电恢复设定但输出 OFF。PROTOCOL_VERSION/FW_VERSION 只读，仅显示/记录，不参与升级或使能门禁。

## 3. 时序引用

| 引用项 | 需求文档章节 | 设计展开（填充单） |
|---|---|---|
| 插拔与短针时序 | R §2.1.4 | 见 §1.1 |
| ALERT 锁存/释放时序 | R §2.3.5 | 见 §3.3 |
| 输出使能主机侧时序 | 待填（来源：T-0009） | 待填（来源：T-0009）；本体侧见 §3.2 |
| 上电/掉电/保护动作时序 | R §2.4.1、§2.4.4 | 见 §3.1、§3.3 |
| 按键/页面切换时序 | 待填（来源：T-0009） | 待填（来源：T-0009） |

### 3.1 上电/自检/掉电时序

| 阶段 | 条件/动作 | 超时/判据 | 异常分支 |
|---|---|---|---|
| S0 辅助电源 | A22 12V、3.3V/5V 进入窗口，释放复位 | 300ms | 不驱动 I2C/ALERT；输出级硬件关断；无电源不上报 |
| S1 自检 | 时钟/WDG/ADC/DAC/比较器/EEPROM CRC/校准表/继电器辅助触点 | 200ms | INTERNAL 锁存、ALERT、禁输出 |
| S2 PFC | AC ≥180VAC 且无 UV/POWER_LOST；PFC_EN=1 软启动 | 2s 建 400V | <320V → PFC_FAULT（母线欠压）；AC<150 → POWER_LOST；不重试 |
| S3 LLC | PFC 稳定；LLC_EN=1 软启动 | 1s 建 55V | <50V → 母线欠压（码位待 owner：UNDERVOLTAGE/INTERNAL）；禁 buck |
| S4 READY | 无锁存故障、校准有效/恒等、设定已 COMMIT | — | 否则拒绝 OUTPUT_ENABLE，OUTPUT_STATUS 给原因 |
| S5 掉电 | AC<180 去抖 20ms / AC<150 4ms / PFC<320V / 55V<50V | ≤1ms 动作 | 禁 buck → 开继电器 → 泄放；POWER_LOST/PFC_FAULT/母线欠压；不自动输出 |

- 欠压类码位：AC 180/150VAC 均落 0x16 POWER_LOST（显示层按 AC 测量值区分欠压/掉电阶段）；PFC 母线 <320V 落 0x15 PFC_FAULT；55V 母线 <50V 的码位归属待 owner（UNDERVOLTAGE/INTERNAL）。三者动作一致：禁 buck、锁存、不自动输出。

- 上电默认：OUTPUT_ENABLE=0、RELAY_STATE=0、PFC/LLC/BUCK 全关；READY 前 I2C 只读。
- 掉电后不再写 EEPROM；辅助电源维持到关断/记录完成；恢复后必须重新走 S0–S4 与使能序列。
- 防反灌：掉电时先禁 buck，再开继电器；55V 母线加理想二极管/ORing，反灌 >0.2A/10µs 关断并锁存 REVERSE_CURRENT。

### 3.2 使能与关断状态机

| 状态 | 进入条件 | 动作 | 退出 |
|---|---|---|---|
| S0_OFF | 复位/关断完成/故障清除 | 继电器开、PWM 关、软使能 0、DAC=0 | 写 OUTPUT_ENABLE=1 → S1 |
| S1_CHECK | 收到使能命令 | 查 EN 高 ≥20ms、SHORT_PIN=1、无锁存、HB<500ms、CAL 有效/恒等、设定已 COMMIT、PFC/LLC READY | 任一失败 → S0 并回原因；全通过 → S2 |
| S2_RELAY | 检查通过 | DAC=0、Ilim=0；吸合继电器；等 RELAY_STATE=1 | ≤50ms 未闭合 → S9（RELAY_WELD/INTERNAL）；成功 → S3 |
| S3_SOFT | 继电器闭合 | buck 使能；V 从 0 按 10V/s 升到目标，I 限流同步升到目标 | 到 target±1% 或 50mV → S4；故障 → S9 |
| S4_ON | 软启动完成 | CV/CC 运行；热调子状态见 §3.4；逐周期查使能链 | 条件失效 → S6；故障 → S9；升级请求 → S10 |
| S6_SHUT | EN 低/软使能 0/短针丢失/心跳丢失/命令关断 | 禁 buck；释放继电器（命令到释放 ≤50ms）；确认 RELAY_STATE=0 | 释放成功 → S7；>50ms/粘连 → S9（RELAY_WELD） |
| S7_DISCHARGE | 继电器已开 | 针侧泄放；等 VOUT_ZERO=1 | 关断命令起 100ms 内到 1V → S0；>1V → S9（VOUT_NOT_ZERO） |
| S9_FAULT | 任一锁存故障 | 硬件关门、继电器开、软使能清、ALERT 低 | 源消失 + 读码 + CLEAR + 重新使能 → S0 |
| S10_UPGRADE | 升级请求 | EN 低、PFC/LLC/BUCK 停、继电器开 | 复位后由 bootloader 接管；完成后回 S0 |

- 使能链逐周期检查：EN、软使能、短针、无故障、心跳、设定 COMMIT、校准有效；任一失效单票否决。
- EN 高→低立即关门（≤1ms），低持续 20ms 才锁存 EN_LOST；低→高需稳定 10–50ms（默认 20ms）才允许进入 S1。硬件门不依赖 MCU。
- 继电器在输出级之后、金手指输出针之前；S2 先闭合再软启动，避免输出针带电插合；S6 先禁 buck 再释放。
- 启动前检查 VOUT_ZERO=1；预偏置/残压 >1V 时不闭合继电器，置 VOUT_NOT_ZERO/REVERSE_CURRENT，避免输出电容反灌。
- fail-safe：PFC_EN/LLC_EN/BUCK_EN 均硬件下拉，MCU 复位/死机/aux 掉电即为关断；EN 门与短针回路共同构成硬件使能门。本产品无独立急停，EN 硬件门、短针/继电器回路和外部断电是唯一安全关断路径，D 侧必须保证 EN 可拉低。

### 3.3 故障锁存与恢复

| 状态 | 含义 | 转移 |
|---|---|---|
| F0_NONE | 无锁存故障 | 任一触发 → F1 |
| F1_LATCHED | 硬件/软件锁存，输出关断，ALERT 低 | 读 FAULT_CODE + FAULT_FLAGS；源在 → F2，源消失 → F3 |
| F2_READ | 已读码，源仍存在 | 源消失 → F3；写 CLEAR 无效（源仍在） |
| F3_SOURCE_GONE | 源已消失，未 CLEAR | 写 CLEAR=0xA5 → F4；新故障 → F1（需重新读码） |
| F4_CLEARED | 锁存位清、软使能 0、输出 OFF | 重新使能 → S1_CHECK；CLEAR 不改设定/校准 |

- 硬件直拉：OVP/OCP/SCP/OTP/REVERSE_CURRENT/HEARTBEAT_LOST/SHORT_PIN_LOST/EN_LOST/REVERSE_INSERT 走比较器/定时器/门驱动，≤10µs 关断并锁存；软件检测：UNDERVOLTAGE/PFC_FAULT/POWER_LOST/RELAY_WELD/VOUT_NOT_ZERO/CAL/EEPROM/INTERNAL，≤1ms 关断并锁存。OVP 的 50µs 是确认窗口，不是关门延迟。
- 故障码优先级按 R §3.3.3：OCP/SCP > OVP > OTP > REVERSE_CURRENT > EN_LOST/HEARTBEAT_LOST > PFC_FAULT/POWER_LOST > UNDERVOLTAGE > 其它；FAULT_FLAGS 保留全部锁存位。
- 故障码对照：0x01 OCP、0x02 SCP、0x03 OVP、0x04 UNDERVOLTAGE、0x05 OTP、0x06/0x07 NTC 开/短、0x08 FAN_STALL、0x09 SHORT_PIN_LOST、0x0A EN_LOST、0x0B HEARTBEAT_LOST、0x0C REVERSE_CURRENT、0x0F RELAY_WELD、0x10 VOUT_NOT_ZERO、0x11 CAL_INVALID、0x12 EEPROM_CRC、0x13 REVERSE_INSERT、0x14 INTERNAL、0x15 PFC_FAULT、0x16 POWER_LOST；0x0D/0x0E 保留不产生。

| 码 | 故障 | 检测路径 | 关断/锁存 | 恢复 |
|---|---|---|---|---|
| 0x01 | OCP | DAC 阈值比较器 + PWM trip | ≤10µs，RS 锁存 | 源消失+读码+CLEAR+重新使能 |
| 0x02 | SCP | 8A 或 0.3V+6A 比较器 | ≤10µs | 同上 |
| 0x03 | OVP | DAC(V_ramp+2V)/50V 比较器 | ≤10µs 关门，50µs 确认 | 同上 |
| 0x04 | UNDERVOLTAGE | Vout<90% 设定 >100ms（非 CC） | ≤1ms | 恢复+CLEAR+重新使能 |
| 0x05 | OTP | NTC 比较器/软件 | 硬件 ≤10µs / 软件 ≤1ms | <80°C+CLEAR+重新使能 |
| 0x0A | EN_LOST | EN 门 | ≤1ms 关门，20ms 锁存 | EN 高+重新使能+CLEAR |
| 0x0B | HEARTBEAT_LOST | 500ms 定时器 | 硬件 ≤10µs / 软件 ≤1ms | 心跳恢复+CLEAR+重新使能 |
| 0x0C | REVERSE_CURRENT | 反灌比较器 >0.2A | ≤10µs | 消失+CLEAR |
| 0x15 | PFC_FAULT | PFC 母线<320V | ≤1ms | 源消失+CLEAR |
| 0x16 | POWER_LOST | AC<180/150VAC | ≤1ms | 恢复+CLEAR；不自动输出 |

- 不自动重试：无 hiccup/自动重合闸；故障消失后仍保持锁存，必须人工 CLEAR + 重新使能。新故障在 CLEAR 前再次置位需重新读码。
- CLEAR 后软使能=0、输出 OFF；重新使能必须重新满足 §3.2 全部条件。硬件直拉与软件置位为线与关系。

### 3.4 热调软变化状态机

| 子状态 | 进入 | 动作 | 退出 |
|---|---|---|---|
| H_IDLE | S4_ON 稳定 | 监视新 COMMIT/设定；不改变输出 | 有新目标 → H_PRECHECK |
| H_PRECHECK | 收到新 V/I | 查使能链/故障/目标范围；算斜率；预置 OVP/OCP 阈值 | 通过 → H_V_RAMP 或 H_I_RAMP；失败 → S6/S9 |
| H_V_RAMP | ΔV≠0 | 每 1ms 更新 DAC：V += 10V/s×1ms（5–20V/s 可配）；OVP 阈值 = min(50V, V_ramp+2V)；UV 屏蔽 | 到 target±1% → H_SETTLE；故障 → S9 |
| H_I_RAMP | ΔI≠0 | 增/降限 50mA/ms（5A/100ms）；降限由 CC 环平滑折叠；OCP 阈值过渡窗取 max(旧,新)+5%，窗后切新值 | 到 target±1% → H_SETTLE |
| H_SETTLE | ramp 完成 | 50ms 稳定窗；V/I 在 ±0.5%；解除 UV 屏蔽 | 稳定 → H_IDLE；新目标 → H_PRECHECK；故障 → S9 |
| H_ABORT | 使能链失效/故障/升级 | 停 ramp，走 S6/S9；不等待 ramp 完成 | 复位后回 S0_OFF |

- V 软变化：默认 10V/s，5–20V/s 可配；0.01V 步进也要按 1ms 节拍爬升，不得跳变。I 限流：增/降限均在 100ms 内平滑到目标；降限由 CC 环折叠输出，OCP 阈值过渡窗取 max(旧,新)+5%，窗后按新阈值保护，避免误触发。
- OVP 阈值随 V_ramp+2V 跟踪，绝对 50V 不变；升压/降压都不得用旧目标造成误触发。OCP 阈值 = 设定限值 + max(5%, 0.1A)，CC 在阈值以下调节。
- UV 屏蔽：软启动/热调 ramp 期间及 CC 期间屏蔽 UNDERVOLTAGE；ramp 完成后延时 100ms 再启用。不得因 ramp 误报 OVP/OCP/UV。
- 热调期间保护始终有效；进入故障立即按 §3.3 锁存，不等待 ramp 到目标。

### 3.5 继电器与残压

- 位置：继电器在输出级之后、金手指输出针之前；常开，线圈经 B22/短针回路供电，EN 门控驱动，任一丢失则硬件释放。
- 关断：禁 buck → 释放继电器（命令到释放 ≤50ms）→ 针侧泄放 → 关断命令起 100ms 内 VOUT_ZERO=1 → OUT_ON=0；100ms 后仍 >1V 置 VOUT_NOT_ZERO，ALERT，禁止宣称可拔出。
- 闭合：DAC=0、Ilim=0 → 吸合 → ≤50ms 确认 RELAY_STATE=1；辅助触点 0/1/2 与命令不一致 >50ms → RELAY_WELD，禁输出。
- 残压泄放：针侧 ≥10mA 有源泄放 + 10k 下拉，按输出针/线束电容 ≤10µF 保证 100ms 到 1V（外部负载电容不在本体保证范围，超时置 VOUT_NOT_ZERO）；输出级另设检修泄放（≥0.5A/1000µF，具体 C_out 由 T-0011 定）。
- RELAY_STATE=2（未知）按断开处理；未确认闭合不得开 buck，未确认释放不得宣称可拔。

### 3.6 CC/CV 与 OVP/OCP 协同

- CV：Vout 在设定 ±0.5% 内且 Iout < Ilim−1%；CC：电流环生效或 Iout ≥ Ilim−0.5% 持续 1ms。CV/CC 状态位互斥，CC 优先。
- CC 退出：负载减轻且 Vout 回升到 Vset−0.5% 以上、Iout < Ilim−2% 持续 20ms；滞回防抖，避免 CC/CV 频繁切换。
- OVP：DAC 阈值 = min(50V, V_ramp+2V) 与固定 50V 比较器 OR，RS 锁存直接关门；50µs 确认后置 0x03 并拉 ALERT。硬件路径不依赖 MCU。
- OCP：DAC 阈值 = Imax_set + max(5%, 0.1A)，比较器送 PWM trip，≤10µs 关断 MOS 并锁存 0x01；SCP 固定 8A 或 Vout<0.3V 且 I>6A，≤10µs 锁存 0x02。CC 不得被误判为 OCP。
- 短路/过载：保护先动作并锁存；输出短接 5s、1.2 倍额定 1min 不损坏；恢复后人工 CLEAR + 重新使能。

## 4. 升级协议引用

| 引用项 | 需求文档章节 | 设计展开（填充单） |
|---|---|---|
| 升级通道与版本策略 | R §2.4.3、§3.3.6 | 见 §4.1、§4.3（无版本门禁） |
| UART 物理层与针脚 | R §2.1.2（A28/A29）、§3.4.5 | 见 §4.1（115200 8N1，字节流） |
| 升级帧/状态机/失败恢复 | R §2.4.3 | 见 §4.1、§4.2、§4.3 |
| 升级期间输出安全状态 | R §2.4.3 | 见 §4.3（EN 低、PFC/LLC/BUCK 停、继电器开） |

### 4.1 升级帧与命令

- 物理：A28/A29，3.3V TTL，115200 8N1，无流控；调试板 USB-UART 到本体 UART 字节流直通，不解析、不改写、不因版本拒绝。任何版本组合可升级；版本只显示/记录。
- 帧：`SOF 0x7E | VER 0x01 | CMD 1 | SEQ 1 | LEN 2(LE) | PAYLOAD 0–256 | CRC16 2(LE)`；CRC16-CCITT-FALSE 覆盖 VER..PAYLOAD；0x7E/0x7D 转义为 0x7D + (byte^0x20)；最大帧 264 字节。
- 应答：ACK/NAK 同帧格式，CMD|0x80，LEN=0 或 2（状态码）；SEQ 回显。帧错/CRC 错回 NAK，主机重传同一 SEQ。
- 命令：HELLO 0x01（交换协议/固件版本与最大帧，仅记录）、ERASE 0x02（应用区长度+镜像 CRC32）、WRITE 0x03（偏移+数据）、VERIFY 0x04、GO 0x05、ABORT 0x06、INFO 0x07。
- 镜像 CRC32-IEEE 覆盖应用区；镜像头含长度/CRC32/版本（版本不参与门禁）。bootloader 只写应用区，绝不擦除自身。

### 4.2 Bootloader 状态机

| 状态 | 进入 | 动作 | 退出 |
|---|---|---|---|
| B0_BOOT | 复位 | 初始化；EN/PFC/LLC/BUCK 全关、继电器开；500ms 窗口听 HELLO/0x7F | 有请求 → B1；无请求且 app CRC 有效 → APP；CRC 无效 → B1（等主机） |
| B1_WAIT_LINK | HELLO/0x7F 或 app 无效 | 回 INFO（boot/app 版本、最大帧）；不校验版本；app 无效时停留等重传 | ERASE → B2；无请求：app 有效 → APP，无效 → 保持 B1 |
| B2_ERASE | ERASE(len,crc32) | 校验长度/地址范围；擦除应用区；失败 → B9 | 成功 → B3 |
| B3_RECEIVE | WRITE(offset,data) | 写 Flash；SEQ/CRC/范围错 NAK 重传；记录 offset | 收齐 → B4 |
| B4_VERIFY | VERIFY | 计算 CRC32，比对长度/CRC | 通过 → B5；失败 → B9 |
| B5_READY | 校验通过 | 等 GO；1s 无命令可按配置自动跳 | GO → APP；ABORT → B0 |
| B9_ERROR | 擦/写/校验失败 | 不跳应用；回 NAK/STATUS；停留 boot | 重新 HELLO/ERASE → B2 |
| APP | 应用有效 | 跳转；不清 boot；收到升级请求回 B0 | 升级请求 → B0 |

- 升级请求：应用写备份 RAM magic + 复位，或复位后 500ms 内发 0x7F/HELLO；两者都接受。
- 校验失败/擦写失败/掉电/超时：停在 bootloader 等重传，不跳无效应用；bootloader 自身完整，可反复重传。
- 应用单区：ERASE 后旧应用不可回退；失败恢复靠重传，不靠双区。boot 区 16–24KB，具体 Flash 布局随最终 MCU 由 T-0002 固化。

### 4.3 升级安全与失败恢复

- 升级期间：EN 硬件拉低（下拉 + 门驱动），PFC_EN/LLC_EN/BUCK_EN=0，继电器开；MCU 死机由 WDG 复位回 boot，引脚保持安全态。
- 失败矩阵：掉电 → 下次复位 app CRC 失败 → B0；帧错/CRC 错 → NAK 重传；Flash 写失败 → B9；VERIFY 失败 → B9；超时 → 停留 boot，不自动跳转。
- 无版本门禁：bootloader 不比较应用版本、不因调试板/本体版本不匹配拒绝升级或禁使能；PROTOCOL_VERSION/FW_VERSION 只读供显示/记录。
- 透传边界：PC ↔ 调试板 USB-UART ↔ A28/A29 ↔ 本体 bootloader；本体可被任何 D 版本升级，对 D 的升级字节只转发不解析、不设版本门禁。D 自身升级及本体转发 D 镜像的具体拓扑由 T-0009 定；P 侧保证字节通路透明。

## 5. 其他接口引用

| 引用项 | 需求文档章节 | 设计展开（填充单） |
|---|---|---|
| I2C 电气 | R §2.2.1 | 待填（来源：T-0010）；本体侧 ESD/上拉预留见 §5.2 |
| I2C 帧格式与编码 | R §2.2.2 | 见 §2.1、§5.2 |
| 地址与多机 | R §2.2.3 | 见 §5.2（0x30–0x3F，无广播） |
| ALERT 电气 | R §2.3.1 | 待填（来源：T-0010）；锁存/释放见 §3.3 |
| 校准数据接口 | R §3.4.1–§3.4.6 | 见 §5.1（状态机/限流/COMMIT） |

### 5.1 校准态状态机

| 状态 | 进入 | 动作 | 退出 |
|---|---|---|---|
| C0_IDLE | 正常运行 | 输出可在 ON/OFF；CAL 命令要求输出 OFF | BEGIN V/I → C1；否则 CAL_STATUS=7 |
| C1_ARMED | BEGIN | 确认 OUTPUT_ENABLE=0、RELAY_STATE=0、VOUT_ZERO=1；置通道限流（V 0.5A / I 目标点+1A）；屏蔽普通设定/使能 | SET/POINT → C2；ABORT/30s → C9 |
| C2_SET | SET/POINT | 校验索引/量程/递增；暂存 RAM；不写 EEPROM | MEAS → C3；ABORT → C9 |
| C3_MEAS | MEAS | 写入该点 set/meas；校验严格递增；下一点或完成 | 全部点完成 → C4；点错 → 保持当前点、CAL_STATUS=5（可重写/中止） |
| C4_READY | 全部点完成 | 等 VERSION/CRC/COMMIT；READ 可读 STATUS/ACTIVE/VERSION | COMMIT → C5；ABORT/30s → C9 |
| C5_COMMIT | COMMIT | 重算 CRC/版本/点数/温度；写非活动区、回读、切活动区 | 成功 → C6；失败 → C9（旧表不变） |
| C6_DONE | 提交成功 | CAL_STATUS=2、CAL_ACTIVE=1；输出 OFF；恢复普通命令 | 回 C0 |
| C9_ABORT | ABORT/超时/故障 | 丢弃 RAM；旧表保留；输出 OFF；清校准限流 | 回 C0 |

- 命令映射：BEGIN→CAL_CTRL 0x01/0x02；SET→CAL_INDEX+CAL_SET_POINT；MEAS→CAL_MEAS_POINT+CAL_CTRL=0x03；COMMIT→CAL_VERSION/CAL_CHECKSUM+CAL_CTRL=0x04；READ→CAL_STATUS/CAL_ACTIVE/CAL_VERSION/CAL_CHECKSUM；ABORT→CAL_CTRL=0x05。命令名映射待 owner（R 附录 E.2）。
- 校准态禁止普通设定/使能命令打断：I2C 写 V/I/OUTPUT_ENABLE 忽略/NACK，UART 回 ERR busy；READ 与 ABORT 始终允许。一次只允许一个通道，切换需先 COMMIT/ABORT。
- 限流：电压通道 0.5A；电流通道 = 目标点 +1A；OVP/OCP/OTP/反灌保护仍有效，任何故障中止会话并锁存。
- EEPROM：只有 COMMIT 写；双区 A/B，CRC16-CCITT-FALSE 按 R §3.4.3；版本单调递增、次数+1、温度采样；回读校验失败保留旧区。COMMIT 前掉电不改旧表。
- 校准输出：BEGIN 后由校准态内部使能（继电器闭合、限流生效）；COMMIT/ABORT 后立即关断、释放继电器；校准开始前必须输出 OFF。

### 5.2 并联预留与 I2C 约束

- 本版不实现多机并联均流：SHARE/SYNC 不驱动、不接；PARALLEL_MODE/CURRENT_SHARE_EN 读 0/写忽略；IMBALANCE/PARALLEL_FAULT 保留不产生；不使用广播/General Call。
- I2C 7 位地址 0x30–0x3F，拨码上电读取，运行中改变需复位；只响应本机地址；时钟拉伸 ≤10ms，SCL 低 >25ms 复位 I2C 状态机但不改变输出。
- I2C 与 UART 共用同一校准会话：同一时刻只允许一个会话，另一通道回 busy；30s 无命令自动中止且不动旧表。
- 多字节读写原子；越界/只读地址 NACK；保留寄存器读 0、写忽略。

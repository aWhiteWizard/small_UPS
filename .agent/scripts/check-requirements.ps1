# T-0003 requirements consistency check (UTF-8)
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot '..\requirements.md'
$path = [IO.Path]::GetFullPath($path)
$text = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
$lines = $text -split "`n"
$fail = 0
$total = 0
function Check([string]$name, [bool]$ok) {
    $script:total++
    if ($ok) { Write-Output ("[PASS] " + $name) }
    else { $script:fail++; Write-Output ("[FAIL] " + $name) }
}
function Has([string]$s) { return $text.Contains($s) }

Check '定位：PSU，不是 UPS，历史命名' ((Has '数控可调直流电源') -and (Has '不是 UPS') -and (Has '历史命名'))
Check '输出：0–48V 设定 / 0.5–48V 保证 / 0–5A' ((Has '0.500') -and (Has '48.000') -and (Has '0–5A') -and (Has '保证性能范围 0.5–48V'))
Check '低压原因：最小脉宽 + 跳周期' ((Has '最小脉宽') -and (Has '跳周期'))

$points = @('3.3V','5V','12V','24V','48V')
foreach ($p in $points) {
    $rows = @($lines | Where-Object { $_ -match ('^\| ' + [regex]::Escape($p) + ' \|') })
    Check ("常用工作点行 " + $p) ($rows.Count -ge 1)
}
Check '五点表含 DVT 实测列' ((Has '实测（DVT 填写）') -and (Has '待 DVT'))

$pinPatterns = @(
    '\| 1–10 \| 输出\+ \| 输出\+',
    '\| 11–20 \| 输出− \| 输出−',
    '\| 21 \| 信号地 \| 信号地',
    '\| 22 \| \+12V（本体→调试板） \| \+12V（调试板→本体继电器）',
    '\| 23 \| 短针 \| 短针',
    '\| 24 \| SDA \| SCL',
    '\| 25 \| ALERT \| EN',
    '\| 26 \| SENSE\+ \| SENSE−',
    '\| 27 \| SHARE（预留） \| SYNC（预留）',
    '\| 28 \| 备用 \| 备用',
    '\| 29 \| 备用 \| 备用',
    '\| 30–32 \| GND 护边 \| GND 护边'
)
foreach ($pat in $pinPatterns) { Check ("针脚行 " + $pat) ([bool](@($lines | Where-Object { $_ -match $pat }).Count)) }
Check '针脚：64 针 / 2.54mm / 不做防呆' ((Has '64 针') -and (Has '2.54mm') -and (Has '不做防呆'))

Check 'ALERT：低有效开漏 + 10k + 锁存 + CLEAR + 多机' ((Has '低有效开漏') -and (Has '10kΩ 上拉') -and (Has 'FAULT_CODE') -and (Has 'FAULT_FLAGS') -and (Has 'CLEAR') -and (Has '逐地址读取') -and (Has '不替代保护'))
Check '继电器：输出级之后、金手指之前、100ms/≤1V' ((Has '输出级之后、金手指输出针之前') -and (Has '100ms') -and (Has '≤1V') -and (Has '22Ω'))
Check 'RELAY_STATE / VOUT_ZERO / ≤50ms' ((Has 'RELAY_STATE') -and (Has 'VOUT_ZERO') -and (Has '≤50ms'))
Check '热替换：低于母线 100mV / PMU / 禁止绕过' ((Has '低于母线 100mV') -and (Has '流程由 PMU 实现') -and (Has '禁止绕过 PMU'))
Check 'EEPROM：只存 V/I，不存 PT100' ((Has '设定区仅保存') -and (Has 'PT100 阈值（属调试板侧）'))
Check '使能四条件 / EN 10k / 10–50ms' ((Has 'EN = 高') -and (Has 'I2C 软使能 = 1') -and (Has '短针在位') -and (Has '无故障') -and (Has '10kΩ 下拉') -and (Has '10–50ms'))
Check '心跳 100ms/500ms' ((Has '100ms') -and (Has '500ms') -and (Has 'HEARTBEAT_LOST'))
Check '按键：上拉/按下低/开关节奏/复位低' ((Has 'GPIO 上拉，按下为低') -and (Has '10–20ms') -and (Has '5–10ms') -and (Has '长按 2s') -and (Has '复位后为低'))
Check '并联：fine-trim ±50mV/1mV + 1mA + ±10% + IMBALANCE' ((Has '±50mV') -and (Has '1mV') -and (Has '1mA') -and (Has '±10%') -and (Has 'IMBALANCE') -and (Has 'PARALLEL_FAULT'))
Check '精度：20mV / ±0.1% / 0.02% / 待确认' ((Has '≤20mV') -and (Has '±0.1%') -and (Has '0.02%') -and (Has '待 owner 确认'))
Check '测量链：16 位 ADC/DAC、0.1%、INA282、2mΩ、AUTOCAL' ((Has '16 位 ΔΣ ADC') -and (Has '16 位 DAC') -and (Has '≤0.1%') -and (Has 'INA282') -and (Has '2mΩ') -and (Has 'AUTOCAL'))
Check '拓扑/效率：LLC+SR、buck、200kHz、90/92、240W' ((Has 'LLC') -and (Has '同步整流') -and (Has '200kHz') -and (Has '≥90%') -and (Has '≥92%') -and (Has '240W'))
Check '纹波：50/30、母线 100/150、20/40dB' ((Has '≤50mVpp') -and (Has '≤30mVpp') -and (Has '≤100mVpp') -and (Has '≤150mVpp') -and (Has '≥20dB') -and (Has '≥40dB'))
Check '风扇：HA60251V4、60×25、FG、≥50mm' ((Has 'HA60251V4') -and (Has '60×25') -and (Has 'FG') -and (Has '≥50mm'))
Check '布局：79×12、Ø5/Ø8、60+30+25≤120' ((Has '79×12') -and (Has 'Ø5') -and (Has 'Ø8') -and (Has '115≤120'))
Check '温度：2 NTC、75/95、PT100 9600/8N1/FC03/±0.5' ((Has '2 路 NTC') -and (Has '75℃') -and (Has '95℃') -and (Has '9600/8N1') -and (Has 'FC03') -and (Has '±0.5℃'))
Check 'MCU：STM32G431CBT6 ×2、数控 B 型' ((Has 'STM32G431CBT6') -and (Has '数控 B 型'))
Check '成本：600/700/1500–2000/BOM 两栏' ((Has '≤600') -and (Has '700') -and (Has '1,500–2,000') -and (Has 'BOM'))
Check '保护：≤10µs、fail-open、不重合闸、4A T' ((Has '≤10µs') -and (Has 'fail-open') -and (Has '不自动重合闸') -and (Has '4A T'))
Check '尺寸：120×60×180、120×60×35、215、顶丝/磁吸' ((Has '120×60×180') -and (Has '120×60×35') -and (Has '215') -and (Has '顶丝') -and (Has '磁吸'))
Check '参考：RT300-MKV / 1000W / 三类结论' ((Has 'RT300-MKV') -and (Has '1000W') -and (Has '可借鉴') -and (Has '需改造') -and (Has '不适用'))
Check '待确认 7 项' ((Has '全量程 0.01V') -and (Has 'PFC') -and (Has '安规') -and (Has '插槽型号') -and (Has '开关频率') -and (Has 'PT100 掉线') -and (Has 'SHARE/SYNC'))
Check '一致性自检' (Has '一致性自检')
Check '无急停声明' ((Has '取消急停') -and (Has '无紧急切断') -and (Has '限用'))

# Register map overlap check (section 7.2)
$inMap = $false
$ranges = @()
foreach ($line in $lines) {
    if ($line -match '^### 7\.2') { $inMap = $true; continue }
    if ($inMap -and $line -match '^### 7\.3') { break }
    if (-not $inMap) { continue }
    if ($line -match '^\| 0x([0-9A-Fa-f]{2})(?:–0x([0-9A-Fa-f]{2}))? \| ([^|]+) \|.*\| ([0-9]+)') {
        $start = [Convert]::ToInt32($matches[1], 16)
        if ($matches[2]) { $end = [Convert]::ToInt32($matches[2], 16) }
        else {
            $width = [int]$matches[4]
            if ($width -gt 8 -and $width -le 64) { $end = $start + [int]($width / 8) - 1 } else { $end = $start }
        }
        $ranges += [pscustomobject]@{ Start = $start; End = $end; Name = $matches[3].Trim() }
    }
}
$overlap = $false
for ($i = 0; $i -lt $ranges.Count; $i++) {
    for ($j = $i + 1; $j -lt $ranges.Count; $j++) {
        if ($ranges[$i].Start -le $ranges[$j].End -and $ranges[$j].Start -le $ranges[$i].End) {
            Write-Output ("[FAIL] 寄存器重叠: 0x{0:X2} {1} <-> 0x{2:X2} {3}" -f $ranges[$i].Start, $ranges[$i].Name, $ranges[$j].Start, $ranges[$j].Name)
            $overlap = $true
        }
    }
}
Check '寄存器表无地址重叠' (-not $overlap)

Write-Output ("RESULT: " + $(if ($fail -eq 0) { "PASS" } else { "FAIL" }) + " ($($total - $fail)/$total)")
if ($fail -ne 0) { exit 1 }

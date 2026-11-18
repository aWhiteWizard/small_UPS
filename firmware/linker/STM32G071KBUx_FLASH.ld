/*
 * STM32G071KBUx（占位型号）链接脚本 —— 内存布局与向量表位置的唯一事实源。
 *
 * 内存：
 *   FLASH 128 KiB @ 0x08000000（只读/执行，掉电保持）
 *   SRAM   36 KiB @ 0x20000000（可读写，掉电丢失）
 *
 * 布局（从低地址到高地址）：
 *   FLASH: .isr_vector -> .text -> .rodata -> .ARM* -> .preinit/.init/.fini_array
 *          -> .data 的加载镜像（LMA）
 *   SRAM : .data（VMA，启动时由 _sidata 复制）-> .bss（启动时清零）
 *          -> 最小堆/栈保留区；_estack = RAM 顶端 = 向量表[0] = 初始 MSP
 *
 * 向量表：.isr_vector 放在 FLASH 最前，并用文末 ASSERT 锁定 _svector ==
 * ORIGIN(FLASH)。复位后 VTOR=0，G0 的 MEM_MODE=00 把主 Flash 映射到
 * 0x00000000，因此 CPU 从 0x00000000 看到的第 0 个字就是 _estack。
 *
 * 换型号时：改 MEMORY 容量/起始地址，并同步启动文件、HAL 设备宏
 * （切换点见 firmware/README.md §6）。
 */
ENTRY(Reset_Handler)

/* 初始 MSP：RAM 顶端；Cortex-M0+ 要求 8 字节对齐。 */
_estack = ORIGIN(RAM) + LENGTH(RAM);
_Min_Heap_Size  = 0x200;
_Min_Stack_Size = 0x400;

MEMORY
{
  RAM   (xrw) : ORIGIN = 0x20000000, LENGTH = 36K
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 128K
}

/* 分开 R/X 与 RW 段，避免新版 ld 报 "LOAD segment with RWX permissions"。 */
PHDRS
{
  text PT_LOAD FLAGS(5);
  data PT_LOAD FLAGS(6);
}

SECTIONS
{
  .isr_vector :
  {
    . = ALIGN(4);
    _svector = .;
    KEEP(*(.isr_vector))
    . = ALIGN(4);
  } >FLASH :text

  .text :
  {
    . = ALIGN(4);
    *(.text)
    *(.text*)
    *(.glue_7)
    *(.glue_7t)
    *(.eh_frame)
    KEEP(*(.init))
    KEEP(*(.fini))
    . = ALIGN(4);
    _etext = .;
  } >FLASH :text

  .rodata :
  {
    . = ALIGN(4);
    *(.rodata)
    *(.rodata*)
    . = ALIGN(4);
  } >FLASH :text

  .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } >FLASH :text
  .ARM :
  {
    . = ALIGN(4);
    __exidx_start = .;
    *(.ARM.exidx*)
    __exidx_end = .;
    . = ALIGN(4);
  } >FLASH :text

  .preinit_array :
  {
    PROVIDE_HIDDEN(__preinit_array_start = .);
    KEEP(*(.preinit_array*))
    PROVIDE_HIDDEN(__preinit_array_end = .);
  } >FLASH :text
  .init_array :
  {
    PROVIDE_HIDDEN(__init_array_start = .);
    KEEP(*(SORT(.init_array.*)))
    KEEP(*(.init_array*))
    PROVIDE_HIDDEN(__init_array_end = .);
  } >FLASH :text
  .fini_array :
  {
    PROVIDE_HIDDEN(__fini_array_start = .);
    KEEP(*(SORT(.fini_array.*)))
    KEEP(*(.fini_array*))
    PROVIDE_HIDDEN(__fini_array_end = .);
  } >FLASH :text

  /* .data：VMA 在 RAM，LMA（初值）在 FLASH；启动文件用 _sidata 复制。 */
  _sidata = LOADADDR(.data);

  .data :
  {
    . = ALIGN(4);
    _sdata = .;
    *(.data)
    *(.data*)
    . = ALIGN(4);
    _edata = .;
  } >RAM AT> FLASH :data

  /* .bss：不占 FLASH 镜像，启动文件按 _sbss.._ebss 清零。 */
  .bss :
  {
    . = ALIGN(4);
    _sbss = .;
    __bss_start__ = _sbss;
    *(.bss)
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
    __bss_end__ = _ebss;
  } >RAM :data

  /* 最小堆/栈保留区（NOLOAD）：保证 .bss 之后至少 0x200+0x400 字节；
     实际 MSP 从 _estack 向下增长。 */
  ._user_heap_stack (NOLOAD) :
  {
    . = ALIGN(8);
    PROVIDE(end = .);
    PROVIDE(_end = .);
    . = . + _Min_Heap_Size;
    . = . + _Min_Stack_Size;
    . = ALIGN(8);
  } >RAM

  /DISCARD/ :
  {
    libc.a(*)
    libm.a(*)
    libgcc.a(*)
  }

  .ARM.attributes 0 : { *(.ARM.attributes) }
}

/* 布局自检：向量表必须在 Flash 起始；初始 MSP 必须在 RAM 顶端。 */
ASSERT(_svector == ORIGIN(FLASH), "vector table must start at FLASH origin")
ASSERT(_estack == ORIGIN(RAM) + LENGTH(RAM), "initial MSP must be top of RAM")

/*
 * STM32G071xx 启动文件（本项目维护的本地副本，GCC 汇编）。
 *
 * 来源：STM32CubeG0 v1.4.5 的
 *   cmsis_device_g0/Source/Templates/gcc/startup_stm32g071xx.s
 * Copyright (c) 2018-2021 STMicroelectronics. All rights reserved.
 * 许可证：Apache-2.0（见 .tools/stm32cube/cmsis_device_g0/LICENSE.md）。
 * 本项目改动：补充中文注释，用 WEAK_DEFAULT 宏压缩 weak 别名；复位流程、
 * 向量表顺序与符号名保持与 CMSIS 模板一致。
 *
 * 链接契约（firmware/linker/STM32G071KBUx_FLASH.ld）：
 *   _estack  = RAM 顶端（也是向量表第 0 个字，初始 MSP）
 *   _sidata  = .data 在 FLASH 中的加载地址
 *   _sdata/_edata = .data 在 RAM 中的起止
 *   _sbss/_ebss   = .bss 起止
 * 向量表放在 FLASH 起始 0x08000000，链接脚本用 ASSERT 固定。
 */

.syntax unified
.cpu cortex-m0plus
.fpu softvfp
.thumb

.global g_pfnVectors
.global Default_Handler

/* Reset_Handler 使用的链接期常量；紧跟在代码前，不进入向量表。 */
.word _sidata          /* .data 初值在 FLASH 的地址 */
.word _sdata           /* .data 在 RAM 的起始 */
.word _edata           /* .data 在 RAM 的结束 */
.word _sbss            /* .bss 起始 */
.word _ebss            /* .bss 结束 */

/*
 * 复位入口：硬件从向量表第 1 个字（0x08000004）取 Reset_Handler 并跳转。
 * 此时还没有 C 运行环境，先建立栈，再初始化 .data/.bss，最后进 main。
 */
.section .text.Reset_Handler
.weak Reset_Handler
.type Reset_Handler, %function
Reset_Handler:
  ldr   r0, =_estack
  mov   sp, r0                  /* 初始 MSP = RAM 顶端（8 字节对齐） */

  bl    SystemInit              /* CMSIS 时钟/FPU 初始化（system_stm32g0xx.c） */

  /* 把 .data 初值从 FLASH(_sidata) 复制到 RAM(_sdata.._edata)。 */
  ldr   r0, =_sdata
  ldr   r1, =_edata
  ldr   r2, =_sidata
  movs  r3, #0
  b     LoopCopyDataInit

CopyDataInit:
  ldr   r4, [r2, r3]
  str   r4, [r0, r3]
  adds  r3, r3, #4

LoopCopyDataInit:
  adds  r4, r0, r3
  cmp   r4, r1
  bcc   CopyDataInit

  /* 把 .bss(_sbss.._ebss) 清零。 */
  ldr   r2, =_sbss
  ldr   r4, =_ebss
  movs  r3, #0
  b     LoopFillZerobss

FillZerobss:
  str   r3, [r2]
  adds  r2, r2, #4

LoopFillZerobss:
  cmp   r2, r4
  bcc   FillZerobss

  bl    __libc_init_array       /* C/C++ 静态构造（newlib） */
  bl    main                    /* 应用入口，正常不返回 */

LoopForever:
  b     LoopForever             /* main 返回时停在这里，保留现场给调试器 */

.size Reset_Handler, .-Reset_Handler

/*
 * 未实现的中断默认入口：死循环，便于调试器看栈/寄存器定位。
 * 具体外设中断可在 C 里定义同名强符号覆盖（如 SysTick_Handler）。
 */
.section .text.Default_Handler,"ax",%progbits
.type Default_Handler, %function
Default_Handler:
Infinite_Loop:
  b     Infinite_Loop
.size Default_Handler, .-Default_Handler

/*
 * Cortex-M0+ 向量表：47 个字（16 个系统向量 + 31 个 IRQ），共 188 字节。
 * 物理位置在 FLASH 起始 0x08000000；复位后 VTOR=0，G0 的 MEM_MODE=00
 * 把主 Flash 映射到 0x00000000，所以 CPU 从 0x00000000 也能看到同一张表。
 * 若以后加 bootloader 或改 VTOR，应显式设为 0x08000000。
 */
.section .isr_vector,"a",%progbits
.type g_pfnVectors, %object
g_pfnVectors:
  .word _estack                 /* 0x08000000: 初始 MSP */
  .word Reset_Handler           /* 0x08000004: 复位入口 */
  .word NMI_Handler             /* 0x08000008: NMI */
  .word HardFault_Handler       /* 0x0800000C: HardFault */
  .word 0                       /* 0x08000010: 保留 */
  .word 0                       /* 0x08000014: 保留 */
  .word 0                       /* 0x08000018: 保留 */
  .word 0                       /* 0x0800001C: 保留 */
  .word 0                       /* 0x08000020: 保留 */
  .word 0                       /* 0x08000024: 保留 */
  .word 0                       /* 0x08000028: 保留 */
  .word SVC_Handler             /* 0x0800002C: SVCall */
  .word 0                       /* 0x08000030: 保留 */
  .word 0                       /* 0x08000034: 保留 */
  .word PendSV_Handler          /* 0x08000038: PendSV */
  .word SysTick_Handler         /* 0x0800003C: SysTick（HAL 1 ms 时基） */

  /* 外设中断 IRQ0..IRQ30，起始偏移 0x08000040。 */
  .word WWDG_IRQHandler                   /* IRQ0  Window watchdog */
  .word PVD_IRQHandler                    /* IRQ1  PVD */
  .word RTC_TAMP_IRQHandler               /* IRQ2  RTC tamper */
  .word FLASH_IRQHandler                  /* IRQ3  FLASH */
  .word RCC_IRQHandler                    /* IRQ4  RCC */
  .word EXTI0_1_IRQHandler                /* IRQ5  EXTI0/1 */
  .word EXTI2_3_IRQHandler                /* IRQ6  EXTI2/3 */
  .word EXTI4_15_IRQHandler               /* IRQ7  EXTI4..15 */
  .word UCPD1_2_IRQHandler                /* IRQ8  UCPD1/2 */
  .word DMA1_Channel1_IRQHandler          /* IRQ9  DMA1 CH1 */
  .word DMA1_Channel2_3_IRQHandler        /* IRQ10 DMA1 CH2/3 */
  .word DMA1_Ch4_7_DMAMUX1_OVR_IRQHandler /* IRQ11 DMA1 CH4..7 / DMAMUX */
  .word ADC1_COMP_IRQHandler              /* IRQ12 ADC1/COMP */
  .word TIM1_BRK_UP_TRG_COM_IRQHandler    /* IRQ13 TIM1 BRK/UP/TRG/COM */
  .word TIM1_CC_IRQHandler                /* IRQ14 TIM1 CC */
  .word TIM2_IRQHandler                   /* IRQ15 TIM2 */
  .word TIM3_IRQHandler                   /* IRQ16 TIM3 */
  .word TIM6_DAC_LPTIM1_IRQHandler        /* IRQ17 TIM6/DAC/LPTIM1 */
  .word TIM7_LPTIM2_IRQHandler            /* IRQ18 TIM7/LPTIM2 */
  .word TIM14_IRQHandler                  /* IRQ19 TIM14 */
  .word TIM15_IRQHandler                  /* IRQ20 TIM15 */
  .word TIM16_IRQHandler                  /* IRQ21 TIM16 */
  .word TIM17_IRQHandler                  /* IRQ22 TIM17 */
  .word I2C1_IRQHandler                   /* IRQ23 I2C1 */
  .word I2C2_IRQHandler                   /* IRQ24 I2C2 */
  .word SPI1_IRQHandler                   /* IRQ25 SPI1 */
  .word SPI2_IRQHandler                   /* IRQ26 SPI2 */
  .word USART1_IRQHandler                 /* IRQ27 USART1 */
  .word USART2_IRQHandler                 /* IRQ28 USART2 */
  .word USART3_4_LPUART1_IRQHandler       /* IRQ29 USART3/4/LPUART1 */
  .word CEC_IRQHandler                    /* IRQ30 CEC */

.size g_pfnVectors, .-g_pfnVectors

/* 把未实现的异常/中断都弱别名到 Default_Handler；C 里的同名强符号优先。 */
.macro WEAK_DEFAULT handler
  .weak \handler
  .thumb_set \handler, Default_Handler
.endm

WEAK_DEFAULT NMI_Handler
WEAK_DEFAULT HardFault_Handler
WEAK_DEFAULT SVC_Handler
WEAK_DEFAULT PendSV_Handler
WEAK_DEFAULT SysTick_Handler
WEAK_DEFAULT WWDG_IRQHandler
WEAK_DEFAULT PVD_IRQHandler
WEAK_DEFAULT RTC_TAMP_IRQHandler
WEAK_DEFAULT FLASH_IRQHandler
WEAK_DEFAULT RCC_IRQHandler
WEAK_DEFAULT EXTI0_1_IRQHandler
WEAK_DEFAULT EXTI2_3_IRQHandler
WEAK_DEFAULT EXTI4_15_IRQHandler
WEAK_DEFAULT UCPD1_2_IRQHandler
WEAK_DEFAULT DMA1_Channel1_IRQHandler
WEAK_DEFAULT DMA1_Channel2_3_IRQHandler
WEAK_DEFAULT DMA1_Ch4_7_DMAMUX1_OVR_IRQHandler
WEAK_DEFAULT ADC1_COMP_IRQHandler
WEAK_DEFAULT TIM1_BRK_UP_TRG_COM_IRQHandler
WEAK_DEFAULT TIM1_CC_IRQHandler
WEAK_DEFAULT TIM2_IRQHandler
WEAK_DEFAULT TIM3_IRQHandler
WEAK_DEFAULT TIM6_DAC_LPTIM1_IRQHandler
WEAK_DEFAULT TIM7_LPTIM2_IRQHandler
WEAK_DEFAULT TIM14_IRQHandler
WEAK_DEFAULT TIM15_IRQHandler
WEAK_DEFAULT TIM16_IRQHandler
WEAK_DEFAULT TIM17_IRQHandler
WEAK_DEFAULT I2C1_IRQHandler
WEAK_DEFAULT I2C2_IRQHandler
WEAK_DEFAULT SPI1_IRQHandler
WEAK_DEFAULT SPI2_IRQHandler
WEAK_DEFAULT USART1_IRQHandler
WEAK_DEFAULT USART2_IRQHandler
WEAK_DEFAULT USART3_4_LPUART1_IRQHandler
WEAK_DEFAULT CEC_IRQHandler

/*
 * T-0002 最小工程的 HAL 配置：只启用 blinky 所需模块。
 * 依据 STM32Cube G0 v1.4.7 的 stm32g0xx_hal_conf_template.h 裁剪。
 */
/*
 * T-0023 占位 STM32G071KB 的最小 HAL 配置。
 * - 只用 HAL；LL 是 header-only，需要时 include stm32g0xx_ll_*.h，无需改本文件。
 * - HAL_FLASH 只启用头文件：HAL_Init() 用 __HAL_FLASH_PREFETCH_BUFFER_ENABLE()，
 *   不编译 stm32g0xx_hal_flash.c。
 * - 换型号/换板时改：模块开关、HSE/HSI/LSE 值与启动超时（firmware/README.md §6.3 第 4 项）。
 */
#ifndef STM32G0xx_HAL_CONF_H
#define STM32G0xx_HAL_CONF_H

#ifdef __cplusplus
extern "C" {
#endif

/* ########################## Module Selection ############################## */
#define HAL_MODULE_ENABLED
#define HAL_CORTEX_MODULE_ENABLED
#define HAL_FLASH_MODULE_ENABLED   /* HAL_Init() 用 __HAL_FLASH_PREFETCH_BUFFER_ENABLE() */
#define HAL_GPIO_MODULE_ENABLED
#define HAL_RCC_MODULE_ENABLED

/* ########################## Oscillator Values ############################# */
/* 占位板未接外部晶振；复位默认 HSI 16 MHz。HSE/LSE 值仅供 HAL 库参数使用。 */
#if !defined(HSE_VALUE)
#define HSE_VALUE               (8000000UL)
#endif
#if !defined(HSE_STARTUP_TIMEOUT)
#define HSE_STARTUP_TIMEOUT     (100UL)
#endif
#if !defined(HSI_VALUE)
#define HSI_VALUE               (16000000UL)
#endif
#if !defined(LSI_VALUE)
#define LSI_VALUE               (32000UL)
#endif
#if !defined(LSE_VALUE)
#define LSE_VALUE               (32768UL)
#endif
#if !defined(LSE_STARTUP_TIMEOUT)
#define LSE_STARTUP_TIMEOUT     (5000UL)
#endif

/* ########################## System Configuration ########################## */
#define VDD_VALUE               (3300UL)
#define TICK_INT_PRIORITY       ((1UL << __NVIC_PRIO_BITS) - 1UL)
#define USE_RTOS                0U
#define PREFETCH_ENABLE         1U
#define INSTRUCTION_CACHE_ENABLE 1U

/* ########################## Assert Selection ############################## */
/* #define USE_FULL_ASSERT    1U */

/* ########################## Includes ###################################### */
#ifdef HAL_RCC_MODULE_ENABLED
#include "stm32g0xx_hal_rcc.h"
#endif

#ifdef HAL_GPIO_MODULE_ENABLED
#include "stm32g0xx_hal_gpio.h"
#endif

#ifdef HAL_CORTEX_MODULE_ENABLED
#include "stm32g0xx_hal_cortex.h"
#endif

#ifdef HAL_FLASH_MODULE_ENABLED
#include "stm32g0xx_hal_flash.h"
#endif

/* Exported macro ----------------------------------------------------------- */
#ifdef USE_FULL_ASSERT
#define assert_param(expr) ((expr) ? (void)0U : assert_failed((uint8_t *)__FILE__, __LINE__))
void assert_failed(uint8_t *file, uint32_t line);
#else
#define assert_param(expr) ((void)0U)
#endif

#ifdef __cplusplus
}
#endif

#endif /* STM32G0xx_HAL_CONF_H */

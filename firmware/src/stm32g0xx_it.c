/*
 * T-0002 最小工程中断入口：HAL 的 1 ms 时基。
 */
#include "stm32g0xx_hal.h"

void SysTick_Handler(void)
{
  HAL_IncTick();
}

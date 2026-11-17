/*
 * T-0002 最小工程：PA5 点灯（1 Hz 翻转）。
 *
 * 目标：STM32G071KB（占位型号，32-pin）。无外部晶振，时钟保持复位后的
 * HSI 16 MHz；本工程只验证工具链/HAL/链接链路，不承担 PSU 控制功能。
 */
#include "stm32g0xx_hal.h"

int main(void)
{
  HAL_Init();

  __HAL_RCC_GPIOA_CLK_ENABLE();

  GPIO_InitTypeDef led = {0};
  led.Pin   = GPIO_PIN_5;
  led.Mode  = GPIO_MODE_OUTPUT_PP;
  led.Pull  = GPIO_NOPULL;
  led.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &led);

  for (;;)
  {
    HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);
    HAL_Delay(500);
  }
}

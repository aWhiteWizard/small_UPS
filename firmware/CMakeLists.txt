cmake_minimum_required(VERSION 3.20)

# T-0002 最小工程：STM32G071KB 点灯（占位型号），验证 工具链 + HAL + 链接 + 产物。
project(psu_minimal LANGUAGES C ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# 固定版本的 CMSIS/HAL 由 firmware/tools/bootstrap.ps1 下载到 <repo>/.tools/stm32cube。
set(STM32CUBE_G0_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.tools/stm32cube"
    CACHE PATH "Pinned CMSIS/HAL checkout root (cmsis_core, cmsis_device_g0, stm32g0xx_hal_driver)")

foreach(_dep cmsis_core cmsis_device_g0 stm32g0xx_hal_driver)
  if(NOT EXISTS "${STM32CUBE_G0_ROOT}/${_dep}")
    message(FATAL_ERROR
      "缺少 ${_dep}：${STM32CUBE_G0_ROOT}/${_dep}\n"
      "先运行 firmware/tools/bootstrap.ps1 拉取固定版本 HAL/CMSIS。")
  endif()
endforeach()

set(CUBE "${STM32CUBE_G0_ROOT}")
set(MCU_FLAGS -mcpu=cortex-m0plus -mthumb -mfloat-abi=soft)

# 仅编译最小 HAL 子集；SysTick/GPIO 用到的头文件在 stm32g0xx_hal_conf.h 中启用。
# HAL_Init() 通过 __HAL_FLASH_PREFETCH_BUFFER_ENABLE() 直接操作 FLASH 寄存器，
# 因此只启用 HAL_FLASH 头文件、不编译 stm32g0xx_hal_flash.c。
set(HAL_SOURCES
  ${CUBE}/stm32g0xx_hal_driver/Src/stm32g0xx_hal.c
  ${CUBE}/stm32g0xx_hal_driver/Src/stm32g0xx_hal_cortex.c
  ${CUBE}/stm32g0xx_hal_driver/Src/stm32g0xx_hal_gpio.c
)

set(STARTUP ${CUBE}/cmsis_device_g0/Source/Templates/gcc/startup_stm32g071xx.s)
set_source_files_properties(${STARTUP} PROPERTIES
  LANGUAGE ASM
  COMPILE_OPTIONS "-x;assembler-with-cpp")

set(LINKER_SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/linker/STM32G071KBUx_FLASH.ld)

add_executable(psu_minimal
  src/main.c
  src/stm32g0xx_it.c
  ${CUBE}/cmsis_device_g0/Source/Templates/system_stm32g0xx.c
  ${STARTUP}
  ${HAL_SOURCES}
)

target_include_directories(psu_minimal PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${CUBE}/cmsis_core/Include
  ${CUBE}/cmsis_device_g0/Include
  ${CUBE}/stm32g0xx_hal_driver/Inc
)

target_compile_definitions(psu_minimal PRIVATE STM32G071xx USE_HAL_DRIVER)

target_compile_options(psu_minimal PRIVATE
  ${MCU_FLAGS}
  -Os -g3
  -ffunction-sections -fdata-sections
  -Wall -Wextra -Wno-unused-parameter
)

target_link_options(psu_minimal PRIVATE
  ${MCU_FLAGS}
  -T${LINKER_SCRIPT}
  -Wl,--gc-sections
  -Wl,-Map=${CMAKE_BINARY_DIR}/psu_minimal.map
  -Wl,--print-memory-usage
  -specs=nano.specs
  -specs=nosys.specs
)

set_target_properties(psu_minimal PROPERTIES
  OUTPUT_NAME psu_minimal
  SUFFIX ".elf"
  LINK_DEPENDS ${LINKER_SCRIPT}
)

add_custom_command(TARGET psu_minimal POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:psu_minimal> ${CMAKE_BINARY_DIR}/psu_minimal.bin
  COMMAND ${CMAKE_OBJCOPY} -O ihex   $<TARGET_FILE:psu_minimal> ${CMAKE_BINARY_DIR}/psu_minimal.hex
  COMMAND ${CMAKE_SIZE} $<TARGET_FILE:psu_minimal>
  COMMENT "Generating .bin/.hex and printing size"
)

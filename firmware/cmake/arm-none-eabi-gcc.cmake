# 交叉编译工具链：GNU Arm Embedded（arm-none-eabi-gcc）
# 使用前把 <repo>/.tools/arm-gcc/bin 加入 PATH（firmware/build.ps1 会自动做）。
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(CMAKE_C_COMPILER   arm-none-eabi-gcc)
set(CMAKE_CXX_COMPILER arm-none-eabi-g++)
set(CMAKE_ASM_COMPILER arm-none-eabi-gcc)

find_program(CMAKE_AR      arm-none-eabi-ar      REQUIRED)
find_program(CMAKE_OBJCOPY arm-none-eabi-objcopy REQUIRED)
find_program(CMAKE_OBJDUMP arm-none-eabi-objdump REQUIRED)
find_program(CMAKE_SIZE    arm-none-eabi-size    REQUIRED)

# 交叉编译不链接主机可执行文件，用静态库做编译器探测。
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
set(CMAKE_EXECUTABLE_SUFFIX ".elf")

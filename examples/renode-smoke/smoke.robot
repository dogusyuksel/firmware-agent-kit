*** Settings ***
Documentation     Renode smoke test for the kit's integration-test templates (STM32F4 Discovery platform).
...               Build: arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Os -nostdlib -T link.ld main.c -o build/smoke.elf
...               Run:   renode-test smoke.robot
Suite Setup       Setup
Suite Teardown    Teardown
Test Setup        Reset Emulation
Test Teardown     Test Teardown
Resource          ${RENODEKEYWORDS}

*** Variables ***
${PLATFORM}       @platforms/boards/stm32f4_discovery-kit.repl
${ELF}            @${CURDIR}/build/smoke.elf
${UART}           sysbus.usart2

*** Keywords ***
Create Machine
    Execute Command           mach create
    Execute Command           machine LoadPlatformDescription ${PLATFORM}
    Execute Command           sysbus LoadELF ${ELF}
    Create Terminal Tester    ${UART}    timeout=5

*** Test Cases ***
Boots And Prints Banner
    Create Machine
    Start Emulation
    Wait For Line On Uart     fw: boot ok

Answers Version Command
    Create Machine
    Start Emulation
    Wait For Line On Uart     fw: boot ok
    Write Line To Uart        version    waitForEcho=false
    Wait For Line On Uart     v\\d+\\.\\d+\\.\\d+    treatAsRegex=true

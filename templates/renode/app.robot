*** Settings ***
Documentation     firmware-agent-kit integration test template (Renode + Robot Framework).
...               Run: renode-test tests/integration/app.robot
Suite Setup       Setup
Suite Teardown    Teardown
Test Setup        Reset Emulation
Test Teardown     Test Teardown
Resource          ${RENODEKEYWORDS}

*** Variables ***
${PLATFORM}       @platforms/boards/stm32f4_discovery-kit.repl
${ELF}            @${CURDIR}/../../build/app.elf
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
    Wait For Line On Uart     boot ok

Answers Version Command
    Create Machine
    Start Emulation
    Wait For Line On Uart     boot ok
    Write Line To Uart        version    waitForEcho=false
    Wait For Line On Uart     v\\d+\\.\\d+\\.\\d+    treatAsRegex=true

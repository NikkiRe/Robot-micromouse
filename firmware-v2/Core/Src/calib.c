#include "calib.h"
#include "main.h"
#include "motors.h"
#include "nav.h"

static void stage_turns90(void)
{
    for (uint8_t i = 0; i < 4; i++) {
        nav_turn_right90();
        HAL_Delay(CALIB_MOVE_PAUSE_MS);
    }
}

static void stage_forward(void)
{
    for (uint8_t i = 0; i < CALIB_FORWARD_CELLS; i++) {
        nav_forward_cell();
    }
}

static void stage_turns180(void)
{
    for (uint8_t i = 0; i < 2; i++) {
        nav_turn180();
        HAL_Delay(CALIB_MOVE_PAUSE_MS);
    }
}

void calib_run(void)
{
    led_set(true);
    button_wait_release();
    HAL_Delay(NAV_START_DELAY_MS);

    for (;;) {
        led_set(true);

        stage_turns90();
        led_blink(1, 300);
        HAL_Delay(CALIB_STAGE_PAUSE_MS);

        stage_forward();
        led_blink(2, 300);
        HAL_Delay(CALIB_STAGE_PAUSE_MS);

        stage_turns180();
        led_blink(3, 300);

        motors_coast();
        while (!button_pressed()) {
            led_toggle();
            HAL_Delay(500);
        }
        button_wait_release();
        led_set(true);
        HAL_Delay(NAV_START_DELAY_MS);
    }
}

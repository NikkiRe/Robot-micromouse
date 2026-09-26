#ifndef MAIN_H
#define MAIN_H

#include "stm32f4xx_hal.h"
#include <stdbool.h>
#include <stdint.h>

#define MOTOR_PORT        GPIOA
#define MOTOR_R_IN1_PIN   GPIO_PIN_5
#define MOTOR_R_IN2_PIN   GPIO_PIN_6
#define MOTOR_L_IN1_PIN   GPIO_PIN_2
#define MOTOR_L_IN2_PIN   GPIO_PIN_3
#define MOTOR_STBY_PIN    GPIO_PIN_9
#define MOTOR_PWMA_PIN    GPIO_PIN_8
#define MOTOR_PWMB_PIN    GPIO_PIN_10

#define SENSOR_R_PORT     GPIOB
#define SENSOR_R_PIN      GPIO_PIN_0
#define SENSOR_L_PORT     GPIOB
#define SENSOR_L_PIN      GPIO_PIN_1
#define SENSOR_C_PORT     GPIOA
#define SENSOR_C_PIN      GPIO_PIN_4

#define LED_PORT          GPIOC
#define LED_PIN           GPIO_PIN_13
#define BUTTON_PORT       GPIOA
#define BUTTON_PIN        GPIO_PIN_0

void led_set(bool on);
void led_toggle(void);
void led_blink(uint8_t n, uint32_t on_ms);

bool button_pressed(void);
void button_wait_release(void);

void Error_Handler(void);

#endif

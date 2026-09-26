#ifndef MOTORS_H
#define MOTORS_H

#include <stdint.h>
#include <stdbool.h>

/* 0 если pwmb драйвера ещё сидит на vcc */
#ifndef MOTORS_PWMB_ON_PA10
#define MOTORS_PWMB_ON_PA10   1
#endif

#define MOTOR_PWM_FREQ_HZ     20000u

/* калибровать */
#define MOTOR_TRIM_LEFT       100
#define MOTOR_TRIM_RIGHT      100

void motors_init(void);
void motors_enable(bool on);
void motors_set(int8_t left_pct, int8_t right_pct);
void motors_brake(void);
void motors_coast(void);

#endif

#include "motors.h"
#include "main.h"

static TIM_HandleTypeDef htim1;
static uint32_t pwm_period;

static void set_dir(uint16_t in1, uint16_t in2, int dir)
{
    GPIO_PinState a = GPIO_PIN_RESET;
    GPIO_PinState b = GPIO_PIN_RESET;
    if (dir > 0) {
        a = GPIO_PIN_SET;
    } else if (dir < 0) {
        b = GPIO_PIN_SET;
    } else {
        a = GPIO_PIN_SET;
        b = GPIO_PIN_SET;
    }
    HAL_GPIO_WritePin(MOTOR_PORT, in1, a);
    HAL_GPIO_WritePin(MOTOR_PORT, in2, b);
}

static void set_duty(uint32_t channel, uint8_t pct)
{
    if (pct > 100) {
        pct = 100;
    }
    uint32_t ccr = (pwm_period * pct) / 100u;
    __HAL_TIM_SET_COMPARE(&htim1, channel, ccr);
}

void motors_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_TIM1_CLK_ENABLE();

    HAL_GPIO_WritePin(MOTOR_PORT,
                      MOTOR_R_IN1_PIN | MOTOR_R_IN2_PIN |
                      MOTOR_L_IN1_PIN | MOTOR_L_IN2_PIN | MOTOR_STBY_PIN,
                      GPIO_PIN_RESET);
    gpio.Pin   = MOTOR_R_IN1_PIN | MOTOR_R_IN2_PIN |
                 MOTOR_L_IN1_PIN | MOTOR_L_IN2_PIN | MOTOR_STBY_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(MOTOR_PORT, &gpio);

    /* gpio шим здесь, а не в HAL_TIM_MspPostInit: та из .ioc переводит pa9 в tim1_ch2, а у нас это stby */
    gpio.Pin       = MOTOR_PWMA_PIN;
#if MOTORS_PWMB_ON_PA10
    gpio.Pin      |= MOTOR_PWMB_PIN;
#endif
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = GPIO_AF1_TIM1;
    HAL_GPIO_Init(MOTOR_PORT, &gpio);

    uint32_t tim_clk = HAL_RCC_GetPCLK2Freq();
    RCC_ClkInitTypeDef clk;
    uint32_t latency;
    HAL_RCC_GetClockConfig(&clk, &latency);
    if (clk.APB2CLKDivider != RCC_HCLK_DIV1) {
        tim_clk *= 2;
    }
    pwm_period = tim_clk / MOTOR_PWM_FREQ_HZ;

    htim1.Instance               = TIM1;
    htim1.Init.Prescaler         = 0;
    htim1.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim1.Init.Period            = pwm_period - 1;
    htim1.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim1.Init.RepetitionCounter = 0;
    htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    if (HAL_TIM_PWM_Init(&htim1) != HAL_OK) {
        Error_Handler();
    }

    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode       = TIM_OCMODE_PWM1;
    oc.Pulse        = 0;
    oc.OCPolarity   = TIM_OCPOLARITY_HIGH;
    oc.OCNPolarity  = TIM_OCNPOLARITY_HIGH;
    oc.OCFastMode   = TIM_OCFAST_DISABLE;
    oc.OCIdleState  = TIM_OCIDLESTATE_RESET;
    oc.OCNIdleState = TIM_OCNIDLESTATE_RESET;
    if (HAL_TIM_PWM_ConfigChannel(&htim1, &oc, TIM_CHANNEL_1) != HAL_OK) {
        Error_Handler();
    }
#if MOTORS_PWMB_ON_PA10
    if (HAL_TIM_PWM_ConfigChannel(&htim1, &oc, TIM_CHANNEL_3) != HAL_OK) {
        Error_Handler();
    }
#endif

    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
#if MOTORS_PWMB_ON_PA10
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);
#endif

    motors_coast();
    motors_enable(true);
}

void motors_enable(bool on)
{
    HAL_GPIO_WritePin(MOTOR_PORT, MOTOR_STBY_PIN, on ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

static uint8_t abs8(int8_t v)
{
    return (uint8_t)(v < 0 ? -v : v);
}

void motors_set(int8_t left_pct, int8_t right_pct)
{
    int ldir = (left_pct > 0) - (left_pct < 0);
    int rdir = (right_pct > 0) - (right_pct < 0);

    uint32_t l = (uint32_t)abs8(left_pct)  * MOTOR_TRIM_LEFT  / 100u;
    uint32_t r = (uint32_t)abs8(right_pct) * MOTOR_TRIM_RIGHT / 100u;

#if MOTORS_PWMB_ON_PA10
    set_duty(TIM_CHANNEL_3, (uint8_t)(l > 100 ? 100 : l));
    set_duty(TIM_CHANNEL_1, (uint8_t)(r > 100 ? 100 : r));
#else
    (void)l;
    set_duty(TIM_CHANNEL_1, (uint8_t)(rdir ? MOTOR_TRIM_RIGHT : 0));
    (void)r;
#endif

    if (ldir == 0) {
        HAL_GPIO_WritePin(MOTOR_PORT, MOTOR_L_IN1_PIN | MOTOR_L_IN2_PIN, GPIO_PIN_RESET);
    } else {
        set_dir(MOTOR_L_IN1_PIN, MOTOR_L_IN2_PIN, ldir);
    }
    if (rdir == 0) {
        HAL_GPIO_WritePin(MOTOR_PORT, MOTOR_R_IN1_PIN | MOTOR_R_IN2_PIN, GPIO_PIN_RESET);
    } else {
        set_dir(MOTOR_R_IN1_PIN, MOTOR_R_IN2_PIN, rdir);
    }
}

void motors_brake(void)
{
    set_dir(MOTOR_L_IN1_PIN, MOTOR_L_IN2_PIN, 0);
    set_dir(MOTOR_R_IN1_PIN, MOTOR_R_IN2_PIN, 0);
    set_duty(TIM_CHANNEL_1, 100);
#if MOTORS_PWMB_ON_PA10
    set_duty(TIM_CHANNEL_3, 100);
#endif
}

void motors_coast(void)
{
    HAL_GPIO_WritePin(MOTOR_PORT,
                      MOTOR_R_IN1_PIN | MOTOR_R_IN2_PIN |
                      MOTOR_L_IN1_PIN | MOTOR_L_IN2_PIN,
                      GPIO_PIN_RESET);
    set_duty(TIM_CHANNEL_1, 0);
#if MOTORS_PWMB_ON_PA10
    set_duty(TIM_CHANNEL_3, 0);
#endif
}

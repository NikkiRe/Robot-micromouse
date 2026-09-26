#include "main.h"
#include "motors.h"
#include "sensors.h"
#include "nav.h"
#include "calib.h"

static void SystemClock_Config(void);
static void board_gpio_init(void);

void led_set(bool on)
{
    /* pc13 на black pill активный low */
    HAL_GPIO_WritePin(LED_PORT, LED_PIN, on ? GPIO_PIN_RESET : GPIO_PIN_SET);
}

void led_toggle(void)
{
    HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
}

void led_blink(uint8_t n, uint32_t on_ms)
{
    for (uint8_t i = 0; i < n; i++) {
        led_set(true);
        HAL_Delay(on_ms);
        led_set(false);
        HAL_Delay(on_ms);
    }
}

bool button_pressed(void)
{
    if (HAL_GPIO_ReadPin(BUTTON_PORT, BUTTON_PIN) != GPIO_PIN_RESET) {
        return false;
    }
    HAL_Delay(20);
    return HAL_GPIO_ReadPin(BUTTON_PORT, BUTTON_PIN) == GPIO_PIN_RESET;
}

void button_wait_release(void)
{
    while (HAL_GPIO_ReadPin(BUTTON_PORT, BUTTON_PIN) == GPIO_PIN_RESET) {
        HAL_Delay(10);
    }
    HAL_Delay(50);
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    board_gpio_init();
    sensors_init();
    motors_init();

    led_blink(2, 100);

    if (button_pressed()) {
        calib_run();
    }

    while (!button_pressed()) {
        led_toggle();
        HAL_Delay(500);
    }
    button_wait_release();
    led_set(false);
    HAL_Delay(NAV_START_DELAY_MS);

    nav_init();
    nav_run();

    for (;;) {
    }
}

static void board_gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    gpio.Pin  = BUTTON_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(BUTTON_PORT, &gpio);

    /* pb8/pb9 как в базовой прошивке, не используются */
    gpio.Pin  = GPIO_PIN_8 | GPIO_PIN_9;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &gpio);
}

static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);

    osc.OscillatorType      = RCC_OSCILLATORTYPE_HSI;
    osc.HSIState            = RCC_HSI_ON;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.PLL.PLLState        = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        Error_Handler();
    }

    clk.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                         RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_HSI;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV1;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_0) != HAL_OK) {
        Error_Handler();
    }
}

void Error_Handler(void)
{
    __disable_irq();
    HAL_GPIO_WritePin(MOTOR_PORT, MOTOR_STBY_PIN, GPIO_PIN_RESET);
    for (;;) {
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        for (volatile uint32_t i = 0; i < 200000; i++) {
        }
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
    (void)file;
    (void)line;
    Error_Handler();
}
#endif

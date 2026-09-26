#include "sensors.h"
#include "main.h"

void sensors_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;

    gpio.Pin = SENSOR_C_PIN;
    HAL_GPIO_Init(SENSOR_C_PORT, &gpio);

    gpio.Pin = SENSOR_L_PIN | SENSOR_R_PIN;
    HAL_GPIO_Init(SENSOR_L_PORT, &gpio);
}

/* yl-63 активный low */
static inline bool read_raw(GPIO_TypeDef *port, uint16_t pin)
{
    return HAL_GPIO_ReadPin(port, pin) == GPIO_PIN_RESET;
}

bool sensors_front_raw(void)
{
    return read_raw(SENSOR_C_PORT, SENSOR_C_PIN);
}

static uint8_t median_u8(uint8_t *v, uint8_t n)
{
    for (uint8_t i = 1; i < n; i++) {
        uint8_t key = v[i];
        int8_t j = (int8_t)(i - 1);
        while (j >= 0 && v[j] > key) {
            v[j + 1] = v[j];
            j--;
        }
        v[j + 1] = key;
    }
    return v[n / 2];
}

void sensors_read(sensors_t *out)
{
    uint8_t f[SENSOR_SAMPLES];
    uint8_t l[SENSOR_SAMPLES];
    uint8_t r[SENSOR_SAMPLES];

    for (uint8_t i = 0; i < SENSOR_SAMPLES; i++) {
        f[i] = read_raw(SENSOR_C_PORT, SENSOR_C_PIN);
        l[i] = read_raw(SENSOR_L_PORT, SENSOR_L_PIN);
        r[i] = read_raw(SENSOR_R_PORT, SENSOR_R_PIN);
        if (i + 1 < SENSOR_SAMPLES) {
            HAL_Delay(SENSOR_SAMPLE_GAP_MS);
        }
    }

    out->front = median_u8(f, SENSOR_SAMPLES) != 0;
    out->left  = median_u8(l, SENSOR_SAMPLES) != 0;
    out->right = median_u8(r, SENSOR_SAMPLES) != 0;
}

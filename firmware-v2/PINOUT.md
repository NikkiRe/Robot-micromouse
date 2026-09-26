# Распиновка v2 и правки в CubeMX

Плата STM32F401CCU6 (Black Pill, WeAct), логика и моторы 3.3 В. Базовая
распиновка сохранена, добавлены ШИМ на TIM1 и кнопка.

## Таблица

| Сигнал | Пин | Режим в CubeMX | Примечание |
|---|---|---|---|
| AIN1 (правый мотор) | PA5 | GPIO_Output | как в базе |
| AIN2 (правый мотор) | PA6 | GPIO_Output | как в базе |
| BIN1 (левый мотор) | PA2 | GPIO_Output | как в базе |
| BIN2 (левый мотор) | PA3 | GPIO_Output | как в базе |
| STBY | PA9 | GPIO_Output | в `robot.ioc` был занят под `TIM1_CH2`, освободить |
| PWMA (правый мотор) | PA8 | TIM1_CH1, PWM Generation | в базе GPIO_Output, постоянно HIGH |
| PWMB (левый мотор) | PA10 | TIM1_CH3, PWM Generation | новый провод от PWMB драйвера к PA10 |
| ИК правый | PB0 | GPIO_Input, Pull-up | как в базе |
| ИК левый | PB1 | GPIO_Input, Pull-up | как в базе |
| ИК центральный | PA4 | GPIO_Input, Pull-up | как в базе |
| LED | PC13 | GPIO_Output | активный LOW |
| Кнопка KEY | PA0 | GPIO_Input, Pull-up | выбор режима и старт |
| USB DFU | PA11, PA12 | не трогать | нужны загрузчику |
| резерв | PB8, PB9 | GPIO_Input, Pull-up | не используются |

## Правки в `robot.ioc`

Периферию v2 инициализирует сама (`motors.c`, `sensors.c`, `main.c`), от
CubeMX нужны тактирование, `stm32f4xx_it.c`, `stm32f4xx_hal_msp.c`, стартап
и HAL. `.ioc` всё равно стоит поправить:

1. PA9: снять `S_TIM1_CH2` (строки `PA9.Signal=S_TIM1_CH2`, `SH.S_TIM1_CH2.*`,
   `TIM1.Channel-PWM Generation2 CH2`), назначить `GPIO_Output`, метка
   `MOTOR_STBY`. Штатный `HAL_TIM_MspPostInit()` из CubeMX иначе переводит PA9
   в TIM1_CH2, а это STBY драйвера. В v2 эта функция не вызывается, GPIO ШИМ
   настраивается в `motors_init()`.
2. TIM1: Clock Source = Internal Clock, Channel1 = `PWM Generation CH1`
   (PA8), Channel3 = `PWM Generation CH3` (PA10). Prescaler 0, Period 799,
   PWM mode 1, полярность High; фактически задаётся в `motors_init()` из
   `MOTOR_PWM_FREQ_HZ`.
3. PA8: убрать из `GPIO_Output`, теперь `TIM1_CH1`.
4. PA10: `TIM1_CH3`.
5. PA0: `GPIO_Input`, Pull-up, метка `BUTTON`. KEY замыкает на GND.
6. PC13: `GPIO_Output`, метка `LED`.
7. PA4, PB0, PB1: `GPIO_Input`, Pull-up.

После генерации не заменять `Core/Src/main.c` из v2 сгенерированным: в нём
нет секций `USER CODE`. Из вывода CubeMX брать только `stm32f4xx_it.c`,
`stm32f4xx_hal_msp.c`, `system_stm32f4xx.c`, `syscalls.c`, `sysmem.c`,
стартап и `Drivers/`.

## Почему PWMB на PA10

В базовой схеме PWMB драйвера к МК не подключён, ШИМ есть только у правого
мотора. Без энкодеров робот едет прямо, только если моторы крутятся
одинаково, а N20 разбросаны по оборотам на 5–10 %; если быстрее левый,
замедлить его нечем. Поэтому PWMB заведён на PA10 (TIM1_CH3, AF1): оба
мотора получают своё заполнение, курс выравнивается `MOTOR_TRIM_LEFT/RIGHT`,
скорость — `NAV_SPEED_PCT`.

Для платы без этого провода в `motors.h` есть `MOTORS_PWMB_ON_PA10 = 0`:
левый мотор всегда на полной, правый подстраивается `MOTOR_TRIM_RIGHT`,
`NAV_SPEED_PCT` не действует.

## Почему TIM1

Каналы TIM1 выведены на PA8/PA9/PA10/PA11. PA9 занят STBY, PA11 — USB,
остаются PA8 и PA10. Тактирование от APB2 16 МГц, период 800 тактов даёт
20 кГц — выше слышимого и в пределах допустимого для TB6612FNG (до 100 кГц).
Главный выход (MOE) включает `HAL_TIM_PWM_Start()`.

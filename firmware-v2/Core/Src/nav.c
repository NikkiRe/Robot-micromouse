#include "nav.h"
#include "main.h"
#include "motors.h"
#include "sensors.h"

static maze_t       maze;
static maze_dist_t  dist;
static uint8_t      pos_x;
static uint8_t      pos_y;
static dir_t        heading;
static nav_state_t  state = NAV_IDLE;
static uint16_t     steps;

nav_state_t nav_state(void)
{
    return state;
}

void nav_stop(void)
{
    motors_brake();
    HAL_Delay(NAV_SETTLE_MS);
    motors_coast();
}

void nav_forward_cell(void)
{
    uint32_t t0 = HAL_GetTick();
    motors_set(NAV_SPEED_PCT, NAV_SPEED_PCT);

    while (HAL_GetTick() - t0 < FORWARD_CELL_MS) {
#if NAV_FRONT_STOP
        if (HAL_GetTick() - t0 > FORWARD_CELL_MS / 2 && sensors_front_raw()) {
            break;
        }
#endif
    }
    nav_stop();
}

void nav_turn_left90(void)
{
    motors_set(-NAV_SPEED_PCT, NAV_SPEED_PCT);
    HAL_Delay(TURN90_MS);
    nav_stop();
}

void nav_turn_right90(void)
{
    motors_set(NAV_SPEED_PCT, -NAV_SPEED_PCT);
    HAL_Delay(TURN90_MS);
    nav_stop();
}

void nav_turn180(void)
{
    motors_set(NAV_SPEED_PCT, -NAV_SPEED_PCT);
    HAL_Delay(TURN180_MS);
    nav_stop();
}

static void turn_to(dir_t d)
{
    uint8_t rel = (uint8_t)((d - heading + 4) & 3);
    switch (rel) {
    case 0:  break;
    case 1:  nav_turn_right90(); break;
    case 2:  nav_turn180();      break;
    case 3:  nav_turn_left90();  break;
    default: break;
    }
    heading = d;
}

static void observe_here(void)
{
    sensors_t s;
    sensors_read(&s);
    maze_observe(&maze, pos_x, pos_y, heading, s.front, s.left, s.right);
}

static bool step_towards(const maze_pos_t *targets, uint8_t n, bool known_only)
{
    dir_t d;

    maze_flood(&maze, targets, n, known_only, dist);
    if (!maze_best_dir(&maze, dist, pos_x, pos_y, heading, known_only, &d)) {
        return false;
    }

    turn_to(d);
    nav_forward_cell();
    maze_step(&pos_x, &pos_y, d);
    return true;
}

static void reset_pose(void)
{
    pos_x   = 0;
    pos_y   = 0;
    heading = DIR_N;
}

void nav_init(void)
{
    maze_init(&maze);
    reset_pose();
    steps = 0;
    state = NAV_EXPLORE;
}

void nav_run(void)
{
    maze_pos_t center[4];
    maze_pos_t start = { 0, 0 };
    maze_center_targets(center);

    if (state == NAV_IDLE) {
        nav_init();
    }

    for (;;) {
        switch (state) {

        case NAV_EXPLORE:
            led_set(false);
            observe_here();
            if (maze_is_center(pos_x, pos_y)) {
                nav_stop();
                led_blink(3, 150);
                HAL_Delay(500);
                state = NAV_RETURN;
                break;
            }
            if (!step_towards(center, 4, false) || ++steps > NAV_MAX_STEPS) {
                state = NAV_ERROR;
            }
            break;

        case NAV_RETURN:
            led_set(true);
            observe_here();
            HAL_Delay(60);
            led_set(false);
            if (pos_x == 0 && pos_y == 0) {
                nav_stop();
                state = NAV_WAIT_RUN;
                break;
            }
            if (!step_towards(&start, 1, false) || ++steps > NAV_MAX_STEPS) {
                state = NAV_ERROR;
            }
            break;

        case NAV_WAIT_RUN:
            /* робота руками ставят в (0,0) носом на север, потом кнопка */
            led_toggle();
            HAL_Delay(250);
            if (button_pressed()) {
                button_wait_release();
                led_set(false);
                HAL_Delay(NAV_START_DELAY_MS);
                reset_pose();
                steps = 0;
                state = NAV_SPEED_RUN;
            }
            break;

        case NAV_SPEED_RUN:
            led_set(true);
            observe_here();
            if (maze_is_center(pos_x, pos_y)) {
                nav_stop();
                state = NAV_DONE;
                break;
            }
            if (!step_towards(center, 4, true) || ++steps > NAV_MAX_STEPS) {
                state = NAV_ERROR;
            }
            break;

        case NAV_DONE:
            motors_coast();
            led_blink(3, 100);
            HAL_Delay(700);
            if (button_pressed()) {
                button_wait_release();
                HAL_Delay(NAV_START_DELAY_MS);
                reset_pose();
                steps = 0;
                state = NAV_SPEED_RUN;
            }
            break;

        case NAV_ERROR:
        default:
            motors_coast();
            motors_enable(false);
            for (;;) {
                led_toggle();
                HAL_Delay(80);
            }
        }
    }
}

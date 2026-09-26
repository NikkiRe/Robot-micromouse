#ifndef NAV_H
#define NAV_H

#include <stdint.h>
#include <stdbool.h>
#include "maze.h"

#define NAV_SPEED_PCT       60

/* калибровать */
#define FORWARD_CELL_MS     700
#define TURN90_MS           450
#define TURN180_MS          840

#define NAV_SETTLE_MS       150
#define NAV_START_DELAY_MS  2000
#define NAV_FRONT_STOP      1
#define NAV_MAX_STEPS       1024

typedef enum {
    NAV_IDLE = 0,
    NAV_EXPLORE,
    NAV_RETURN,
    NAV_WAIT_RUN,
    NAV_SPEED_RUN,
    NAV_DONE,
    NAV_ERROR
} nav_state_t;

void        nav_init(void);
void        nav_run(void);
nav_state_t nav_state(void);

void nav_forward_cell(void);
void nav_turn_left90(void);
void nav_turn_right90(void);
void nav_turn180(void);
void nav_stop(void);

#endif

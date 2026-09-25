#ifndef MAZE_H
#define MAZE_H

#include <stdint.h>
#include <stdbool.h>

#define MAZE_SIZE        16
#define MAZE_CELLS       (MAZE_SIZE * MAZE_SIZE)
#define MAZE_UNREACHABLE 255u

#define WALL_N        0x01u
#define WALL_E        0x02u
#define WALL_S        0x04u
#define WALL_W        0x08u
#define WALL_MASK     0x0Fu
#define CELL_VISITED  0x10u

typedef enum {
    DIR_N = 0,
    DIR_E = 1,
    DIR_S = 2,
    DIR_W = 3
} dir_t;

typedef struct {
    uint8_t cell[MAZE_SIZE][MAZE_SIZE];
} maze_t;

typedef struct {
    uint8_t x;
    uint8_t y;
} maze_pos_t;

typedef uint8_t maze_dist_t[MAZE_SIZE][MAZE_SIZE];

dir_t maze_dir_left(dir_t d);
dir_t maze_dir_right(dir_t d);
dir_t maze_dir_back(dir_t d);
void  maze_step(uint8_t *x, uint8_t *y, dir_t d);
bool  maze_in_bounds(int x, int y);

void  maze_init(maze_t *m);
void  maze_set_wall(maze_t *m, uint8_t x, uint8_t y, dir_t d);
bool  maze_has_wall(const maze_t *m, uint8_t x, uint8_t y, dir_t d);
void  maze_mark_visited(maze_t *m, uint8_t x, uint8_t y);
bool  maze_is_visited(const maze_t *m, uint8_t x, uint8_t y);

void  maze_observe(maze_t *m, uint8_t x, uint8_t y, dir_t heading,
                   bool front, bool left, bool right);

bool  maze_is_center(uint8_t x, uint8_t y);
void  maze_center_targets(maze_pos_t out[4]);

void  maze_flood(const maze_t *m, const maze_pos_t *targets, uint8_t n_targets,
                 bool known_only, maze_dist_t dist);

bool  maze_best_dir(const maze_t *m, const maze_dist_t dist,
                    uint8_t x, uint8_t y, dir_t heading, bool known_only,
                    dir_t *out);

#endif

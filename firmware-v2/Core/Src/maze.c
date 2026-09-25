#include "maze.h"
#include <string.h>

static const int8_t  DX[4] = { 0, 1, 0, -1 };
static const int8_t  DY[4] = { 1, 0, -1, 0 };
static const uint8_t WALL_BIT[4] = { WALL_N, WALL_E, WALL_S, WALL_W };

dir_t maze_dir_left(dir_t d)  { return (dir_t)((d + 3) & 3); }
dir_t maze_dir_right(dir_t d) { return (dir_t)((d + 1) & 3); }
dir_t maze_dir_back(dir_t d)  { return (dir_t)((d + 2) & 3); }

void maze_step(uint8_t *x, uint8_t *y, dir_t d)
{
    *x = (uint8_t)(*x + DX[d]);
    *y = (uint8_t)(*y + DY[d]);
}

bool maze_in_bounds(int x, int y)
{
    return x >= 0 && x < MAZE_SIZE && y >= 0 && y < MAZE_SIZE;
}

void maze_init(maze_t *m)
{
    memset(m, 0, sizeof(*m));
    for (uint8_t i = 0; i < MAZE_SIZE; i++) {
        m->cell[i][0]             |= WALL_S;
        m->cell[i][MAZE_SIZE - 1] |= WALL_N;
        m->cell[0][i]             |= WALL_W;
        m->cell[MAZE_SIZE - 1][i] |= WALL_E;
    }
}

void maze_set_wall(maze_t *m, uint8_t x, uint8_t y, dir_t d)
{
    if (!maze_in_bounds(x, y)) {
        return;
    }
    m->cell[x][y] |= WALL_BIT[d];

    int nx = x + DX[d];
    int ny = y + DY[d];
    if (maze_in_bounds(nx, ny)) {
        m->cell[nx][ny] |= WALL_BIT[maze_dir_back(d)];
    }
}

bool maze_has_wall(const maze_t *m, uint8_t x, uint8_t y, dir_t d)
{
    if (!maze_in_bounds(x, y)) {
        return true;
    }
    return (m->cell[x][y] & WALL_BIT[d]) != 0;
}

void maze_mark_visited(maze_t *m, uint8_t x, uint8_t y)
{
    if (maze_in_bounds(x, y)) {
        m->cell[x][y] |= CELL_VISITED;
    }
}

bool maze_is_visited(const maze_t *m, uint8_t x, uint8_t y)
{
    if (!maze_in_bounds(x, y)) {
        return false;
    }
    return (m->cell[x][y] & CELL_VISITED) != 0;
}

void maze_observe(maze_t *m, uint8_t x, uint8_t y, dir_t heading,
                  bool front, bool left, bool right)
{
    if (front) {
        maze_set_wall(m, x, y, heading);
    }
    if (left) {
        maze_set_wall(m, x, y, maze_dir_left(heading));
    }
    if (right) {
        maze_set_wall(m, x, y, maze_dir_right(heading));
    }
    maze_mark_visited(m, x, y);
}

bool maze_is_center(uint8_t x, uint8_t y)
{
    const uint8_t c0 = MAZE_SIZE / 2 - 1;
    const uint8_t c1 = MAZE_SIZE / 2;
    return (x == c0 || x == c1) && (y == c0 || y == c1);
}

void maze_center_targets(maze_pos_t out[4])
{
    const uint8_t c0 = MAZE_SIZE / 2 - 1;
    const uint8_t c1 = MAZE_SIZE / 2;
    out[0].x = c0; out[0].y = c0;
    out[1].x = c0; out[1].y = c1;
    out[2].x = c1; out[2].y = c0;
    out[3].x = c1; out[3].y = c1;
}

#define IDX(x, y)  ((uint8_t)(((y) << 4) | (x)))

void maze_flood(const maze_t *m, const maze_pos_t *targets, uint8_t n_targets,
                bool known_only, maze_dist_t dist)
{
    /* tail доходит до 256, поэтому uint16_t */
    static uint8_t queue[MAZE_CELLS];
    uint16_t head = 0;
    uint16_t tail = 0;

    memset(dist, MAZE_UNREACHABLE, MAZE_CELLS);

    for (uint8_t i = 0; i < n_targets; i++) {
        uint8_t tx = targets[i].x;
        uint8_t ty = targets[i].y;
        if (!maze_in_bounds(tx, ty) || dist[tx][ty] != MAZE_UNREACHABLE) {
            continue;
        }
        dist[tx][ty] = 0;
        queue[tail++] = IDX(tx, ty);
    }

    while (head < tail) {
        uint8_t idx = queue[head++];
        uint8_t x = idx & 0x0F;
        uint8_t y = idx >> 4;
        uint8_t d0 = dist[x][y];

        for (uint8_t d = 0; d < 4; d++) {
            if (m->cell[x][y] & WALL_BIT[d]) {
                continue;
            }
            int nx = x + DX[d];
            int ny = y + DY[d];
            if (!maze_in_bounds(nx, ny)) {
                continue;
            }
            if (known_only && !(m->cell[nx][ny] & CELL_VISITED)) {
                continue;
            }
            if (dist[nx][ny] != MAZE_UNREACHABLE) {
                continue;
            }
            dist[nx][ny] = (uint8_t)(d0 + 1);
            queue[tail++] = IDX((uint8_t)nx, (uint8_t)ny);
        }
    }
}

bool maze_best_dir(const maze_t *m, const maze_dist_t dist,
                   uint8_t x, uint8_t y, dir_t heading, bool known_only,
                   dir_t *out)
{
    /* при равных dist первый в списке — меньше поворотов */
    const dir_t order[4] = {
        heading,
        maze_dir_left(heading),
        maze_dir_right(heading),
        maze_dir_back(heading),
    };

    uint8_t best = MAZE_UNREACHABLE;
    bool found = false;

    for (uint8_t i = 0; i < 4; i++) {
        dir_t d = order[i];
        if (maze_has_wall(m, x, y, d)) {
            continue;
        }
        int nx = x + DX[d];
        int ny = y + DY[d];
        if (!maze_in_bounds(nx, ny)) {
            continue;
        }
        if (known_only && !maze_is_visited(m, (uint8_t)nx, (uint8_t)ny)) {
            continue;
        }
        uint8_t nd = dist[nx][ny];
        if (nd == MAZE_UNREACHABLE) {
            continue;
        }
        if (!found || nd < best) {
            best = nd;
            *out = d;
            found = true;
        }
    }
    return found;
}

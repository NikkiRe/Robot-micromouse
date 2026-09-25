#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "maze.h"

static int g_checks = 0;
static int g_failed = 0;

#define CHECK(cond, ...)                                          \
    do {                                                          \
        g_checks++;                                               \
        if (!(cond)) {                                            \
            g_failed++;                                           \
            printf("  FAIL %s:%d: ", __FILE__, __LINE__);         \
            printf(__VA_ARGS__);                                  \
            printf("\n");                                         \
        }                                                         \
    } while (0)

static uint32_t g_rng = 1;
static uint32_t rnd(void)
{
    g_rng = g_rng * 1664525u + 1013904223u;
    return g_rng >> 8;
}

static void print_maze(const maze_t *m, const maze_dist_t dist)
{
    for (int y = MAZE_SIZE - 1; y >= 0; y--) {
        for (int x = 0; x < MAZE_SIZE; x++) {
            printf("+%s", maze_has_wall(m, x, y, DIR_N) ? "----" : "    ");
        }
        printf("+\n");
        for (int x = 0; x < MAZE_SIZE; x++) {
            printf("%s", maze_has_wall(m, x, y, DIR_W) ? "|" : " ");
            if (dist && dist[x][y] != MAZE_UNREACHABLE) {
                printf("%3d ", dist[x][y]);
            } else if (dist) {
                printf("  . ");
            } else {
                printf("    ");
            }
        }
        printf("|\n");
    }
    for (int x = 0; x < MAZE_SIZE; x++) {
        printf("+----");
    }
    printf("+\n");
}

/* эталон другим алгоритмом: релаксация до сходимости */
static void reference_dist(const maze_t *m, const maze_pos_t *targets, int n,
                           bool known_only, maze_dist_t out)
{
    static const int DX[4] = { 0, 1, 0, -1 };
    static const int DY[4] = { 1, 0, -1, 0 };
    int d[MAZE_SIZE][MAZE_SIZE];

    for (int x = 0; x < MAZE_SIZE; x++)
        for (int y = 0; y < MAZE_SIZE; y++)
            d[x][y] = 100000;
    for (int i = 0; i < n; i++)
        d[targets[i].x][targets[i].y] = 0;

    bool changed = true;
    while (changed) {
        changed = false;
        for (int x = 0; x < MAZE_SIZE; x++) {
            for (int y = 0; y < MAZE_SIZE; y++) {
                for (int k = 0; k < 4; k++) {
                    if (maze_has_wall(m, x, y, (dir_t)k)) continue;
                    int nx = x + DX[k], ny = y + DY[k];
                    if (!maze_in_bounds(nx, ny)) continue;
                    if (known_only && !maze_is_visited(m, nx, ny)) continue;
                    if (d[x][y] + 1 < d[nx][ny]) {
                        d[nx][ny] = d[x][y] + 1;
                        changed = true;
                    }
                }
            }
        }
    }
    for (int x = 0; x < MAZE_SIZE; x++)
        for (int y = 0; y < MAZE_SIZE; y++)
            out[x][y] = (d[x][y] >= 100000) ? MAZE_UNREACHABLE : (uint8_t)d[x][y];
}

/* dfs со стеком, потом extra_open случайных дырок для циклов */
static void random_maze(maze_t *m, unsigned seed, int extra_open)
{
    static const int DX[4] = { 0, 1, 0, -1 };
    static const int DY[4] = { 1, 0, -1, 0 };
    bool seen[MAZE_SIZE][MAZE_SIZE];
    maze_pos_t stack[MAZE_CELLS];
    int sp = 0;

    g_rng = seed;
    maze_init(m);

    for (int x = 0; x < MAZE_SIZE; x++)
        for (int y = 0; y < MAZE_SIZE; y++)
            m->cell[x][y] |= WALL_MASK;
    memset(seen, 0, sizeof(seen));

    stack[sp].x = 0; stack[sp].y = 0; sp++;
    seen[0][0] = true;
    while (sp > 0) {
        maze_pos_t c = stack[sp - 1];
        int cand[4], nc = 0;
        for (int k = 0; k < 4; k++) {
            int nx = c.x + DX[k], ny = c.y + DY[k];
            if (maze_in_bounds(nx, ny) && !seen[nx][ny]) cand[nc++] = k;
        }
        if (nc == 0) { sp--; continue; }
        int k = cand[rnd() % nc];
        int nx = c.x + DX[k], ny = c.y + DY[k];

        static const uint8_t bit[4] = { WALL_N, WALL_E, WALL_S, WALL_W };
        m->cell[c.x][c.y] &= (uint8_t)~bit[k];
        m->cell[nx][ny]   &= (uint8_t)~bit[(k + 2) & 3];
        seen[nx][ny] = true;
        stack[sp].x = (uint8_t)nx; stack[sp].y = (uint8_t)ny; sp++;
    }

    for (int i = 0; i < extra_open; i++) {
        int x = rnd() % MAZE_SIZE, y = rnd() % MAZE_SIZE, k = rnd() % 4;
        int nx = x + DX[k], ny = y + DY[k];
        if (!maze_in_bounds(nx, ny)) continue;
        static const uint8_t bit[4] = { WALL_N, WALL_E, WALL_S, WALL_W };
        m->cell[x][y]   &= (uint8_t)~bit[k];
        m->cell[nx][ny] &= (uint8_t)~bit[(k + 2) & 3];
    }

    for (int x = 0; x < MAZE_SIZE; x++)
        for (int y = 0; y < MAZE_SIZE; y++)
            m->cell[x][y] &= WALL_MASK;
}

static bool dists_equal(const maze_dist_t a, const maze_dist_t b)
{
    return memcmp(a, b, MAZE_CELLS) == 0;
}

static void test_empty_maze(void)
{
    printf("[1] пустой лабиринт\n");
    maze_t m;
    maze_pos_t t[4];
    maze_dist_t dist;

    maze_init(&m);
    maze_center_targets(t);
    maze_flood(&m, t, 4, false, dist);

    CHECK(dist[7][7] == 0 && dist[7][8] == 0 && dist[8][7] == 0 && dist[8][8] == 0,
          "центр должен иметь расстояние 0");
    CHECK(dist[0][0] == 14, "dist[0][0]=%d, ожидалось 14", dist[0][0]);
    CHECK(dist[15][15] == 14, "dist[15][15]=%d, ожидалось 14", dist[15][15]);
    CHECK(dist[0][15] == 14, "dist[0][15]=%d, ожидалось 14", dist[0][15]);
    CHECK(dist[7][0] == 7, "dist[7][0]=%d, ожидалось 7", dist[7][0]);
    CHECK(dist[6][7] == 1, "dist[6][7]=%d, ожидалось 1", dist[6][7]);

    for (int x = 0; x < MAZE_SIZE; x++) {
        for (int y = 0; y < MAZE_SIZE; y++) {
            int dx = (x < 7) ? 7 - x : (x > 8 ? x - 8 : 0);
            int dy = (y < 7) ? 7 - y : (y > 8 ? y - 8 : 0);
            CHECK(dist[x][y] == dx + dy, "dist[%d][%d]=%d, ожидалось %d",
                  x, y, dist[x][y], dx + dy);
        }
    }
}

static void test_wall_consistency(void)
{
    printf("[2] согласованность стен\n");
    maze_t m;
    maze_init(&m);

    CHECK(maze_has_wall(&m, 0, 0, DIR_S) && maze_has_wall(&m, 0, 0, DIR_W),
          "у старта должны быть внешние стены S и W");
    CHECK(!maze_has_wall(&m, 0, 0, DIR_N), "у старта не должно быть стены N");

    maze_set_wall(&m, 3, 3, DIR_N);
    CHECK(maze_has_wall(&m, 3, 3, DIR_N), "стена N у (3,3)");
    CHECK(maze_has_wall(&m, 3, 4, DIR_S), "зеркальная стена S у (3,4)");
    CHECK(!maze_has_wall(&m, 3, 3, DIR_E), "лишних стен нет");

    maze_observe(&m, 5, 5, DIR_E, true, true, false);
    CHECK(maze_has_wall(&m, 5, 5, DIR_E), "front при курсе E = стена E");
    CHECK(maze_has_wall(&m, 5, 5, DIR_N), "left при курсе E = стена N");
    CHECK(!maze_has_wall(&m, 5, 5, DIR_S), "right=false — стены S нет");
    CHECK(maze_is_visited(&m, 5, 5), "клетка помечена как осмотренная");
    CHECK(!maze_is_visited(&m, 5, 6), "сосед не осмотрен");

    maze_set_wall(&m, 15, 15, DIR_N);
    maze_set_wall(&m, 0, 0, DIR_W);
    CHECK(maze_has_wall(&m, 15, 15, DIR_N), "стена на границе");

    CHECK(maze_dir_left(DIR_N) == DIR_W && maze_dir_right(DIR_N) == DIR_E &&
          maze_dir_back(DIR_N) == DIR_S, "повороты от N");
    CHECK(maze_dir_left(DIR_W) == DIR_S && maze_dir_right(DIR_W) == DIR_N,
          "повороты от W");
}

static void test_single_gap(void)
{
    printf("[3] стена через всё поле с одним проходом\n");
    maze_t m;
    maze_pos_t t[4];
    maze_dist_t dist;

    maze_init(&m);

    for (uint8_t x = 0; x < MAZE_SIZE - 1; x++) {
        maze_set_wall(&m, x, 3, DIR_N);
    }
    maze_center_targets(t);
    maze_flood(&m, t, 4, false, dist);

    CHECK(dist[15][4] == 10, "dist[15][4]=%d, ожидалось 10", dist[15][4]);
    CHECK(dist[15][3] == 11, "dist[15][3]=%d, ожидалось 11", dist[15][3]);
    CHECK(dist[0][0] == 29, "dist[0][0]=%d, ожидалось 29", dist[0][0]);
    CHECK(dist[0][3] == 26, "dist[0][3]=%d, ожидалось 26", dist[0][3]);

    CHECK(dist[0][4] == 10, "dist[0][4]=%d, ожидалось 10", dist[0][4]);

    uint8_t x = 0, y = 0;
    dir_t h = DIR_N;
    int steps = 0;
    while (!maze_is_center(x, y) && steps < 300) {
        dir_t d;
        CHECK(maze_best_dir(&m, dist, x, y, h, false, &d), "best_dir в (%d,%d)", x, y);
        CHECK(!maze_has_wall(&m, x, y, d), "шаг сквозь стену в (%d,%d)", x, y);
        maze_step(&x, &y, d);
        h = d;
        steps++;
    }
    CHECK(maze_is_center(x, y), "спуск по градиенту должен прийти в центр");
    CHECK(steps == 29, "длина спуска %d, ожидалось 29", steps);

    if (g_failed) print_maze(&m, dist);
}

static void test_unreachable(void)
{
    printf("[4] закрытый центр\n");
    maze_t m;
    maze_pos_t t[4];
    maze_dist_t dist;

    maze_init(&m);

    maze_set_wall(&m, 7, 7, DIR_W); maze_set_wall(&m, 7, 8, DIR_W);
    maze_set_wall(&m, 8, 7, DIR_E); maze_set_wall(&m, 8, 8, DIR_E);
    maze_set_wall(&m, 7, 7, DIR_S); maze_set_wall(&m, 8, 7, DIR_S);
    maze_set_wall(&m, 7, 8, DIR_N); maze_set_wall(&m, 8, 8, DIR_N);

    maze_center_targets(t);
    maze_flood(&m, t, 4, false, dist);

    CHECK(dist[7][7] == 0, "внутри центра 0");
    CHECK(dist[0][0] == MAZE_UNREACHABLE, "старт недостижим");
    CHECK(dist[6][7] == MAZE_UNREACHABLE, "сосед центра недостижим");

    dir_t d;
    CHECK(!maze_best_dir(&m, dist, 0, 0, DIR_N, false, &d),
          "best_dir должен вернуть false, когда пути нет");

    maze_pos_t start = { 0, 0 };
    maze_flood(&m, &start, 1, false, dist);
    CHECK(dist[0][0] == 0 && dist[7][7] == MAZE_UNREACHABLE, "заливка от старта");
    CHECK(dist[15][15] == 30, "dist[15][15]=%d, ожидалось 30", dist[15][15]);
}

static void test_known_only(void)
{
    printf("[5] пессимистичная заливка по осмотренным клеткам\n");
    maze_t m;
    maze_pos_t t[4];
    maze_dist_t dist;

    maze_init(&m);

    for (uint8_t y = 0; y <= 7; y++) maze_mark_visited(&m, 0, y);
    for (uint8_t x = 0; x <= 7; x++) maze_mark_visited(&m, x, 7);

    maze_center_targets(t);
    maze_flood(&m, t, 4, true, dist);

    CHECK(dist[0][0] == 14, "dist[0][0]=%d, ожидалось 14", dist[0][0]);
    CHECK(dist[1][0] == MAZE_UNREACHABLE, "неосмотренная клетка недостижима");
    CHECK(dist[0][7] == 7, "dist[0][7]=%d, ожидалось 7", dist[0][7]);

    CHECK(dist[8][8] == 0, "цель всегда 0");
    CHECK(dist[9][8] == MAZE_UNREACHABLE, "из неосмотренного центра не выходим");

    dir_t d;
    CHECK(maze_best_dir(&m, dist, 0, 0, DIR_N, true, &d) && d == DIR_N,
          "из старта только на север");
    CHECK(maze_best_dir(&m, dist, 0, 7, DIR_N, true, &d) && d == DIR_E,
          "в углу коридора — на восток");

    maze_flood(&m, t, 4, false, dist);
    CHECK(dist[1][0] == 13, "оптимистично dist[1][0]=%d", dist[1][0]);
}

static void test_random_vs_reference(void)
{
    printf("[6] случайные лабиринты против эталонной реализации\n");
    maze_t m;
    maze_pos_t t[4];
    maze_dist_t a, b;
    maze_center_targets(t);

    int reachable = 0;
    for (unsigned seed = 1; seed <= 60; seed++) {
        random_maze(&m, seed, (int)(seed % 7) * 5);

        maze_flood(&m, t, 4, false, a);
        reference_dist(&m, t, 4, false, b);
        CHECK(dists_equal(a, b), "seed=%u: расхождение с эталоном (optimistic)", seed);
        CHECK(a[0][0] != MAZE_UNREACHABLE, "seed=%u: идеальный лабиринт связен", seed);
        if (a[0][0] != MAZE_UNREACHABLE) reachable++;

        for (int x = 0; x < MAZE_SIZE; x++)
            for (int y = 0; y < MAZE_SIZE; y++)
                if (rnd() % 3) maze_mark_visited(&m, x, y);
        maze_flood(&m, t, 4, true, a);
        reference_dist(&m, t, 4, true, b);
        CHECK(dists_equal(a, b), "seed=%u: расхождение с эталоном (known_only)", seed);

        maze_pos_t s = { 0, 0 };
        maze_flood(&m, &s, 1, false, a);
        reference_dist(&m, &s, 1, false, b);
        CHECK(dists_equal(a, b), "seed=%u: расхождение (цель старт)", seed);
    }
    CHECK(reachable == 60, "все 60 лабиринтов связны (%d)", reachable);
}

typedef struct {
    const maze_t *truth;
    maze_t map;
    uint8_t x, y;
    dir_t heading;
    int wall_hits;
    int steps;
} sim_t;

static void sim_observe(sim_t *s)
{
    bool f = maze_has_wall(s->truth, s->x, s->y, s->heading);
    bool l = maze_has_wall(s->truth, s->x, s->y, maze_dir_left(s->heading));
    bool r = maze_has_wall(s->truth, s->x, s->y, maze_dir_right(s->heading));
    maze_observe(&s->map, s->x, s->y, s->heading, f, l, r);
}

static int sim_phase(sim_t *s, const maze_pos_t *targets, int n, bool known_only,
                     int max_steps)
{
    maze_dist_t dist;
    int steps = 0;
    for (;;) {
        sim_observe(s);
        bool at_target = false;
        for (int i = 0; i < n; i++)
            if (targets[i].x == s->x && targets[i].y == s->y) at_target = true;
        if (at_target) return steps;
        if (steps >= max_steps) return -1;

        maze_flood(&s->map, targets, (uint8_t)n, known_only, dist);
        dir_t d;
        if (!maze_best_dir(&s->map, dist, s->x, s->y, s->heading, known_only, &d))
            return -1;
        if (maze_has_wall(s->truth, s->x, s->y, d)) s->wall_hits++;
        s->heading = d;
        maze_step(&s->x, &s->y, d);
        steps++;
        s->steps++;
    }
}

static void test_exploration_sim(void)
{
    printf("[7] симуляция EXPLORE -> RETURN -> SPEED_RUN\n");
    maze_t truth;
    maze_pos_t center[4], start = { 0, 0 };
    maze_center_targets(center);

    int total_explore = 0, total_speed = 0, runs = 0;
    for (unsigned seed = 100; seed < 140; seed++) {
        random_maze(&truth, seed, (int)(seed % 5) * 8);

        sim_t s;
        memset(&s, 0, sizeof(s));
        s.truth = &truth;
        maze_init(&s.map);
        s.heading = DIR_N;

        int e = sim_phase(&s, center, 4, false, 2000);
        CHECK(e > 0, "seed=%u: EXPLORE не дошёл до центра", seed);
        CHECK(maze_is_center(s.x, s.y), "seed=%u: EXPLORE не в центре", seed);

        int r = sim_phase(&s, &start, 1, false, 2000);
        CHECK(r > 0, "seed=%u: RETURN не вернулся на старт", seed);
        CHECK(s.x == 0 && s.y == 0, "seed=%u: RETURN не на старте", seed);

        maze_dist_t dist;
        maze_flood(&s.map, center, 4, true, dist);
        int expected = dist[0][0];
        CHECK(expected != MAZE_UNREACHABLE, "seed=%u: нет известного пути", seed);

        int sp = sim_phase(&s, center, 4, true, 600);
        CHECK(sp > 0, "seed=%u: SPEED_RUN не доехал", seed);
        CHECK(sp == expected, "seed=%u: SPEED_RUN длина %d, flood %d", seed, sp, expected);

        maze_dist_t true_dist;
        maze_flood(&truth, center, 4, false, true_dist);
        CHECK(sp >= true_dist[0][0], "seed=%u: путь короче истинного (%d < %d)",
              seed, sp, true_dist[0][0]);

        CHECK(s.wall_hits == 0, "seed=%u: %d проходов сквозь стену", seed, s.wall_hits);

        if (e > 0 && sp > 0) {
            total_explore += e;
            total_speed += sp;
            runs++;
        }
        if (g_failed && seed == 100) print_maze(&truth, true_dist);
    }
    if (runs) {
        printf("    среднее: исследование %d шагов, скоростной путь %d клеток\n",
               total_explore / runs, total_speed / runs);
    }
}

int main(void)
{
    test_empty_maze();
    test_wall_consistency();
    test_single_gap();
    test_unreachable();
    test_known_only();
    test_random_vs_reference();
    test_exploration_sim();

    printf("\n%d проверок, %d ошибок — %s\n", g_checks, g_failed,
           g_failed ? "FAIL" : "OK");
    return g_failed ? 1 : 0;
}

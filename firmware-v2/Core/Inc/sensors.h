#ifndef SENSORS_H
#define SENSORS_H

#include <stdbool.h>
#include <stdint.h>

#define SENSOR_SAMPLES        5
#define SENSOR_SAMPLE_GAP_MS  2

typedef struct {
    bool front;
    bool left;
    bool right;
} sensors_t;

void sensors_init(void);
void sensors_read(sensors_t *out);
bool sensors_front_raw(void);

#endif

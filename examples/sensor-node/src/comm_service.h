/**
 * @file comm_service.h
 * @brief Receives frames from the UART ISR and keeps statistics.
 *
 * Thread-safe: comm_get_stats() may be called from any task (mutex protected).
 * ISR-safe: only comm_rx_byte_from_isr().
 */
#ifndef COMM_SERVICE_H
#define COMM_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

typedef struct
{
    uint32_t frames_ok;
    uint32_t frames_bad;
    uint32_t overruns;
} comm_stats_t;

int comm_init(void);
void comm_rx_byte_from_isr(uint8_t byte);
void comm_process(void);
int comm_get_stats(comm_stats_t *out, uint32_t timeout_ms);

#endif /* COMM_SERVICE_H */

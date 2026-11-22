#include "comm_service.h"

#include <stddef.h>

#include "frame_parser.h"
#include "osal.h"
#include "ring_buffer.h"

static ring_buffer_t s_rx;
static frame_parser_t s_parser;
static osal_mutex_t s_lock;
static comm_stats_t s_stats;

int comm_init(void)
{
    static const comm_stats_t zero = {0u, 0u, 0u};

    rb_init(&s_rx);
    frame_parser_reset(&s_parser);
    s_stats = zero;
    return (osal_mutex_create(&s_lock) == OSAL_OK) ? 0 : -1;
}

/* @req SN-COM-001 Received bytes are buffered in the ISR and the comm task is woken */
void comm_rx_byte_from_isr(uint8_t byte)
{
    bool woken = false;

    (void)rb_put(&s_rx, byte);
    osal_notify_from_isr(&woken);
    osal_yield_from_isr(woken);
}

/* Called only by the comm task (single owner of the parser). */
void comm_process(void)
{
    uint8_t byte;

    while (rb_get(&s_rx, &byte))
    {
        frame_status_t st = frame_parser_feed(&s_parser, byte);

        if (st == FRAME_INCOMPLETE)
        {
            continue;
        }
        if (osal_mutex_lock(s_lock, 10u) == OSAL_OK)
        {
            if (st == FRAME_OK)
            {
                s_stats.frames_ok++;
            }
            else
            {
                s_stats.frames_bad++;
            }
            osal_mutex_unlock(s_lock);
        }
    }
}

/* @req SN-COM-002 Statistics can be read consistently from any task */
int comm_get_stats(comm_stats_t *out, uint32_t timeout_ms)
{
    if (out == NULL)
    {
        return -2;
    }
    if (osal_mutex_lock(s_lock, timeout_ms) != OSAL_OK)
    {
        return -1;
    }
    *out = s_stats;
    out->overruns = s_rx.overruns;
    osal_mutex_unlock(s_lock);
    return 0;
}

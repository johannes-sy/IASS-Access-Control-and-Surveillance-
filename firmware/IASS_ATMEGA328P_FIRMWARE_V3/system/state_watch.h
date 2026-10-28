#ifndef IASS_STATE_WATCH_H
#define IASS_STATE_WATCH_H
#include <stdint.h>

/* Diffs every actuator's observable state against what was last reported
 * and emits an unsolicited MSG_EVENT frame for anything that changed.
 * Call once per main-loop iteration.
 *
 * This is deliberately one polling diff, not per-call-site event firing
 * scattered across every handler and every actuator tick function -- a
 * command handler can only tell you a command was *accepted*, not that the
 * physical state actually changed (an UNLOCK command on an already-unlocked
 * door changes nothing observable), and it can never see an autonomous
 * change like the door's own auto-relock timeout or a failsafe engaging
 * from a lost heartbeat. Polling the actual state here catches both, with
 * one mechanism, and can't be missed by forgetting to add a call at some
 * new call site later. */
void state_watch_init(void);
void state_watch_poll(uint32_t now);

#endif

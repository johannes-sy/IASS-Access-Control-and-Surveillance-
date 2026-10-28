#ifndef IASS_HANDLERS_H
#define IASS_HANDLERS_H
/* One include, one call (handlers_register_all), to bring every domain's
 * commands into the dispatch table. Adding a new domain later (e.g. a
 * future sensor input) means: write handlers/<domain>_handlers.c with its
 * own _register() function, add one line here and one call in
 * handlers_register_all() -- main.c and command_dispatch.c never change. */
void handlers_register_all(void);
#endif

best advice here is to keep the handlers as small as possible. like, ideally you just want to set a flag indicating the interupt has been received, and do any actual processing inside the main loop.

the reasoning for this is that while the interrupt handler is running, all other interrupts are blocked. this could lead to short triggers or button-presses being missed completely.

some function calls are ok in the handler. e.g. if you need to set the time you can call time.ticks_ms(), or you can turn CVs on/off.

what you don't want to do inside the handler is:
file operations (reading/writing to disk is slow, and will block the interrupts for a long time)
screen operations (same as above; these are slow and will block things)
creating/destroying objects (memory allocation is also slow and involves a lot of hidden function calls)

///

one important quirk of python i don't know if you've run into or not when dealing with accumulators: in python, an integer is not a fixed number of bits. if your integer gets too big, instead of rolling back around to zero, it'll just allocate more memory to it, and keep growing. this can cause problems if you're expecting e.g. a uint8_t to roll back around to zero every 256 increments.
my preferred work-around for this quirk is to do a bitwise & operator with a bitmask to keep the integer to the right size. e.g.

one_byte_counter = (one_byte_counter + n) & 0xff


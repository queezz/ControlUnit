# Prepare IG settings while idle — 4.8.2

Owner requested IG range selection before acquisition. Removed gauge from
the shared acquisition-required set (HTTP and main-thread application).
Kept Remote/fence/holder gates. UI enables gauge mode/range while idle.
MainApp updaters publish the selected settings before returning without
workers; existing start_all_threads reapplies them to the ADC.

481 tests passed, including real MainApp updater calls on an idle fake rig;
strict docs passed. Browser idle fixture accepted range -7 while gas stayed
disabled; Remote-off disabled gauge controls. No console errors. Preview
used loopback 48964 and lab PID 35224; stopped after verification. No rig
commands, push or deployment.

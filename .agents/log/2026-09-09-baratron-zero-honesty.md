# Baratron zero presentation — 4.8.3

Owner asked for an honest indication near zero and a minimum detectable
pressure. Registry identifies Bu MKS 627, 1 Torr FS; Bd 628B, 0.1 Torr FS.
No validated system detection limit is recorded. MKS 627D/627F and 628F
manufacturer documents distinguish resolution and zero-related conditions;
these do not justify assigning a limit to this installed measurement chain.
No numerical detection threshold was invented. Characterization remains
necessary before censoring small positive readings as below a limit.

Implemented Below zero on negative Baratron readouts, with signed residual
retained. Linear plots retain signed values. Log exclusions now say <=0 on
log rather than no data; mixed traces leave gaps across omitted values.
An all-nonpositive log plot explains the constraint instead of drawing an
arbitrary pressure scale. Chart note says detection limit not characterized.

481 Python tests, 4 Node behavior tests and strict docs passed. Browser
verified negative readouts and switching linear/log on synthetic readings;
no rig commands sent. Preview lab PID 39576, loopback port 48964, stopped
after review. Not pushed/deployed.

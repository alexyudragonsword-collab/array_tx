# Bundled clock profiles

Every file here was written by pll_simulator's own exporter at the pinned
commit (`pllsim export <preset> --clock-profile`, pll_simulator@00e48a2f6f7c,
linear model); the `source:` line inside each file says so.  They are the
library's 18 presets as shipped, not measurements: `source: survey` in the
sense of "pll_simulator's published preset", with the preset name as the
reference.  Nothing was edited after export.

Use one with `element.lo.clock_profile: "bundled:<preset>"`; the profile's
L(f) is scaled by `(28 GHz / f0)^2` to the standard's carrier, the usual
reading of a sub-10 GHz PLL behind an ideal multiplier (`arraytx.lo`).

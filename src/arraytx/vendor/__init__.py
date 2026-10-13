"""Adapted copies of the sibling libraries arraytx builds on.

This tree is a VERIFIABLE COPY, not a fork (polar_tx CONTRIBUTING 3): every
file carries an attribution header naming its upstream repository, commit and
path, and ``tools/vendor_check.py --strict`` re-derives the relationship on
every CI run.  Code outside this tree imports only through
``arraytx.vendor.polartx...``.

Pins
----
* ``polartx/`` — polar_tx @ ``008cc90baf180b5519453ffdecf15d20ff51582d`` (its
  ``claude/digital-polar-tx-dev-r0c338`` branch: the four array_tx-driven fixes,
  not yet on polar_tx main),
  ``src/polartx`` minus the GUI surfaces (``guiqt/``, ``guiutil.py``,
  ``appbridge.py``).  Everything else is verbatim, package ``__init__``
  included.  polar_tx's own nested vendor tree comes along unchanged, with
  ITS attribution headers, and is checked against ITS upstreams:
  - ``polartx/vendor/padpd/`` — PA_DPD @ ``44cbcb3`` (``pa/thermal.py`` and
    ``gain_modulation.py`` @ ``08b9725595748b290c76d1b70355f7e6014a709e``),
    ``pa/presets.py`` is polar_tx's extraction (manifest-pinned);
  - ``polartx/vendor/pllsim/`` — pll_simulator @ ``931cfaf`` except
    ``arch/adpll.py`` / ``arch/frac.py`` @ ``d7be4712``, polar_tx's extension
    and extraction, pin frozen for polar_tx's reason (its ROADMAP C5).
* ``polartx/vendor/pllsim/export/clock_profile.py`` — pll_simulator @
  ``00e48a2f6f7c11c0b6f106234f1490493d43e082``.  polar_tx's pllsim pin
  predates the ``export`` package, so this one file is taken from
  pll_simulator HEAD and placed inside the nested pllsim tree so its
  ``..core`` relative imports resolve (``core/jitter.py`` and
  ``core/results.py`` are identical between 931cfaf and 00e48a2).  The
  ``export/__init__.py`` is arraytx's.

Local changes
-------------
None in any ``.py`` body.  The only arraytx-authored lines are the two-line
attribution headers on polar_tx's own files and the ``export/__init__.py``
above.  A change to a vendored body goes upstream first, then gets
re-vendored; if it cannot, it is declared in ``tools/vendor_manifest.json``
with a reason, or it does not happen.
"""

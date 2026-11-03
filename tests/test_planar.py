"""Milestone 2a: the rectangular grid.  One row is the linear array bit for
bit; a column scanned in the y-z plane is that same row; the 2-D neighbour
classes reduce to the 1-D shape along a row; adding a row leaves the first
row's draws alone (invariant 5)."""
import numpy as np
import pytest

from arraytx import ArraySim, config_from_dict, load_config
from arraytx.beam import (beamwidth_3db_deg, far_field, highest_sidelobe_direction, peak_direction_cw,
                          squint_analytic_deg)
from arraytx.coupling import analytic_matrix, build_coupling, survey_matrix
from arraytx.geometry import ArrayGeometry, LinearArray

F0 = 28e9
FS = 1.96608e9


def test_row_major_centred_grid_and_the_one_row_special_case():
    g = ArrayGeometry(4, 2, 0.5, 0.75, F0)
    assert g.n == 8 and list(g.ix) == [0, 1, 2, 3] * 2 and list(g.iy) == [0] * 4 + [1] * 4
    assert abs(g.x_m.sum()) < 1e-18 and abs(g.y_m.sum()) < 1e-18
    assert abs(g.y_m[4] - g.y_m[0] - 0.75 * g.wavelength_m) < 1e-15
    row = LinearArray(4, 0.5, F0)
    assert row.is_linear and np.array_equal(row.positions_m, g.x_m[:4]) and np.array_equal(g.x_m[:4], g.x_m[4:])
    # one row: the milestone-1 delay expression, bit for bit, whatever the planar code does
    assert np.array_equal(row.delays_s(37.0), row.positions_m * np.sin(np.deg2rad(37.0)) / 299_792_458.0)
    with pytest.raises(ValueError):
        ArrayGeometry(0, 1, 0.5, 0.5, F0)


def test_a_column_in_the_yz_plane_is_the_row_in_the_xz_plane_bit_for_bit():
    row = LinearArray(8, 0.5, F0)
    col = ArrayGeometry(1, 8, 0.5, 0.5, F0, plane_phi_deg=90.0)
    for th in (-50.0, 0.0, 12.5, 60.0):
        assert np.array_equal(row.delays_s(th), col.delays_s(th))
    assert np.array_equal(col.plane_m, row.plane_m)
    assert col.aperture_m == row.aperture_m
    # and a 45 deg cut of a square grid sees the diagonal pitch
    sq = ArrayGeometry(2, 2, 0.5, 0.5, F0, plane_phi_deg=45.0)
    assert np.allclose(sorted(sq.plane_m), [-sq.spacing_m / np.sqrt(2), 0.0, 0.0, sq.spacing_m / np.sqrt(2)])


def test_8x8_far_field_gain_beamwidth_and_squint():
    g = ArrayGeometry(8, 8, 0.5, 0.5, F0)
    y = np.exp(2j * np.pi * 50e6 * np.arange(4096) / FS)
    e = far_field(np.tile(y, (64, 1)), g, 0.0, FS, normalize=False)
    assert abs(20 * np.log10(np.abs(e).mean()) - 20 * np.log10(64)) < 1e-6          # 64 elements add in voltage at broadside
    assert abs(beamwidth_3db_deg(g, 0.0) - beamwidth_3db_deg(LinearArray(8, 0.5, F0), 0.0)) < 1e-9   # the x-z cut of 8x8 is an 8-row
    assert abs(beamwidth_3db_deg(g.with_plane(90.0), 0.0) - beamwidth_3db_deg(g, 0.0)) < 1e-9
    meas = peak_direction_cw(g, 60.0, 200e6, "phase") - 60.0
    assert abs(meas - squint_analytic_deg(60.0, F0, 200e6)) < 0.05                   # same squint law in any plane
    assert highest_sidelobe_direction(g, 30.0, "phase") is not None


def test_coupling_classes_reduce_to_the_row_shape_and_are_reciprocal():
    g = ArrayGeometry(4, 2, 0.5, 0.5, F0)
    m = analytic_matrix(g, -16.0, 180.0, -6.0, F0 - 1e9, F0 + 1e9, c1y_rel_db=-3.0, c_diag_rel_db=-9.0).at(F0)
    a1 = 10 ** (-16 / 20)
    assert abs(abs(m[0, 1]) - a1) < 1e-12 and abs(abs(m[0, 2]) - a1 * 10 ** (-6 / 20)) < 1e-12        # x1, x2
    assert abs(abs(m[0, 4]) - a1 * 10 ** (-3 / 20)) < 1e-12 and abs(abs(m[0, 5]) - a1 * 10 ** (-9 / 20)) < 1e-12   # y1, d1
    assert m[0, 3] == 0 and m[0, 6] == 0 and m[0, 7] == 0                              # x3, (2,1), (3,1) are not coupled
    assert np.allclose(m, m.T)
    # the first row's block IS the 4-element matrix of milestone 1, bit for bit
    row = analytic_matrix(4, -16.0, 180.0, -6.0, F0 - 1e9, F0 + 1e9).at(F0)
    assert np.array_equal(m[:4, :4], row)
    grid = np.linspace(F0 - 1e9, F0 + 1e9, 5)
    s2 = survey_matrix(g, -16.0, 180.0, -6.0, F0, g.spacing_m, grid)
    s1 = survey_matrix(4, -16.0, 180.0, -6.0, F0, g.spacing_m, grid)
    assert np.array_equal(s2.s[:, :4, :4], s1.s)
    # the diagonal pair's phase slope is the sqrt(2)-pitch delay
    ph = np.unwrap(np.angle(s2.s[:, 0, 5]))
    slope = (ph[-1] - ph[0]) / (grid[-1] - grid[0])
    assert abs(slope + 2 * np.pi * np.hypot(g.spacing_m, g.spacing_y_m) / 299_792_458.0) < 1e-12


def test_adding_a_row_keeps_the_first_rows_draws_and_a_planar_sim_runs():
    a = ArraySim(config_from_dict({"array": {"n_elements": 4}}))
    b = ArraySim(config_from_dict({"array": {"n_elements": 4, "n_rows": 2}}))
    assert b.geom.n == 8 and all(a.elements[k].errors == b.elements[k].errors for k in range(4))
    assert all(a.elements[k].run_seed == b.elements[k].run_seed for k in range(4))
    assert len(b.coupling.nonzero_pairs()) == 40                                        # 4x2: 12 x1 + 8 x2 + 8 y1 + 12 d1
    r = b.run(30.0, "none")
    assert r.ys.shape[0] == 8 and r.beam.domain == "ota" and r.sidelobe_deg is not None
    cfg = load_config("configs/fr2_4el_survey.yaml")
    assert cfg.array.n_rows == 1 and cfg.beam.plane_phi_deg == 0.0                     # the shipped configs are unchanged
    assert build_coupling(cfg, ArraySim(cfg).geom, FS).n == 4
    with pytest.raises(ValueError):
        config_from_dict({"array": {"n_rows": 0}})

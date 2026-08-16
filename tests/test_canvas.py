from browsrrr.canvas import stretched_size


def test_no_growth_when_subwindow_inside():
    assert stretched_size(1000, 800, 10, 10, 400, 300) == (1000, 800)


def test_grows_to_fit_subwindow():
    assert stretched_size(1000, 800, 900, 700, 400, 300) == (1324, 1024)
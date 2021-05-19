from utilsd.search import Choice, sample_from, iterate_over


def test_sample():
    space = {
        'sensors': {
            'position': Choice([1, 2, 3]),
            'velocity': Choice([-1, 0, 1]),
        },
        'ext_controller': Choice(['a', 'b', 'c']),
        'inner_state': [Choice([0.5, 1.5]), Choice([2, 5])]
    }
    sample = sample_from(space)
    assert len(sample['_meta']) == 5

    assert len(set([str(sample['_meta']) for sample in iterate_over(space)])) == 108
    assert len(list(iterate_over(space))) == 108

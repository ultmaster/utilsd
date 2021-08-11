from pathlib import Path

from utilsd.search import Choice, Evaluation, sample_from, iterate_over, size, run_commands
from utilsd.search.runner import MemQueueRunner


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
    assert len(list(iterate_over(space))) == size(space)


def test_sample_with_evaluation():
    space = {
        'sensors': {
            'eval_a': Evaluation(lambda sample: sample['sensors']['position'] + 1),
            'position': Choice([1, 2, 3]),
            'velocity': Choice([-1, 0, 1]),
        },
        'ext_controller': Choice(['a', 'b', 'c']),
        'inner_state': [Choice([0.5, 1.5]), Choice([2, 5])]
    }
    sample = sample_from(space)
    assert sample['sensors']['eval_a'] == sample['sensors']['position'] + 1
    assert len(sample['_meta']) == 6

    assert len(set([str(sample['_meta']) for sample in iterate_over(space)])) == 108
    assert len(list(iterate_over(space))) == 108
    assert len(list(iterate_over(space))) == size(space)

    for sample in iterate_over(space):
        assert sample['sensors']['eval_a'] == sample['sensors']['position'] + 1


def test_submit_via_memqueue():
    trials = {
        'abc': 'echo 1',
        'cde': 'cat /etc/profile',
        'ggg': 'python -c "import time; print(time.time())"',
        'env': 'python -c "import os; print(os.environ[\'PT_OUTPUT_DIR\'])"',
    }
    exp_dir = Path('.cache')
    exp_dir.mkdir(exist_ok=True, parents=True)
    run_commands(trials, MemQueueRunner(exp_dir, '127.0.0.1', '6379'))


if __name__ == '__main__':
    test_submit_via_memqueue()

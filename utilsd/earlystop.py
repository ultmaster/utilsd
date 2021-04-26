from enum import Enum

from .logging import print_log


class EarlyStopStatus(str, Enum):
    BEST = 'best'
    STOP = 'stop'
    HOLD = 'hold'


class EarlyStop:
    def __init__(self, mode='max', patience=10, threshold=1e-3, threshold_mode='rel'):
        self.mode = mode
        self.patience = patience
        self.threshold = threshold
        self.threshold_mode = threshold_mode
        self.best = None
        self.num_bad_epochs = 0

        self._init_is_better(mode=mode, threshold=threshold,
                             threshold_mode=threshold_mode)

    def is_better(self, a, best):
        if self.mode == 'min' and self.threshold_mode == 'rel':
            rel_epsilon = 1. - self.threshold
            return a < best * rel_epsilon

        elif self.mode == 'min' and self.threshold_mode == 'abs':
            return a < best - self.threshold

        elif self.mode == 'max' and self.threshold_mode == 'rel':
            rel_epsilon = self.threshold + 1.
            return a > best * rel_epsilon

        else:  # mode == 'max' and epsilon_mode == 'abs':
            return a > best + self.threshold

    def _init_is_better(self, mode, threshold, threshold_mode):
        if mode not in {'min', 'max'}:
            raise ValueError('mode ' + mode + ' is unknown!')
        if threshold_mode not in {'rel', 'abs'}:
            raise ValueError('threshold mode ' + threshold_mode + ' is unknown!')

        if mode == 'min':
            self.best = float('inf')
        else:  # mode == 'max':
            self.best = float('-inf')

        self.mode = mode
        self.threshold = threshold
        self.threshold_mode = threshold_mode

    def step(self, metrics):
        # convert `metrics` to float, in case it's a zero-dim Tensor
        current = float(metrics)

        if self.is_better(current, self.best):
            self.best = current
            print_log(f'Earlystop hit best record: {self.best}', __name__)
            self.num_bad_epochs = 0
            return EarlyStopStatus.BEST

        self.num_bad_epochs += 1
        if self.num_bad_epochs > self.patience:
            print_log(f'Earlystop running out of patience ({self.patience})', __name__)
            return EarlyStopStatus.STOP  # should earlystop
        print_log(f'Earlystop patience {self.num_bad_epochs} out of {self.patience}', __name__)
        return EarlyStopStatus.HOLD

    def load_state_dict(self, state_dict):
        self.best = state_dict['best']
        self.num_bad_epochs = state_dict['num_bad_epochs']

    def state_dict(self):
        return {
            'best': self.best,
            'num_bad_epochs': self.num_bad_epochs
        }

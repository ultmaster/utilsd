from .import_class import BaseBar


class SubBar(BaseBar):
    def __init__(self, a: int):
        self.a = a

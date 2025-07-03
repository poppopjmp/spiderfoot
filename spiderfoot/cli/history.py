"""
History and spooling utilities for SpiderFoot CLI.
"""
import codecs

class CLIHistory:
    def __init__(self, history_file):
        self.history_file = history_file

    def add(self, line):
        with codecs.open(self.history_file, "a", encoding="utf-8") as f:
            f.write(line)
            f.write('\n')

    def load(self):
        try:
            with codecs.open(self.history_file, "r", encoding="utf-8") as f:
                return [line.strip() for line in f.readlines()]
        except Exception:
            return []

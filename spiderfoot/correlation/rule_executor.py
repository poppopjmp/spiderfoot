import logging
from copy import deepcopy
from spiderfoot.correlation.rule_loader import RuleLoader

class RuleExecutionStrategy:
    """Base class for pluggable rule execution strategies."""
    def execute(self, dbh, rule, scan_ids):
        raise NotImplementedError

class DefaultRuleExecutionStrategy(RuleExecutionStrategy):
    def execute(self, dbh, rule, scan_ids):
        # Placeholder: implement default rule logic here
        return {
            'meta': rule['meta'],
            'result': f"Processed rule {rule['meta']['name']} for scans {scan_ids}"
        }

class RuleExecutor:
    _strategy_registry = {}
    _event_hooks = {
        'pre_rule': [],
        'post_rule': [],
        'pre_aggregate': [],
        'post_aggregate': [],
    }

    @classmethod
    def register_strategy(cls, rule_type, strategy):
        cls._strategy_registry[rule_type] = strategy

    @classmethod
    def register_event_hook(cls, hook_name, func):
        if hook_name in cls._event_hooks:
            cls._event_hooks[hook_name].append(func)

    def __init__(self, dbh, rules, scan_ids=None):
        self.log = logging.getLogger("spiderfoot.correlation.executor")
        self.dbh = dbh
        self.rules = rules
        self.scan_ids = scan_ids if scan_ids else []
        self.results = {}

    def run(self):
        for rule in self.rules:
            if not rule.get('enabled', True):
                self.log.info(f"Skipping disabled rule: {rule.get('id', rule.get('meta', {}).get('name', 'unknown'))}")
                continue
            try:
                for hook in self._event_hooks['pre_rule']:
                    hook(rule, self.scan_ids)
                rule_result = self.process_rule(rule)
                for hook in self._event_hooks['post_rule']:
                    hook(rule, rule_result, self.scan_ids)
                self.results[rule.get('id', rule.get('meta', {}).get('name', 'unknown'))] = rule_result
            except Exception as e:
                self.log.error(f"Error processing rule {rule.get('id', rule.get('meta', {}).get('name', 'unknown'))}: {e}")
        return self.results

    def process_rule(self, rule):
        rule_type = rule.get('meta', {}).get('type', 'default')
        strategy = self._strategy_registry.get(rule_type, DefaultRuleExecutionStrategy())
        return strategy.execute(self.dbh, rule, self.scan_ids)

# Example: Register a custom strategy for a new rule type
# class CustomRuleStrategy(RuleExecutionStrategy):
#     def execute(self, dbh, rule, scan_ids):
#         # Custom logic here
#         return {...}
# RuleExecutor.register_strategy('custom_type', CustomRuleStrategy())

# Example: Register an event hook
# def my_pre_rule_hook(rule, scan_ids):
#     print(f"Pre-processing rule: {rule.get('id')}")
# RuleExecutor.register_event_hook('pre_rule', my_pre_rule_hook)

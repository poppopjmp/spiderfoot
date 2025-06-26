import logging

class ResultAggregator:
    def __init__(self):
        self.log = logging.getLogger("spiderfoot.correlation.aggregator")

    def aggregate(self, results, method='count'):
        # Example: aggregate results by method
        if method == 'count':
            return len(results)
        # Add more aggregation methods as needed
        return results

"""List the fixed authoring sample in seeded, stratified order."""
import json
import random
from collections import defaultdict

import yaml

from .common import ROOT, responses


def main():
    groups = defaultdict(list)
    for row in responses():
        case = yaml.safe_load((ROOT / 'cases/dev' / (row['case_id'] + '.yaml')).read_text())
        groups[case['flaw_type']].append(dict(response_id=row['response_id'], case_id=row['case_id']))
    if len(groups) != 6 or any(len(rows) != 10 for rows in groups.values()):
        raise ValueError('Authoring set must contain ten responses per flaw category, including valid')
    rng = random.Random(17)
    for category in sorted(groups):
        rows = sorted(groups[category], key=lambda row: row['response_id'])
        rng.shuffle(rows)
        print(json.dumps(dict(category=category, responses=rows)))


if __name__ == '__main__':
    main()

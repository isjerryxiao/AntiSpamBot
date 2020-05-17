#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from re import compile
from utils import find_cjk_letters, print_traceback

MAX_SCORE = 100
ACCEPTABLE_CJK_LENGTH = 10

RULES = [
    {'type': 'search', 'regex': '(?i)q[^aw]{0,2}q', 'score': 80},
    {'type': 'search', 'regex': '微.{0,2}信' , 'score': 80},
    {'type': 'search', 'regex': '电.{0,2}报' , 'score': 30},
    {'type': 'search', 'regex': '拉.{0,2}人' , 'score': 80},
    {'type': 'search', 'regex': '推.{0,2}广' , 'score': 80},
]

for r in RULES:
    r['compiled'] = getattr(compile(r['regex']), r['type'])

def _length_score(full_name: str) -> int:
    try:
        num_cjk = len(find_cjk_letters(full_name))
    except Exception:
        num_cjk = 0
        print_traceback()
    if num_cjk <= ACCEPTABLE_CJK_LENGTH:
        return 0
    else:
        return int(2.2**(num_cjk - ACCEPTABLE_CJK_LENGTH))

def spam_score(full_name: str) -> int:
    '''
        returns a int score between 0 to 100 according to predefined RULES
    '''
    score = 0
    score += _length_score(full_name)
    if score >= MAX_SCORE:
        return MAX_SCORE
    for r in RULES:
        if r['compiled'](full_name):
            score += r['score']
        if score >= MAX_SCORE:
            return MAX_SCORE
    return score

if __name__ == "__main__":
    import sys
    n = sys.argv[1]
    print("name:", n, "score:", spam_score(n))

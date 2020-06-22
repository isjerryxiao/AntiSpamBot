#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from re import compile
from utils import find_cjk_letters, print_traceback

MAX_SCORE = 100
ACCEPTABLE_CJK_LENGTH = 10

RULES = [
    {'type': 'search', 'regex': '(?i)q[^aw]{0,2}q', 'score': 90},
    {'type': 'search', 'regex': '(?i)[^a-z]vx[^a-z]', 'score': 90},
    {'type': 'search', 'regex': '微.{0,2}信' , 'score': 90},
    {'type': 'search', 'regex': '电.{0,2}报' , 'score': 50},
    {'type': 'search', 'regex': '拉.{0,2}人' , 'score': 90},
    {'type': 'search', 'regex': '币.{0,2}圈' , 'score': 90},
    {'type': 'search', 'regex': '优.{0,2}质' , 'score': 30},
    {'type': 'search', 'regex': '广.{0,2}告' , 'score': 90},
    {'type': 'search', 'regex': '出.{0,2}售' , 'score': 90},
    {'type': 'search', 'regex': '售.{0,2}卖' , 'score': 90},
    {'type': 'search', 'regex': '客.{0,2}服' , 'score': 30},
    {'type': 'search', 'regex': '(加|增).{0,2}粉' , 'score': 90},
    {'type': 'search', 'regex': '点.{0,2}赞' , 'score': 90},
    {'type': 'search', 'regex': '评.{0,2}论' , 'score': 90},
    {'type': 'search', 'regex': '小.{0,2}号' , 'score': 30},
    {'type': 'search', 'regex': '批.{0,2}量' , 'score': 90},
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

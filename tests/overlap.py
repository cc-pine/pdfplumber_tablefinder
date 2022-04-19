import time

import numpy as np
from pdfplumber.table import naive_get_overlapped_bboxes_pairs, get_overlapped_bboxes_pairs


def test1():
    bbox1_list = [(1, 2, 3, 4), (3, 2, 4, 4), (4, 2, 6, 4), (2.0, 4.0, 5.0, 9.0)]

    bbox2_list = [
        (1.2, 2.2, 2.8, 3.8),
        (6, 2, 8, 5),
        (8, 10, 10, 12),
        (1.4, 2.4, 6, 3.8),
    ]

    overlap1 = get_overlapped_bboxes_pairs(bbox1_list, bbox2_list)
    overlap2 = naive_get_overlapped_bboxes_pairs(bbox1_list, bbox2_list)

    print(overlap1)
    print(overlap2)

    assert overlap1.sort() == overlap2.sort()


def gen_rect():
    x1 = int(np.random.random() * 100)
    y1 = int(np.random.random() * 100)
    x2 = x1 + int(np.random.random() * 100)
    y2 = y1 + int(np.random.random() * 100)
    return (x1, y1, x2, y2)


def test2(n_rec=100, seed=0):
    np.random.seed(seed)
    bbox1_list = [gen_rect() for _ in range(n_rec)]
    bbox2_list = [gen_rect() for _ in range(n_rec)]

    sweep_start = time.perf_counter()
    overlap1 = get_overlapped_bboxes_pairs(bbox1_list, bbox2_list)
    sweep_time = time.perf_counter() - sweep_start

    naive_start = time.perf_counter()
    overlap2 = naive_get_overlapped_bboxes_pairs(bbox1_list, bbox2_list)
    naive_time = time.perf_counter() - naive_start

    print("Sweeping algorithm took:", sweep_time, "seconds")
    print("Naive algorithm took:", naive_time, "seconds")
    assert overlap1.sort() == overlap2.sort()

import numpy as np


def get_bbox_from_object(obj):
    return (obj["x0"], obj["top"], obj["x1"], obj["bottom"])


def get_bboxlist_from_objectlist(obj_list):
    return [get_bbox_from_object(obj) for obj in obj_list]


def get_overlapping_index(overlap_list, get_first=True):
    if get_first:
        return sorted(list(set([x[0] for x in overlap_list])))
    else:
        return sorted(list(set([x[1] for x in overlap_list])))


def get_cell_size(cell):
    # width, height
    return cell[2] - cell[0], cell[3] - cell[1]


def get_cell_idxs_overlapped_with_chars(table, page):
    page_table_area = crop_page_within_table(table, page)
    cells_bbox = table.cells
    chars_bbox = get_bboxlist_from_objectlist(page_table_area.chars)
    overlap_list = get_overlapped_bboxes_pairs(cells_bbox, chars_bbox)
    cells_with_overlap = get_overlapping_index(overlap_list)
    return cells_with_overlap


def get_min_char_size(page):
    """
    return: min_width, min_height
        min_width: minimum character width of given page
        min_height: minimum character height of given page
    """
    chars = page.chars
    min_width = page.width
    min_height = page.height
    for char in chars:
        min_width = min(min_width, char["width"])
        min_height = min(min_height, char["height"])
    return min_width, min_height


def get_mode_char_size(page):
    """
    return: mode_width, mode_height
        mode_width: mode character width of given page
        mode_height: mode character height of given page
    """
    chars = page.chars
    width_list = [c["width"] for c in chars]
    height_list = [c["height"] for c in chars]
    width_unique, width_count = np.unique(width_list, return_counts=True)
    height_unique, height_count = np.unique(height_list, return_counts=True)
    mode_width = width_unique[width_count == np.amax(width_count)].min()
    mode_height = height_unique[height_count == np.amax(height_count)].min()
    return mode_width, mode_height


def get_overlapped_bboxes_pairs(bbox_list1, bbox_list2):
    """
    return: list of pair of indexes with overlap
    """
    # bbox: (x1, y1, x2, y2)
    bbox_events = []

    for i, bbox in enumerate(bbox_list1):
        bbox_events.append(("box1", bbox[0], i, 0))
        bbox_events.append(("box1", bbox[2], i, 1))
    for i, bbox in enumerate(bbox_list2):
        bbox_events.append(("box2", bbox[0], i, 0))
        bbox_events.append(("box2", bbox[2], i, 1))
    bbox_events.sort(key=lambda x: (x[1], x[3]))
    bbox1_sweeping = []
    bbox2_sweeping = []
    overlap_list = []
    # print(bbox_events)

    for event in bbox_events:
        # print("loop:", event)
        bbox_type = event[0]
        bbox_idx = event[2]
        if bbox_type == "box1":
            bbox1_x1, bbox1_y1, bbox1_x2, bbox1_y2 = bbox_list1[bbox_idx]
            if event[3] == 0:
                bbox1_sweeping.append((bbox_idx, bbox1_x1, bbox1_y1, bbox1_x2, bbox1_y2))
                for bbox2 in bbox2_sweeping:
                    bbox2_idx, bbox2_x1, bbox2_y1, bbox2_x2,  bbox2_y2 = bbox2
                    if bbox2_y1 < bbox1_y2 and bbox2_y2 > bbox1_y1 and (bbox2_x1 - bbox1_x2) * (bbox2_x2 - bbox1_x1) != 0:
                        overlap_list.append((bbox_idx, bbox2_idx))
            elif event[3] == 1:
                bbox1_sweeping.remove((bbox_idx, bbox1_x1, bbox1_y1, bbox1_x2, bbox1_y2))
        else:
            bbox2_x1, bbox2_y1, bbox2_x2, bbox2_y2 = bbox_list2[bbox_idx]
            if event[3] == 0:
                bbox2_sweeping.append((bbox_idx, bbox2_x1, bbox2_y1, bbox2_x2, bbox2_y2))
                for bbox1 in bbox1_sweeping:
                    bbox1_idx, bbox1_x1, bbox1_y1, bbox1_x2, bbox1_y2 = bbox1
                    if bbox1_y1 < bbox2_y2 and bbox1_y2 > bbox2_y1 and (bbox2_x1 - bbox1_x2) * (bbox2_x2 - bbox1_x1) != 0:
                        overlap_list.append((bbox1_idx, bbox_idx))
            elif event[3] == 1:
                bbox2_sweeping.remove((bbox_idx, bbox2_x1, bbox2_y1, bbox2_x2, bbox2_y2))
        # print(bbox1_sweeping, bbox2_sweeping)

    assert len(bbox1_sweeping) == 0

    return overlap_list


def naive_get_overlapped_bboxes_pairs(bbox_list1, bbox_list2):
    overlap_list = []
    for i, bbox1 in enumerate(bbox_list1):
        x1_b1, y1_b1, x2_b1, y2_b1 = bbox1
        for j, bbox2 in enumerate(bbox_list2):
            x1_b2, y1_b2, x2_b2, y2_b2 = bbox2
            if (x1_b1 < x2_b2 and x2_b1 > x1_b2) and (
                y1_b1 < y2_b2 and y2_b1 > y1_b2
            ):
                overlap_list.append((i, j))
    return overlap_list


def get_cell_nums(table):
    """
    return:
        n_col, n_row: The number of cells on table in a col/row direction
    """
    col = set((cell[0], cell[2]) for cell in table.cells)
    row = set((cell[1], cell[3]) for cell in table.cells)

    n_col = len(col)
    n_row = len(row)
    return n_col, n_row


def crop_page_within_table(table, page):
    bbox = table.bbox
    page_x0, page_top, _, _ = page.bbox
    bbox = (
        bbox[0] + page_x0,
        bbox[1] + page_top,
        bbox[2] + page_x0,
        bbox[3] + page_top,
    )
    return page.within_bbox(bbox)


def get_unique_list(seq):
    seen = []
    return [x for x in seq if x not in seen and not seen.append(x)]

import numpy as np

import pdfplumber


def get_bbox_from_object(obj: dict) -> "tuple[float, float, float, float]":
    """
    pdfのオブジェクトからbboxを取り出す。
    Parameters
    ----------
    obj: dict
        pdf中に存在する要素を表現するdict

    Returns
    -------
    bbox: tuple[float, float, float, float]

    Notes
    -----
    画像上での表示に用いることを前提としているため、ｙ軸については
    topとbottomの値を持ってきている。
    top / bottomは、オブジェクトのてっぺんのページの一番上からの距離を示しており、
    y0, y1はオブジェクトの底のページの一番下からの距離を示す。
    """
    return (obj["x0"], obj["top"], obj["x1"], obj["bottom"])


def get_bboxlist_from_objectlist(
    obj_list: "list[dict]",
) -> "list[tuple[float, float, float, float]]":
    """
    pdfのオブジェクトのリストからbboxのリストを返す。
    Parameters
    ----------
    obj_list: list[dict]
        page.chars, page.linesなどで得られるオブジェクトのリスト

    Returns
    -------
    bbox_list: list[tuple[float, float, float, float]]
    """
    return [get_bbox_from_object(obj) for obj in obj_list]


def get_overlapping_index(
    overlap_list: "list[tuple[int, int]]", get_first: bool = True
) -> "list[int]":
    """
    Get the width and height of the cell.

    Parameters
    ----------
    overlap_list: list[tuple[int, int]]
        2つのbboxのリストが与えられたとき、1番目のリストに存在する要素と
        2番目のリストに存在する要素について、重なっている要素のindexの組を保持したリスト。
    get_first: bool
        Trueの時、重なりを示すタプルの最初の要素について、
        indexのlistを返す。
        Falseの時はタプルの二番目の要素について返す。
    Returns
    -------
    index_list: list[int]
        どちらかのbboxのリストについて、もう一方のbboxリストとの重なりをもつ要素のindexのリスト
    """
    if get_first:
        return sorted(list(set([x[0] for x in overlap_list])))
    else:
        return sorted(list(set([x[1] for x in overlap_list])))


def get_cell_size(cell: "tuple[float, float, float, float]") -> "tuple[float, float]":
    """
    Get the height and width of the cell.

    Parameters
    ----------
    cell: tuple of list[float, float, float, float]

    Returns
    -------
    height: float
    width: float

    Notes
    -----
    cellは(x0, top, x1, bottom)のタプル
    """
    return cell[3] - cell[1],cell[2] - cell[0]


def get_cell_idxs_overlapped_with_chars(
    table: "pdfplumber.table.Table", page: "pdfplumber.page.Page"
):
    """
    テーブルに含まれるセルについて、ページ上の文字と重なっているものの
    pdfplumber.table.Table.cellsにおけるindexのリストを返す。
    """
    page_table_area = crop_page_within_table(page, table)
    cells_bbox = table.cells
    chars_bbox = get_bboxlist_from_objectlist(page_table_area.chars)
    overlap_list = get_overlapped_bboxes_pairs(cells_bbox, chars_bbox)
    cells_with_overlap = get_overlapping_index(overlap_list)
    return cells_with_overlap


def get_min_char_size(page: "pdfplumber.page.Page") -> "tuple[float, float]":
    """
    Get the minimum height / width of character in page.

    Parameters
    ----------
    page: pdfplumber.page.Page or pdfplumber.page.CroppedPage

    Returns
    -------
    min_height: float
    min_width: float
    """
    chars = page.chars
    min_height = page.height
    min_width = page.width
    for char in chars:
        min_height = min(min_height, char["height"])
        min_width = min(min_width, char["width"])
    return min_height, min_width


def get_mode_char_size(
    page: "pdfplumber.page.Page" or "pdfplumber.page.CroppedPage",
) -> "tuple[float, float]":
    """
    Get the height / width of character that appears most in page.

    Parameters
    ----------
    page: pdfplumber.page.Page or pdfplumber.page.CroppedPage

    Returns
    -------
    mode_height: float
    mode_width: float
    """
    chars = page.chars
    height_list = [c["height"] for c in chars]
    width_list = [c["width"] for c in chars]
    height_unique, height_count = np.unique(height_list, return_counts=True)
    width_unique, width_count = np.unique(width_list, return_counts=True)
    mode_height = height_unique[height_count == np.amax(height_count)].min()
    mode_width = width_unique[width_count == np.amax(width_count)].min()
    return mode_height, mode_width


def get_overlapped_bboxes_pairs(
    bbox_list1: "list[tuple[float, float, float, float]]",
    bbox_list2: "list[tuple[float, float, float, float]]",
) -> "list[tuple[int, int]]":
    """
    Get two bbox list and return pairs of indices of bbox that are overlapped between two list.

    Parameters
    ----------
    bbox_list1 : list[tuple[float, float, float, float]]
        List of bbox. Bbox is a tuple of four values
        which represents (x1, top, x2, bottom).
    bbox_list2 : list[list(int or float)]

    Returns
    -------
    overlap_list: list[tuple[int, int]]
        List of pair of indices with overlap between two list.

    Notes
    -----
    bounding boxの数が多いときには単純な実装より高速。
    bounding boxの数が少ないときにはやや遅い。
    辺を共有しているだけの場合はoverlapと判定しない。
    共有部分が面積を持つときのみにoverlapと判定。
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
                bbox1_sweeping.append(
                    (bbox_idx, bbox1_x1, bbox1_y1, bbox1_x2, bbox1_y2)
                )
                for bbox2 in bbox2_sweeping:
                    bbox2_idx, bbox2_x1, bbox2_y1, bbox2_x2, bbox2_y2 = bbox2
                    if (
                        bbox2_y1 < bbox1_y2
                        and bbox2_y2 > bbox1_y1
                        and (bbox2_x1 - bbox1_x2) * (bbox2_x2 - bbox1_x1) != 0
                    ):
                        overlap_list.append((bbox_idx, bbox2_idx))
            elif event[3] == 1:
                bbox1_sweeping.remove(
                    (bbox_idx, bbox1_x1, bbox1_y1, bbox1_x2, bbox1_y2)
                )
        else:
            bbox2_x1, bbox2_y1, bbox2_x2, bbox2_y2 = bbox_list2[bbox_idx]
            if event[3] == 0:
                bbox2_sweeping.append(
                    (bbox_idx, bbox2_x1, bbox2_y1, bbox2_x2, bbox2_y2)
                )
                for bbox1 in bbox1_sweeping:
                    bbox1_idx, bbox1_x1, bbox1_y1, bbox1_x2, bbox1_y2 = bbox1
                    if (
                        bbox1_y1 < bbox2_y2
                        and bbox1_y2 > bbox2_y1
                        and (bbox2_x1 - bbox1_x2) * (bbox2_x2 - bbox1_x1) != 0
                    ):
                        overlap_list.append((bbox1_idx, bbox_idx))
            elif event[3] == 1:
                bbox2_sweeping.remove(
                    (bbox_idx, bbox2_x1, bbox2_y1, bbox2_x2, bbox2_y2)
                )
        # print(bbox1_sweeping, bbox2_sweeping)

    assert len(bbox1_sweeping) == 0

    return overlap_list


def naive_get_overlapped_bboxes_pairs(
    bbox_list1: "list[tuple[float, float, float, float]]",
    bbox_list2: "list[tuple[float, float, float, float]]",
) -> "list[tuple[int, int]]":
    """
    Get two bbox list and return pairs of indices of bbox that are overlapped between two list.

    Parameters
    ----------
    bbox_list1 : list[tuple[float, float, float, float]]
        List of bbox. Bbox is a tuple of four values
        which represents (x1, top, x2, bottom).
    bbox_list2 : list[list(int or float)]

    Returns
    -------
    overlap_list: list[tuple[int, int]]
        List of pair of indices with overlap between two list.

    Notes
    -----
    辺を共有しているだけの場合はoverlapと判定しない。
    共有部分が面積を持つときのみにoverlapと判定。
    """
    overlap_list = []
    for i, bbox1 in enumerate(bbox_list1):
        x1_b1, y1_b1, x2_b1, y2_b1 = bbox1
        for j, bbox2 in enumerate(bbox_list2):
            x1_b2, y1_b2, x2_b2, y2_b2 = bbox2
            if (x1_b1 < x2_b2 and x2_b1 > x1_b2) and (y1_b1 < y2_b2 and y2_b1 > y1_b2):
                overlap_list.append((i, j))
    return overlap_list


def get_cell_nums(table: "pdfplumber.table.Table") -> "tuple[int, int]":
    """
    Returns how many rows or cols exist in a table.

    Parameters
    ----------
    table: pdfplumber.table.Table

    Returns
    -------
    n_row: int
    n_col: int

    Notes
    -----
    行の数、列の数は必ずしも表の見た目とは一致しない。
    実際には、行の数は、セルの矩形を表現するy座標の組の種類を、
    列の数はx座標の組の種類となっている。
    """
    row = set((cell[1], cell[3]) for cell in table.cells)
    col = set((cell[0], cell[2]) for cell in table.cells)

    n_row = len(row)
    n_col = len(col)
    return n_row, n_col


def crop_page_within_table(
    page: "pdfplumber.page.Page", table: "pdfplumber.table.Table"
) -> "pdfplumber.page.CroppedPage":
    """
    Returns cropped page in the size of table.

    Parameters
    ----------
    table: pdfplumber.table.Table
    page: pdfplumber.page.Page

    Returns
    -------
    cropped_page: pdfplumber.page.CroppedPage

    Notes
    -----
    pageを表すbboxがずれていることがあるため、補正を行っている。
    """
    bbox = table.bbox
    page_x0, page_top, _, _ = page.bbox
    bbox = (
        bbox[0] + page_x0,
        bbox[1] + page_top,
        bbox[2] + page_x0,
        bbox[3] + page_top,
    )
    return page.within_bbox(bbox)


def get_unique_list(seq: list) -> list:
    """
    Returns the list of unique elements of the original list.

    Parameters
    ----------
    seq: list

    Returns
    -------
    unique_list: list

    Notes
    -----
    リストの要素がunhashableの時、setを使う方法が使えないため追加。
    """
    seen = []
    return [x for x in seq if x not in seen and not seen.append(x)]

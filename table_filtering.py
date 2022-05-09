from operator import itemgetter

from pdfplumber import table_filtering_utils as utils


def remove_too_long_edges(page, edges, ratio=0.95):
    """
    Notes
    -----
    ページの幅 * ratio以上の長さの水平線、高さ * ratio以上の長さの垂直線を削除する
    """

    edges_adequate = list(
        filter(lambda edge: not is_too_long_edge(page, edge, ratio=0.95), edges)
    )
    return edges_adequate


def is_too_long_edge(page, edge, ratio):
    page_width = page.width
    page_height = page.height
    return edge["width"] > ratio * page_width or edge["height"] > ratio * page_height


def remove_terminal_edges(page, edges):
    """
    Notes
    -----
    ページの終端部に届いているエッジを削除する
    """
    edges_adequate = list(filter(lambda edge: not is_terminal_edge(page, edge), edges))
    return edges_adequate


def is_terminal_edge(page, edge):
    is_terminal = (
        edge["x0"] <= page.height * 0.03
        or edge["x1"] >= page.width * 0.97
        or edge["top"] <= page.height * 0.03
        or edge["bottom"] >= page.height * 0.97
    )
    return is_terminal


def remove_colorless_edges(edges):
    """
    Notes
    -----
    stroking_colorとnon_stroking_colorが同一なエッジを削除する
    """
    edges_adequate = list(
        filter(
            lambda x: itemgetter("stroking_color")(x)
            != itemgetter("non_stroking_color")(x),
            edges,
        )
    )
    return edges_adequate


def remove_too_small_cells(page, cells):
    """
    Notes
    -----
    ページの最小の文字よりも高さや幅が小さいセルを削除する
    """
    cells_adequate = list(
        filter(lambda cell: not is_too_small_cell_for_chars(page, cell), cells)
    )
    return cells_adequate


def is_too_small_cell_for_chars(page, cell):
    min_char_width, min_char_height = utils.get_min_char_size(page)
    cell_width, cell_height = utils.get_cell_size(cell)
    return cell_width < min_char_width and cell_height < min_char_height


def remove_too_short_cells(cells, ratio=10):
    """
    Notes
    -----
    セルの高さについて、ページ上の他のセルと比較して極端に低いセルを削除する。
    デフォルトでは平均の1/10より低いセルを削除。
    """
    if len(cells) == 0:
        return cells
    cell_height_list = [utils.get_cell_size(cell)[1] for cell in cells]
    mean_height = sum(cell_height_list) / len(cell_height_list)
    cells_adequate = list(
        filter(lambda cell: not is_too_short_cell(cell, mean_height, ratio), cells)
    )
    return cells_adequate


def is_too_short_cell(cell, mean_height, ratio=10):
    cell_height = utils.get_cell_size(cell)[1]
    return cell_height * ratio < mean_height


# def remove_tables_without_chars(tables, chars):
#     """
#     tableと判定された領域のうち、文字を一切含まないものをtableから除外する
#     """
#     ret_tables = []
#     tables_bbox = [table.bbox for table in tables]
#     chars_bbox = [(c["x0"], c["top"], c["x1"], c["bottom"]) for c in chars]
#     overlaps = utils.get_overlapped_bboxes_pairs(tables_bbox, chars_bbox)
#     idx_tables_with_overlap = set([p[0] for p in overlaps])
#     for i, table in enumerate(tables):
#         if i in idx_tables_with_overlap:
#             ret_tables.append(table)

#     return ret_tables


def remove_tables_without_chars(tables, chars):
    """
    tableと判定された領域のうち、文字を一切含まないものをtableから除外する
    """
    tables_adequate = list(
        filter(lambda table: is_table_overlapped_with_char(table, chars), tables)
    )

    return tables_adequate


def is_table_overlapped_with_char(table, chars):
    table_bbox = [table.bbox]
    chars_bbox = utils.get_bboxlist_from_objectlist(chars)
    overlap_pair_with_chars = utils.get_overlapped_bboxes_pairs(table_bbox, chars_bbox)
    return len(overlap_pair_with_chars) > 0


def remove_misdetected_tables_with_two_cells(page, tables):
    """
    文字入りの矩形領域+文字のない近接する矩形によって表と判定されてしまうことを防ぐ
    """
    tables_adequate = list(
        filter(
            lambda table: not is_misdetected_table_with_two_cells(page, table), tables
        )
    )
    return tables_adequate


def is_misdetected_table_with_two_cells(page, table):
    cells_with_overlap = utils.get_cell_idxs_overlapped_with_chars(table, page)
    return len(table.cells) == 2 and len(cells_with_overlap) == 1


def remove_tables_with_one_cell(tables):
    """
    セルが1つのものは除外する
    """
    tables_adequate = list(
        filter(lambda table: not is_table_with_one_cell(table), tables)
    )
    return tables_adequate


def is_table_with_one_cell(table):
    return len(table.cells) == 1


def remove_table_with_unusual_shape(tables):
    """
    構成するセルの高さor幅がすべて異なるtableを除外する
    """
    tables_adequate = list(
        filter(lambda table: not is_table_with_unusual_shape(table), tables)
    )
    return tables_adequate


def is_table_with_unusual_shape(table):
    cell_sizes = [utils.get_cell_size(cell) for cell in table.cells]
    cell_widths = set([size[0] for size in cell_sizes])
    cell_heights = set([size[1] for size in cell_sizes])
    return len(cell_widths) == len(table.cells) and len(cell_heights) == len(
        table.cells
    )


def remove_tables_with_single_line(tables):
    """
    一行/一列しか存在しない表のうち、一行/一列の文字しか含まないと推定されるものを除外する。
    タイトルの一文字一文字が矩形で囲まれ、表と五検知されるケースへの対処。
    """
    tables_adequate = list(
        filter(lambda table: not is_table_with_single_line(table), tables)
    )
    return tables_adequate


def is_table_with_single_line(table):
    n_col, n_row = utils.get_cell_nums(table)
    if n_col == 1:
        cell_width, _ = utils.get_cell_size(table.cells[0])
        if cell_width < table.page.width * 0.03:
            return True
    if n_row == 1:
        _, cell_height = utils.get_cell_size(table.cells[0])
        if cell_height < table.page.height * 0.02:
            return True
    return False


def remove_tables_with_many_small_cells(page, tables):
    """
    table領域の最もよく現れる文字サイズより小さいセルを多数含むtableを除外する
    """
    tables_adequate = list(
        filter(lambda table: not is_table_with_many_small_cells(page, table), tables)
    )
    return tables_adequate


def is_table_with_many_small_cells(page, table):
    page_table_area = utils.crop_page_within_table(page, table)
    mode_char_w, mode_char_h = utils.get_mode_char_size(page_table_area)
    n_cell = len(table.cells)
    n_small_cell = 0
    for cell in table.cells:
        cell_w, cell_h = utils.get_cell_size(cell)
        if cell_w < mode_char_w or cell_h < mode_char_h:
            n_small_cell += 1
    if n_small_cell * 2 > n_cell - n_small_cell:
        return True
    else:
        return False


def remove_charts(page, tables, ratio=5):
    """
    文字を含まないセルを多数含むものを除外する
    """
    tables_adequate = list(
        filter(lambda table: not seems_to_be_chart(page, table), tables)
    )
    return tables_adequate


def seems_to_be_chart(page, table, ratio=5):
    cells_bbox = table.cells
    cells_with_overlap = utils.get_cell_idxs_overlapped_with_chars(table, page)
    return len(cells_with_overlap) < len(cells_bbox) / ratio


def remove_titles(page, tables):
    """
    すべてのセルに1文字ずつしか含まれていないケースを除外する。
    """

    tables_adequate = list(
        filter(lambda table: not seems_to_be_title(page, table), tables)
    )
    return tables_adequate


def seems_to_be_title(page, table):
    def get_meaningful_chars(chars):
        MEANINGLESS_CHARS = [" "]
        return list(filter(lambda x: x["text"] not in MEANINGLESS_CHARS, chars))

    cells_with_overlap = utils.get_cell_idxs_overlapped_with_chars(table, page)
    page_table_area = utils.crop_page_within_table(page, table)
    cropped_chars = page_table_area.chars
    meaningful_chars = get_meaningful_chars(cropped_chars)
    return len(cells_with_overlap) >= len(meaningful_chars)


def remove_bar_graph(page, tables):
    """
    ある領域が含む矩形について、セルの数と比較して矩形の色が多い場合はtableから除外する
    """
    tables_adequate = list(filter(lambda table: not is_bar_graph(page, table), tables))
    return tables_adequate


def is_bar_graph(page, table):
    n_col, n_row = utils.get_cell_nums(table)
    if (n_col == 1 or n_row == 1) and n_col + n_row > 4:
        n_cells = n_col + n_row - 1
        cropped_page = page.crop(table.bbox)
        color_list = [x["non_stroking_color"] for x in cropped_page.rects]
        unique_color_list = utils.get_unique_list(color_list)
        return len(unique_color_list) >= n_cells + 1
    return False


def remove_complicated_rects(tables):
    """
    セルが整列していない表は除外する
    """
    tables_adequate = list(
        filter(lambda table: not is_complicated_rects(table), tables)
    )
    return tables_adequate


def is_complicated_rects(table):
    n_col, n_row = utils.get_cell_nums(table)
    overlap_bbox = utils.get_overlapped_bboxes_pairs(table.cells, table.cells)
    if len(overlap_bbox) > len(table.cells):
        return True
    if n_col * n_row > 2 * len(table.cells):
        return True
    return False
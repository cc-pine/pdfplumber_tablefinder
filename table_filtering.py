from operator import itemgetter

from pdfplumber import utils


def remove_too_long_edges(page, edges, ratio=0.95):
    page_width = page.width
    page_height = page.height

    edges_adequate = []
    for edge in edges:
        if edge["width"] < ratio * page_width and edge["height"] < ratio * page_height:
            edges_adequate.append(edge)

    return edges_adequate


def remove_terminal_edges(page, edges):
    edges_ret = []
    for edge in edges:
        if (
            edge["x0"] <= page.height * 0.03
            or edge["x1"] >= page.width * 0.97
            or edge["top"] <= page.height * 0.03
            or edge["bottom"] >= page.height * 0.97
        ):
            continue
        edges_ret.append(edge)
    return edges_ret


def remove_colorless_edges(edges):
    edges_ret = list(
        filter(
            lambda x: itemgetter("stroking_color")(x)
            != itemgetter("non_stroking_color")(x),
            edges,
        )
    )
    return edges_ret


def remove_too_small_cells(page, cells):
    min_char_width, min_char_height = utils.get_min_char_size(page)
    cells_adequate = []
    for cell in cells:
        cell_width, cell_height = utils.get_cell_size(cell)
        if cell_width > min_char_width and cell_height > min_char_height:
            cells_adequate.append(cell)
    return cells_adequate


def remove_too_short_cells(cells, ratio=10):
    if len(cells) == 0:
        return cells
    cell_height_list = [utils.get_cell_size(cell)[1] for cell in cells]
    mean_height = sum(cell_height_list) / len(cell_height_list)
    ret_cells = []
    for i, cell in enumerate(cells):
        if cell_height_list[i] * ratio > mean_height:
            ret_cells.append(cell)
    return ret_cells


def remove_table_without_chars(tables, chars):
    ret_tables = []
    tables_bbox = [table.bbox for table in tables]
    chars_bbox = [(c["x0"], c["top"], c["x1"], c["bottom"]) for c in chars]
    overlaps = utils.get_overlapped_bboxes_pairs(tables_bbox, chars_bbox)
    idx_tables_with_overlap = set([p[0] for p in overlaps])
    for i, table in enumerate(tables):
        if i in idx_tables_with_overlap:
            ret_tables.append(table)

    return ret_tables


def remove_misdetected_table_with_two_cells(page, tables):
    ret_tables = []
    for table in tables:
        if len(table.cells) == 2:
            cells_with_overlap = utils.get_cell_idxs_overlapped_with_chars(table, page)
            if len(cells_with_overlap) == 1:
                continue
        ret_tables.append(table)
    return ret_tables


def remove_table_with_lt_two_cells(tables):
    ret_tables = []
    for table in tables:
        if len(table.cells) > 2:
            ret_tables.append(table)
    return ret_tables


def remove_table_with_unusual_shape(tables):
    ret_tables = []
    for table in tables:
        cell_widths = set()
        cell_heights = set()
        for cell in table.cells:
            cell_width, cell_height = utils.get_cell_size(cell)
            cell_widths.add(cell_width)
            cell_heights.add(cell_height)
            # 形が全部違う
        if len(cell_widths) == len(table.cells) and len(cell_heights) == len(
            table.cells
        ):
            continue
        ret_tables.append(table)
    return ret_tables


def remove_table_with_single_col_row(tables):
    ret_tables = []
    for table in tables:
        n_col, n_row = utils.get_cell_nums(table)
        if n_col == 1:
            cell_width, _ = utils.get_cell_size(table.cells[0])
            if cell_width < table.page.width * 0.03:
                continue
        if n_row == 1:
            _, cell_height = utils.get_cell_size(table.cells[0])
            if cell_height < table.page.height * 0.02:
                continue
        ret_tables.append(table)
    return ret_tables


def remove_tables_with_many_too_small_cells(page, tables):
    ret_tables = []
    for table in tables:
        page_table_area = utils.crop_page_within_table(table, page)
        mode_char_w, mode_char_h = utils.get_mode_char_size(page_table_area)
        n_cell = len(table.cells)
        n_small_cell = 0
        for cell in table.cells:
            # print(cell)
            cell_w, cell_h = utils.get_cell_size(cell)
            if cell_w < mode_char_w or cell_h < mode_char_h:
                n_small_cell += 1
        if n_small_cell * 2 >= n_cell - n_small_cell:
            continue
        else:
            ret_tables.append(table)
    return ret_tables


def remove_charts(page, tables, ratio=5):
    # セルに文字が含まれていないものを削除する
    ret_tables = []
    for table in tables:
        cells_bbox = table.cells
        cells_with_overlap = utils.get_cell_idxs_overlapped_with_chars(table, page)
        if len(cells_with_overlap) < len(cells_bbox) / ratio:
            continue
        ret_tables.append(table)
    return ret_tables


def remove_titles(page, tables):
    def get_meaningful_chars(chars):
        MEANINGLESS_CHARS = [" "]
        return list(filter(lambda x: x["text"] not in MEANINGLESS_CHARS, chars))

    ret_tables = []
    for table in tables:
        cells_with_overlap = utils.get_cell_idxs_overlapped_with_chars(table, page)
        page_table_area = utils.crop_page_within_table(table, page)
        cropped_chars = page_table_area.chars
        meaningful_chars = get_meaningful_chars(cropped_chars)
        if len(cells_with_overlap) >= len(meaningful_chars):
            continue
        ret_tables.append(table)
    return ret_tables


def remove_bar_graph(page, tables):
    ret_tables = []
    for table in tables:
        n_col, n_row = utils.get_cell_nums(table)
        if (n_col == 1 or n_row == 1) and n_col + n_row > 4:
            n_cells = n_col + n_row - 1
            cropped_page = page.crop(table.bbox)
            color_list = [x["non_stroking_color"] for x in cropped_page.rects]
            unique_color_list = utils.get_unique_list(color_list)
            if len(unique_color_list) >= n_cells + 1:
                continue
        ret_tables.append(table)
    return ret_tables

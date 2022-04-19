import itertools
from operator import itemgetter

from . import utils

DEFAULT_SNAP_TOLERANCE = 3
DEFAULT_JOIN_TOLERANCE = 3
DEFAULT_MIN_WORDS_VERTICAL = 3
DEFAULT_MIN_WORDS_HORIZONTAL = 1


def snap_edges(
    edges, x_tolerance=DEFAULT_SNAP_TOLERANCE, y_tolerance=DEFAULT_SNAP_TOLERANCE
):
    """
    Given a list of edges, snap any within `tolerance` pixels of one another
    to their positional average.
    """
    by_orientation = {"v": [], "h": []}
    for e in edges:
        by_orientation[e["orientation"]].append(e)

    snapped_v = utils.snap_objects(by_orientation["v"], "x0", x_tolerance)
    snapped_h = utils.snap_objects(by_orientation["h"], "top", y_tolerance)
    return snapped_v + snapped_h


def join_edge_group(edges, orientation, tolerance=DEFAULT_JOIN_TOLERANCE):
    """
    Given a list of edges along the same infinite line, join those that
    are within `tolerance` pixels of one another.
    """
    if orientation == "h":
        min_prop, max_prop = "x0", "x1"
    elif orientation == "v":
        min_prop, max_prop = "top", "bottom"
    else:
        raise ValueError("Orientation must be 'v' or 'h'")

    sorted_edges = list(sorted(edges, key=itemgetter(min_prop)))
    joined = [sorted_edges[0]]
    for e in sorted_edges[1:]:
        last = joined[-1]
        if e[min_prop] <= (last[max_prop] + tolerance):
            if e[max_prop] > last[max_prop]:
                # Extend current edge to new extremity
                joined[-1] = utils.resize_object(last, max_prop, e[max_prop])
        else:
            # Edge is separate from previous edges
            joined.append(e)

    return joined


def merge_edges(
    edges, snap_x_tolerance, snap_y_tolerance, join_x_tolerance, join_y_tolerance
):
    """
    Using the `snap_edges` and `join_edge_group` methods above,
    merge a list of edges into a more "seamless" list.
    """

    def get_group(edge):
        if edge["orientation"] == "h":
            return ("h", edge["top"])
        else:
            return ("v", edge["x0"])

    if snap_x_tolerance > 0 or snap_y_tolerance > 0:
        edges = snap_edges(edges, snap_x_tolerance, snap_y_tolerance)

    _sorted = sorted(edges, key=get_group)
    edge_groups = itertools.groupby(_sorted, key=get_group)
    edge_gen = (
        join_edge_group(
            items, k[0], (join_x_tolerance if k[0] == "h" else join_y_tolerance)
        )
        for k, items in edge_groups
    )
    edges = list(itertools.chain(*edge_gen))
    return edges


def words_to_edges_h(words, word_threshold=DEFAULT_MIN_WORDS_HORIZONTAL):
    """
    Find (imaginary) horizontal lines that connect the tops
    of at least `word_threshold` words.
    """
    by_top = utils.cluster_objects(words, "top", 1)
    large_clusters = filter(lambda x: len(x) >= word_threshold, by_top)
    rects = list(map(utils.objects_to_rect, large_clusters))
    if len(rects) == 0:
        return []
    min_x0 = min(map(itemgetter("x0"), rects))
    max_x1 = max(map(itemgetter("x1"), rects))

    edges = []
    for r in rects:
        edges += [
            # Top of text
            {
                "x0": min_x0,
                "x1": max_x1,
                "top": r["top"],
                "bottom": r["top"],
                "width": max_x1 - min_x0,
                "orientation": "h",
            },
            # For each detected row, we also add the 'bottom' line.  This will
            # generate extra edges, (some will be redundant with the next row
            # 'top' line), but this catches the last row of every table.
            {
                "x0": min_x0,
                "x1": max_x1,
                "top": r["bottom"],
                "bottom": r["bottom"],
                "width": max_x1 - min_x0,
                "orientation": "h",
            },
        ]

    return edges


def words_to_edges_v(words, word_threshold=DEFAULT_MIN_WORDS_VERTICAL):
    """
    Find (imaginary) vertical lines that connect the left, right, or
    center of at least `word_threshold` words.
    """
    # Find words that share the same left, right, or centerpoints
    by_x0 = utils.cluster_objects(words, "x0", 1)
    by_x1 = utils.cluster_objects(words, "x1", 1)
    by_center = utils.cluster_objects(words, lambda x: (x["x0"] + x["x1"]) / 2, 1)
    clusters = by_x0 + by_x1 + by_center

    # Find the points that align with the most words
    sorted_clusters = sorted(clusters, key=lambda x: -len(x))
    large_clusters = filter(lambda x: len(x) >= word_threshold, sorted_clusters)

    # For each of those points, find the bboxes fitting all matching words
    bboxes = list(map(utils.objects_to_bbox, large_clusters))

    # Iterate through those bboxes, condensing overlapping bboxes
    condensed_bboxes = []
    for bbox in bboxes:
        overlap = False
        for c in condensed_bboxes:
            if utils.get_bbox_overlap(bbox, c):
                overlap = True
                break
        if not overlap:
            condensed_bboxes.append(bbox)

    if len(condensed_bboxes) == 0:
        return []

    condensed_rects = map(utils.bbox_to_rect, condensed_bboxes)
    sorted_rects = list(sorted(condensed_rects, key=itemgetter("x0")))

    max_x1 = max(map(itemgetter("x1"), sorted_rects))
    min_top = min(map(itemgetter("top"), sorted_rects))
    max_bottom = max(map(itemgetter("bottom"), sorted_rects))

    # Describe all the left-hand edges of each text cluster
    edges = [
        {
            "x0": b["x0"],
            "x1": b["x0"],
            "top": min_top,
            "bottom": max_bottom,
            "height": max_bottom - min_top,
            "orientation": "v",
        }
        for b in sorted_rects
    ] + [
        {
            "x0": max_x1,
            "x1": max_x1,
            "top": min_top,
            "bottom": max_bottom,
            "height": max_bottom - min_top,
            "orientation": "v",
        }
    ]

    return edges


def edges_to_intersections(edges, x_tolerance=1, y_tolerance=1):
    """
    Given a list of edges, return the points at which they intersect
    within `tolerance` pixels.
    """
    intersections = {}
    v_edges, h_edges = [
        list(filter(lambda x: x["orientation"] == o, edges)) for o in ("v", "h")
    ]
    for v in sorted(v_edges, key=itemgetter("x0", "top")):
        for h in sorted(h_edges, key=itemgetter("top", "x0")):
            if (
                (v["top"] <= (h["top"] + y_tolerance))
                and (v["bottom"] >= (h["top"] - y_tolerance))
                and (v["x0"] >= (h["x0"] - x_tolerance))
                and (v["x0"] <= (h["x1"] + x_tolerance))
            ):
                vertex = (v["x0"], h["top"])
                if vertex not in intersections:
                    intersections[vertex] = {"v": [], "h": []}
                intersections[vertex]["v"].append(v)
                intersections[vertex]["h"].append(h)
    return intersections


def intersections_to_cells(intersections):
    """
    Given a list of points (`intersections`), return all rectangular "cells"
    that those points describe.

    `intersections` should be a dictionary with (x0, top) tuples as keys,
    and a list of edge objects as values. The edge objects should correspond
    to the edges that touch the intersection.
    """

    def edge_connects(p1, p2):
        def edges_to_set(edges):
            return set(map(utils.obj_to_bbox, edges))

        if p1[0] == p2[0]:
            common = edges_to_set(intersections[p1]["v"]).intersection(
                edges_to_set(intersections[p2]["v"])
            )
            if len(common):
                return True

        if p1[1] == p2[1]:
            common = edges_to_set(intersections[p1]["h"]).intersection(
                edges_to_set(intersections[p2]["h"])
            )
            if len(common):
                return True
        return False

    points = list(sorted(intersections.keys()))
    n_points = len(points)

    def find_smallest_cell(points, i):
        if i == n_points - 1:
            return None
        pt = points[i]
        rest = points[i + 1 :]
        # Get all the points directly below and directly right
        below = [x for x in rest if x[0] == pt[0]]
        right = [x for x in rest if x[1] == pt[1]]
        for below_pt in below:
            if not edge_connects(pt, below_pt):
                continue

            for right_pt in right:
                if not edge_connects(pt, right_pt):
                    continue

                bottom_right = (right_pt[0], below_pt[1])

                if (
                    (bottom_right in intersections)
                    and edge_connects(bottom_right, right_pt)
                    and edge_connects(bottom_right, below_pt)
                ):

                    return (pt[0], pt[1], bottom_right[0], bottom_right[1])

    cell_gen = (find_smallest_cell(points, i) for i in range(len(points)))
    return list(filter(None, cell_gen))


def cells_to_tables(cells):
    """
    Given a list of bounding boxes (`cells`), return a list of tables that
    hold those cells most simply (and contiguously).
    """

    def bbox_to_corners(bbox):
        x0, top, x1, bottom = bbox
        return list(itertools.product((x0, x1), (top, bottom)))

    cells = [
        {"available": True, "bbox": bbox, "corners": bbox_to_corners(bbox)}
        for bbox in cells
    ]

    # Iterate through the cells found above, and assign them
    # to contiguous tables

    def init_new_table():
        return {"corners": set([]), "cells": []}

    def assign_cell(cell, table):
        table["corners"] = table["corners"].union(set(cell["corners"]))
        table["cells"].append(cell["bbox"])
        cell["available"] = False

    n_cells = len(cells)
    n_assigned = 0
    tables = []
    current_table = init_new_table()
    while True:
        initial_cell_count = len(current_table["cells"])
        for i, cell in enumerate(filter(itemgetter("available"), cells)):
            if len(current_table["cells"]) == 0:
                assign_cell(cell, current_table)
                n_assigned += 1
            else:
                corner_count = sum(
                    c in current_table["corners"] for c in cell["corners"]
                )
                if corner_count > 0 and cell["available"]:
                    assign_cell(cell, current_table)
                    n_assigned += 1
        if n_assigned == n_cells:
            break
        if len(current_table["cells"]) == initial_cell_count:
            tables.append(current_table)
            current_table = init_new_table()

    if len(current_table["cells"]):
        tables.append(current_table)

    # Sort the tables top-to-bottom-left-to-right based on the value of the
    # topmost-and-then-leftmost coordinate of a table. The topmost-and-then-leftmost
    # coordinate is found by reversing the coordinates of the corners to (Y, X) from
    # (X, Y) and then finding the smallest.
    _sorted = sorted(tables, key=lambda t: min(corner[::-1] for corner in t["corners"]))
    filtered = [t["cells"] for t in _sorted if len(t["cells"]) > 1]
    return filtered


class CellGroup(object):
    def __init__(self, cells):
        self.cells = cells
        self.bbox = (
            min(map(itemgetter(0), filter(None, cells))),
            min(map(itemgetter(1), filter(None, cells))),
            max(map(itemgetter(2), filter(None, cells))),
            max(map(itemgetter(3), filter(None, cells))),
        )


class Row(CellGroup):
    pass


class Table(object):
    def __init__(self, page, cells):
        self.page = page
        self.cells = cells
        self.bbox = (
            min(map(itemgetter(0), cells)),
            min(map(itemgetter(1), cells)),
            max(map(itemgetter(2), cells)),
            max(map(itemgetter(3), cells)),
        )

    @property
    def rows(self):
        _sorted = sorted(self.cells, key=itemgetter(1, 0))
        xs = list(sorted(set(map(itemgetter(0), self.cells))))
        rows = []
        for y, row_cells in itertools.groupby(_sorted, itemgetter(1)):
            xdict = dict((cell[0], cell) for cell in row_cells)
            row = Row([xdict.get(x) for x in xs])
            rows.append(row)
        return rows

    def extract(
        self,
        x_tolerance=utils.DEFAULT_X_TOLERANCE,
        y_tolerance=utils.DEFAULT_Y_TOLERANCE,
    ):

        chars = self.page.chars
        table_arr = []

        def char_in_bbox(char, bbox):
            v_mid = (char["top"] + char["bottom"]) / 2
            h_mid = (char["x0"] + char["x1"]) / 2
            x0, top, x1, bottom = bbox
            return (
                (h_mid >= x0) and (h_mid < x1) and (v_mid >= top) and (v_mid < bottom)
            )

        for row in self.rows:
            arr = []
            row_chars = [char for char in chars if char_in_bbox(char, row.bbox)]

            for cell in row.cells:
                if cell is None:
                    cell_text = None
                else:
                    cell_chars = [
                        char for char in row_chars if char_in_bbox(char, cell)
                    ]

                    if len(cell_chars):
                        cell_text = utils.extract_text(
                            cell_chars,
                            x_tolerance=x_tolerance,
                            y_tolerance=y_tolerance,
                        ).strip()
                    else:
                        cell_text = ""
                arr.append(cell_text)
            table_arr.append(arr)

        return table_arr


TABLE_STRATEGIES = ["lines", "lines_strict", "text", "explicit"]
DEFAULT_TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "explicit_vertical_lines": [],
    "explicit_horizontal_lines": [],
    "snap_tolerance": DEFAULT_SNAP_TOLERANCE,
    "snap_x_tolerance": None,
    "snap_y_tolerance": None,
    "join_tolerance": DEFAULT_JOIN_TOLERANCE,
    "join_x_tolerance": None,
    "join_y_tolerance": None,
    "edge_min_length": 3,
    "min_words_vertical": DEFAULT_MIN_WORDS_VERTICAL,
    "min_words_horizontal": DEFAULT_MIN_WORDS_HORIZONTAL,
    "keep_blank_chars": False,
    "text_tolerance": 3,
    "text_x_tolerance": None,
    "text_y_tolerance": None,
    "intersection_tolerance": 3,
    "intersection_x_tolerance": None,
    "intersection_y_tolerance": None,
}

NON_NEGATIVE_SETTINGS = [
    "snap_tolerance",
    "snap_x_tolerance",
    "snap_y_tolerance",
    "join_tolerance",
    "join_x_tolerance",
    "join_y_tolerance",
    "edge_min_length",
    "min_words_vertical",
    "min_words_horizontal",
    "text_tolerance",
    "text_x_tolerance",
    "text_y_tolerance",
    "intersection_tolerance",
    "intersection_x_tolerance",
    "intersection_y_tolerance",
]


class TableFinder(object):
    """
    Given a PDF page, find plausible table structures.

    Largely borrowed from Anssi Nurminen's master's thesis:
    http://dspace.cc.tut.fi/dpub/bitstream/handle/123456789/21520/Nurminen.pdf?sequence=3

    ... and inspired by Tabula:
    https://github.com/tabulapdf/tabula-extractor/issues/16
    """

    def __init__(self, page, settings={}):
        self.page = page
        self.settings = self.resolve_table_settings(settings)
        self.edges = self.get_edges()
        self.intersections = edges_to_intersections(
            self.edges,
            self.settings["intersection_x_tolerance"],
            self.settings["intersection_y_tolerance"],
        )
        self.cells = intersections_to_cells(self.intersections)
        self.tables = [Table(self.page, t) for t in cells_to_tables(self.cells)]

    @staticmethod
    def resolve_table_settings(table_settings={}):
        """Clean up user-provided table settings.

        Validates that the table settings provided consists of acceptable keys and
        returns a cleaned up version. The cleaned up version fills out the missing
        values with the default values in the provided settings.

        TODO: Can be further used to validate that the values are of the correct
            type. For example, raising a value error when a non-boolean input is
            provided for the key ``keep_blank_chars``.

        :param table_settings: User-provided table settings.
        :returns: A cleaned up version of the user-provided table settings.
        :raises ValueError: When an unrecognised key is provided.
        """
        for k in table_settings.keys():
            if k not in DEFAULT_TABLE_SETTINGS:
                raise ValueError(f"Unrecognized table setting: '{k}'")

        for setting in NON_NEGATIVE_SETTINGS:
            if (table_settings.get(setting) or 0) < 0:
                raise ValueError(f"Table setting '{setting}' cannot be negative")

        resolved_table_settings = dict(DEFAULT_TABLE_SETTINGS)
        resolved_table_settings.update(table_settings)

        for var, fallback in [
            ("text_x_tolerance", "text_tolerance"),
            ("text_y_tolerance", "text_tolerance"),
            ("snap_x_tolerance", "snap_tolerance"),
            ("snap_y_tolerance", "snap_tolerance"),
            ("join_x_tolerance", "join_tolerance"),
            ("join_y_tolerance", "join_tolerance"),
            ("intersection_x_tolerance", "intersection_tolerance"),
            ("intersection_y_tolerance", "intersection_tolerance"),
        ]:
            if resolved_table_settings[var] is None:
                resolved_table_settings.update({var: resolved_table_settings[fallback]})

        return resolved_table_settings

    def get_edges(self):
        settings = self.settings
        for name in ["vertical", "horizontal"]:
            strategy = settings[name + "_strategy"]
            if strategy not in TABLE_STRATEGIES:
                raise ValueError(
                    f'{name}_strategy must be one of {{{",".join(TABLE_STRATEGIES)}}}'
                )
            if strategy == "explicit":
                if len(settings["explicit_" + name + "_lines"]) < 2:
                    raise ValueError(
                        f"If {strategy}_strategy == 'explicit', explicit_{name}_lines "
                        f"must be specified as a list/tuple of two or more "
                        f"floats/ints."
                    )

        v_strat = settings["vertical_strategy"]
        h_strat = settings["horizontal_strategy"]

        if v_strat == "text" or h_strat == "text":
            words = self.page.extract_words(
                x_tolerance=settings["text_x_tolerance"],
                y_tolerance=settings["text_y_tolerance"],
                keep_blank_chars=settings["keep_blank_chars"],
            )

        v_explicit = []
        for desc in settings["explicit_vertical_lines"]:
            if isinstance(desc, dict):
                for e in utils.obj_to_edges(desc):
                    if e["orientation"] == "v":
                        v_explicit.append(e)
            else:
                v_explicit.append(
                    {
                        "x0": desc,
                        "x1": desc,
                        "top": self.page.bbox[1],
                        "bottom": self.page.bbox[3],
                        "height": self.page.bbox[3] - self.page.bbox[1],
                        "orientation": "v",
                    }
                )

        if v_strat == "lines":
            v_base = utils.filter_edges(self.page.edges, "v")
        elif v_strat == "lines_strict":
            v_base = utils.filter_edges(self.page.edges, "v", edge_type="line")
        elif v_strat == "text":
            v_base = words_to_edges_v(
                words, word_threshold=settings["min_words_vertical"]
            )
        elif v_strat == "explicit":
            v_base = []

        v = v_base + v_explicit

        h_explicit = []
        for desc in settings["explicit_horizontal_lines"]:
            if isinstance(desc, dict):
                for e in utils.obj_to_edges(desc):
                    if e["orientation"] == "h":
                        h_explicit.append(e)
            else:
                h_explicit.append(
                    {
                        "x0": self.page.bbox[0],
                        "x1": self.page.bbox[2],
                        "width": self.page.bbox[2] - self.page.bbox[0],
                        "top": desc,
                        "bottom": desc,
                        "orientation": "h",
                    }
                )

        if h_strat == "lines":
            h_base = utils.filter_edges(self.page.edges, "h")
        elif h_strat == "lines_strict":
            h_base = utils.filter_edges(self.page.edges, "h", edge_type="line")
        elif h_strat == "text":
            h_base = words_to_edges_h(
                words, word_threshold=settings["min_words_horizontal"]
            )
        elif h_strat == "explicit":
            h_base = []

        h = h_base + h_explicit

        edges = list(v) + list(h)

        edges = merge_edges(
            edges,
            snap_x_tolerance=settings["snap_x_tolerance"],
            snap_y_tolerance=settings["snap_y_tolerance"],
            join_x_tolerance=settings["join_x_tolerance"],
            join_y_tolerance=settings["join_y_tolerance"],
        )

        return utils.filter_edges(edges, min_length=settings["edge_min_length"])


class TableFinder2(object):
    """
    Given a PDF page, find plausible table structures.

    Largely borrowed from Anssi Nurminen's master's thesis:
    http://dspace.cc.tut.fi/dpub/bitstream/handle/123456789/21520/Nurminen.pdf?sequence=3

    ... and inspired by Tabula:
    https://github.com/tabulapdf/tabula-extractor/issues/16
    """

    def __init__(self, page, settings={"snap_tolerance":1e-2}):
        self.page = page
        self.settings = self.resolve_table_settings(settings)
        self.edges = self.get_edges()
        self.edges = self.remove_too_long_edges(self.page, self.edges)  # v1
        self.edges = self.remove_terminal_edges(self.page, self.edges)
        self.intersections = edges_to_intersections(
            self.edges,
            self.settings["intersection_x_tolerance"],
            self.settings["intersection_y_tolerance"],
        )
        self.cells = intersections_to_cells(self.intersections)
        self.cells_dev = self.remove_too_small_cells(self.cells)  # v2
        self.tables = [Table(self.page, t) for t in cells_to_tables(self.cells_dev)]
        if len(self.tables) > 0:
            self.tables = self.remove_table_without_chars(
                self.tables, self.page.extract_words()  # chars -> extract_words v6_2
            )  # v4
            # self.tables = self.remove_table_with_lt_two_cells(self.tables)  # v5 v8で削除
            self.tables = self.remove_table_with_unusual_shape(self.tables)  # v6
            self.tables = self.remove_table_with_single_col_row(self.tables)  # v6

    @staticmethod
    def resolve_table_settings(table_settings={}):
        """Clean up user-provided table settings.

        Validates that the table settings provided consists of acceptable keys and
        returns a cleaned up version. The cleaned up version fills out the missing
        values with the default values in the provided settings.

        TODO: Can be further used to validate that the values are of the correct
            type. For example, raising a value error when a non-boolean input is
            provided for the key ``keep_blank_chars``.

        :param table_settings: User-provided table settings.
        :returns: A cleaned up version of the user-provided table settings.
        :raises ValueError: When an unrecognised key is provided.
        """
        for k in table_settings.keys():
            if k not in DEFAULT_TABLE_SETTINGS:
                raise ValueError(f"Unrecognized table setting: '{k}'")

        for setting in NON_NEGATIVE_SETTINGS:
            if (table_settings.get(setting) or 0) < 0:
                raise ValueError(f"Table setting '{setting}' cannot be negative")

        resolved_table_settings = dict(DEFAULT_TABLE_SETTINGS)
        resolved_table_settings.update(table_settings)

        for var, fallback in [
            ("text_x_tolerance", "text_tolerance"),
            ("text_y_tolerance", "text_tolerance"),
            ("snap_x_tolerance", "snap_tolerance"),
            ("snap_y_tolerance", "snap_tolerance"),
            ("join_x_tolerance", "join_tolerance"),
            ("join_y_tolerance", "join_tolerance"),
            ("intersection_x_tolerance", "intersection_tolerance"),
            ("intersection_y_tolerance", "intersection_tolerance"),
        ]:
            if resolved_table_settings[var] is None:
                resolved_table_settings.update({var: resolved_table_settings[fallback]})

        return resolved_table_settings

    def get_edges(self):
        settings = self.settings
        for name in ["vertical", "horizontal"]:
            strategy = settings[name + "_strategy"]
            if strategy not in TABLE_STRATEGIES:
                raise ValueError(
                    f'{name}_strategy must be one of {{{",".join(TABLE_STRATEGIES)}}}'
                )
            if strategy == "explicit":
                if len(settings["explicit_" + name + "_lines"]) < 2:
                    raise ValueError(
                        f"If {strategy}_strategy == 'explicit', explicit_{name}_lines "
                        f"must be specified as a list/tuple of two or more "
                        f"floats/ints."
                    )

        v_strat = settings["vertical_strategy"]
        h_strat = settings["horizontal_strategy"]

        if v_strat == "text" or h_strat == "text":
            words = self.page.extract_words(
                x_tolerance=settings["text_x_tolerance"],
                y_tolerance=settings["text_y_tolerance"],
                keep_blank_chars=settings["keep_blank_chars"],
            )

        v_explicit = []
        for desc in settings["explicit_vertical_lines"]:
            if isinstance(desc, dict):
                for e in utils.obj_to_edges(desc):
                    if e["orientation"] == "v":
                        v_explicit.append(e)
            else:
                v_explicit.append(
                    {
                        "x0": desc,
                        "x1": desc,
                        "top": self.page.bbox[1],
                        "bottom": self.page.bbox[3],
                        "height": self.page.bbox[3] - self.page.bbox[1],
                        "orientation": "v",
                    }
                )

        if v_strat == "lines":
            v_base = utils.filter_edges(self.page.edges, "v")
        elif v_strat == "lines_strict":
            v_base = utils.filter_edges(self.page.edges, "v", edge_type="line")
        elif v_strat == "text":
            v_base = words_to_edges_v(
                words, word_threshold=settings["min_words_vertical"]
            )
        elif v_strat == "explicit":
            v_base = []

        v = v_base + v_explicit

        h_explicit = []
        for desc in settings["explicit_horizontal_lines"]:
            if isinstance(desc, dict):
                for e in utils.obj_to_edges(desc):
                    if e["orientation"] == "h":
                        h_explicit.append(e)
            else:
                h_explicit.append(
                    {
                        "x0": self.page.bbox[0],
                        "x1": self.page.bbox[2],
                        "width": self.page.bbox[2] - self.page.bbox[0],
                        "top": desc,
                        "bottom": desc,
                        "orientation": "h",
                    }
                )

        if h_strat == "lines":
            h_base = utils.filter_edges(self.page.edges, "h")
        elif h_strat == "lines_strict":
            h_base = utils.filter_edges(self.page.edges, "h", edge_type="line")
        elif h_strat == "text":
            h_base = words_to_edges_h(
                words, word_threshold=settings["min_words_horizontal"]
            )
        elif h_strat == "explicit":
            h_base = []

        h = h_base + h_explicit

        edges = list(v) + list(h)

        edges = merge_edges(
            edges,
            snap_x_tolerance=settings["snap_x_tolerance"],
            snap_y_tolerance=settings["snap_y_tolerance"],
            join_x_tolerance=settings["join_x_tolerance"],
            join_y_tolerance=settings["join_y_tolerance"],
        )

        return utils.filter_edges(edges, min_length=settings["edge_min_length"])

    def remove_too_long_edges(self, page, edges, ratio=0.95):
        page_width = page.width
        page_height = page.height

        edges_adequate = []
        for edge in edges:
            if (
                edge["width"] < ratio * page_width
                and edge["height"] < ratio * page_height
            ):
                edges_adequate.append(edge)

        return edges_adequate

    def remove_terminal_edges(self, page, edges):
        edges_ret = []
        for edge in edges:
            if (
                edge["x0"] <= page.height*0.03
                or edge["x1"] >= page.width *0.97
                or edge["top"] <= page.height * 0.03
                or edge["bottom"] >= page.height * 0.97
            ):
                continue
            edges_ret.append(edge)
        return edges_ret

    def remove_too_small_cells(self, cells):
        min_char_width, min_char_height = get_min_char_size(self.page)
        cells_adequate = []
        for cell in cells:
            cell_width, cell_height = get_cell_size(cell)
            if cell_width > min_char_width and cell_height > min_char_height:
                cells_adequate.append(cell)
        return cells_adequate

    def remove_table_without_chars(self, tables, chars):
        ret_tables = []
        tables_bbox = [table.bbox for table in tables]
        chars_bbox = [(c["x0"], c["top"], c["x1"], c["bottom"]) for c in chars]
        overlaps = overlap_bboxes(tables_bbox, chars_bbox)
        idx_tables_with_overlap = set([p[0] for p in overlaps])
        for i, table in enumerate(tables):
            if i in idx_tables_with_overlap:
                ret_tables.append(table)

        return ret_tables

    def remove_table_with_lt_two_cells(self, tables):
        ret_tables = []
        for table in tables:
            if len(table.cells) > 2:
                ret_tables.append(table)

        return ret_tables

    def remove_table_with_unusual_shape(self, tables):
        ret_tables = []
        for table in tables:
            cell_widths = set()
            cell_heights = set()
            for cell in table.cells:
                cell_width, cell_height = get_cell_size(cell)
                cell_widths.add(cell_width)
                cell_heights.add(cell_height)
                # 形が全部違う
            if len(cell_widths) == len(table.cells) and len(cell_heights) == len(
                table.cells
            ):
                continue
            ret_tables.append(table)
        return ret_tables

    def remove_table_with_single_col_row(self, tables):
        ret_tables = []
        for table in tables:
            n_col, n_row = get_cell_nums(table)
            if n_col == 1:
                cell_width, _ = get_cell_size(table.cells[0])
                if cell_width < table.page.width * 0.03:
                    continue
            if n_row == 1:
                _, cell_height = get_cell_size(table.cells[0])
                if cell_height < table.page.height * 0.02:
                    continue
            ret_tables.append(table)
        return ret_tables


def get_bbox_from_table(table):
    """
    returns bounding box of table: (x1, y1, x2, y2)
    """
    return table["bbox"]


def get_min_char_size(page):
    chars = page.chars
    min_width = page.width
    min_height = page.height
    for char in chars:
        min_width = min(min_width, char["width"])
        min_height = min(min_height, char["height"])

    return min_width, min_height


def get_cell_size(cell):
    # width, height
    return cell[2] - cell[0], cell[3] - cell[1]


def overlap_bboxes(bbox_list1, bbox_list2):
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
            _, y1, _, y2 = bbox_list1[bbox_idx]
            if event[3] == 0:
                bbox1_sweeping.append((bbox_idx, y1, y2))
                for bbox2 in bbox2_sweeping:
                    bbox2_idx, bbox2_y1, bbox2_y2 = bbox2
                    if bbox2_y1 <= y2 and bbox2_y2 >= y1:
                        overlap_list.append((bbox_idx, bbox2_idx))
            elif event[3] == 1:
                bbox1_sweeping.remove((bbox_idx, y1, y2))
        else:
            _, y1, _, y2 = bbox_list2[bbox_idx]
            if event[3] == 0:
                bbox2_sweeping.append((bbox_idx, y1, y2))
                for bbox1 in bbox1_sweeping:
                    bbox1_idx, bbox1_y1, bbox1_y2 = bbox1
                    if bbox1_y1 <= y2 and bbox1_y2 >= y1:
                        overlap_list.append((bbox1_idx, bbox_idx))
            elif event[3] == 1:
                bbox2_sweeping.remove((bbox_idx, y1, y2))
        # print(bbox1_sweeping, bbox2_sweeping)

    assert len(bbox1_sweeping) == 0

    return overlap_list


def naive_overlap_bboxes(bbox_list1, bbox_list2):
    overlap_list = []
    for i, bbox1 in enumerate(bbox_list1):
        x1_b1, y1_b1, x2_b1, y2_b1 = bbox1
        for j, bbox2 in enumerate(bbox_list2):
            x1_b2, y1_b2, x2_b2, y2_b2 = bbox2
            if (x1_b1 <= x2_b2 and x2_b1 >= x1_b2) and (
                y1_b1 <= y2_b2 and y2_b1 >= y1_b2
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
